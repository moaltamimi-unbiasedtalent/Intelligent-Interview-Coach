"""Label-checked RAM-backed PostgreSQL 16, explicitly disposable and loopback only."""

from __future__ import annotations
import json
import os
import re
import subprocess
import time
import uuid

IMAGE = "postgres:16@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97"
LABEL = "io.ask4mo.checkpoint.disposable"


def command(args, *, timeout=60, check=True):
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError("disposable_postgresql_command_failed")
    return p


class DisposablePostgres:
    def __init__(self):
        self.token = uuid.uuid4().hex[:16]
        self.name = "ask4mo-checkpoint-" + self.token
        self.cid = None
        self.admin = None

    def verify(self):
        info = json.loads(command(["docker", "inspect", self.cid]).stdout)[0]
        if (
            info["Config"]["Labels"].get(LABEL) != self.token
            or info["Name"] != "/" + self.name
        ):
            raise RuntimeError("disposable_postgresql_ownership_refused")
        return info

    def __enter__(self):
        command(["docker", "image", "inspect", IMAGE])  # no implicit image pull/prune
        self.cid = (
            command(
                [
                    "docker",
                    "run",
                    "-d",
                    "--pull",
                    "never",
                    "--name",
                    self.name,
                    "--label",
                    LABEL + "=" + self.token,
                    "--publish",
                    "127.0.0.1::5432",
                    "--tmpfs",
                    "/var/lib/postgresql/data:rw,nosuid,nodev,size=268435456",
                    "-e",
                    "POSTGRES_USER=disposable",
                    "-e",
                    "POSTGRES_PASSWORD=synthetic-test-only",
                    "-e",
                    "POSTGRES_DB=p5b_checkpoint_test_" + self.token,
                    "--entrypoint",
                    "sleep",
                    IMAGE,
                    "infinity",
                ]
            )
            .stdout.decode()
            .strip()
        )
        try:
            info = self.verify()
            ports = info["NetworkSettings"]["Ports"]["5432/tcp"]
            assert len(ports) == 1 and ports[0]["HostIp"] == "127.0.0.1"
            self.port = int(ports[0]["HostPort"])
            self.admin = f"postgresql+psycopg://disposable:synthetic-test-only@127.0.0.1:{self.port}/p5b_checkpoint_test_{self.token}"
            command(
                [
                    "docker",
                    "exec",
                    "-d",
                    self.cid,
                    "/usr/local/bin/docker-entrypoint.sh",
                    "postgres",
                    "-c",
                    "log_statement=none",
                ]
            )
            self.wait()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def wait(self):
        for _ in range(100):
            p = command(
                [
                    "docker",
                    "exec",
                    self.cid,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "disposable",
                    "-d",
                    "p5b_checkpoint_test_" + self.token,
                ],
                check=False,
            )
            if p.returncode == 0:
                return
            time.sleep(0.2)
        raise RuntimeError("disposable_postgresql_not_ready")

    def stop(self):
        self.verify()
        command(
            [
                "docker",
                "exec",
                "--user",
                "postgres",
                self.cid,
                "pg_ctl",
                "-D",
                "/var/lib/postgresql/data",
                "-m",
                "fast",
                "-w",
                "-t",
                "10",
                "stop",
            ]
        )

    def start(self):
        self.verify()
        command(
            [
                "docker",
                "exec",
                "--user",
                "postgres",
                self.cid,
                "pg_ctl",
                "-D",
                "/var/lib/postgresql/data",
                "-l",
                "/tmp/checkpoint-postgres.log",
                "-w",
                "-t",
                "10",
                "start",
            ]
        )
        self.wait()

    def environment(self):
        return {
            "P5B_PG_ADMIN_URL": self.admin,
            "RUN_CHECKPOINT_RECOVERY_PG": "1",
            "CHECKPOINT_PG_CONTAINER": self.cid,
            "CHECKPOINT_PG_TOKEN": self.token,
        }

    def __exit__(self, *exc):
        if self.cid:
            self.verify()
            command(["docker", "rm", "-fv", self.cid])
            self.cid = None


def control(action):
    """Tests may stop/start ONLY the labelled container created by this runner."""
    cid, token = (
        os.environ.get("CHECKPOINT_PG_CONTAINER", ""),
        os.environ.get("CHECKPOINT_PG_TOKEN", ""),
    )
    if not re.fullmatch(r"[a-f0-9]{64}", cid) or not re.fullmatch(
        r"[a-f0-9]{16}", token
    ):
        raise RuntimeError("disposable_postgresql_control_refused")
    instance = DisposablePostgres()
    instance.token, instance.cid, instance.name = (
        token,
        cid,
        "ask4mo-checkpoint-" + token,
    )
    instance.verify()
    if action == "stop":
        instance.stop()
    elif action == "start":
        instance.start()
    else:
        raise RuntimeError("disposable_postgresql_control_refused")
