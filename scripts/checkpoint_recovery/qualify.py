"""Opt-in real PostgreSQL outage qualification; emits only redacted test metadata."""

from __future__ import annotations
import argparse
import json
from importlib.metadata import version
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from scripts.checkpoint_recovery.disposable import DisposablePostgres


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Refuse reuse, including private artifacts from earlier qualifications.
    args.output.mkdir(parents=True, exist_ok=False)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"]))
    result = {
        "source_sha": sha,
        "working_tree_dirty": dirty,
        "result": "FAIL",
        "scope": "disposable PG16; synthetic model and HTTP identity seam; no deployment",
    }
    result["dependencies"] = {
        name: version(name)
        for name in (
            "langgraph",
            "langgraph-checkpoint",
            "langgraph-checkpoint-postgres",
            "psycopg",
            "psycopg-pool",
            "SQLAlchemy",
        )
    }
    with tempfile.TemporaryDirectory(prefix="ask4mo-checkpoint-") as private:
        junit = Path(private) / "results.xml"
        with DisposablePostgres() as pg:
            env = dict(os.environ, **pg.environment())
            import psycopg

            with psycopg.connect(
                pg.admin.replace("postgresql+psycopg:", "postgresql:"),
                connect_timeout=2,
            ) as conn:
                result["postgresql_version"] = conn.execute(
                    "SHOW server_version"
                ).fetchone()[0]
            with (Path(private) / "pytest.log").open("w") as log:
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        "-o",
                        "addopts=",
                        "-p",
                        "no:cacheprovider",
                        "tests/test_agent_checkpoint_recovery_pg.py",
                        "--junitxml=" + str(junit),
                    ],
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            result["pytest_exit"] = proc.returncode
            if junit.exists():
                cases = list(ET.parse(junit).iter("testcase"))
                result["tests"] = [
                    {
                        "name": t.attrib["name"],
                        "outcome": "failed"
                        if t.find("failure") is not None or t.find("error") is not None
                        else "skipped"
                        if t.find("skipped") is not None
                        else "passed",
                    }
                    for t in cases
                ]
                result["counts"] = {
                    k: sum(t["outcome"] == k for t in result["tests"])
                    for k in ("passed", "failed", "skipped")
                }
                if (
                    proc.returncode == 0
                    and len(cases) >= 17
                    and result["counts"]["failed"] == result["counts"]["skipped"] == 0
                ):
                    result["result"] = "PASS"
        result["owned_container_removed"] = True
        (args.output / "checkpoint-recovery.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("source_sha", "working_tree_dirty", "result", "counts")
                if k in result
            }
        )
    )
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
