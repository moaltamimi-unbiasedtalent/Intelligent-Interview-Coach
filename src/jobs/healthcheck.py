"""Container healthcheck for the job worker (05A): ``python -m src.jobs.healthcheck [max_age_seconds]``.

Exit 0 when a ``running`` worker heartbeat is fresh, 1 otherwise. The default window (180s) is deliberately more lenient than the
admin "seen recently" window (60s) so a long job does not get the worker restarted. Prints nothing sensitive.
"""

from __future__ import annotations

import sys

DEFAULT_MAX_AGE_SECONDS = 180


def main(argv: list[str] | None = None) -> int:   # pragma: no cover - thin entrypoint, logic tested via worker_heartbeat_fresh
    args = sys.argv[1:] if argv is None else argv
    try:
        max_age = int(args[0]) if args else DEFAULT_MAX_AGE_SECONDS
    except ValueError:
        max_age = DEFAULT_MAX_AGE_SECONDS
    try:
        from src.application.factories import build_repository
        from src.application.hosted_readiness import worker_heartbeat_fresh
        from src.config import load_config

        repo = build_repository(load_config())
        return 0 if worker_heartbeat_fresh(repo.session_factory, max_age_seconds=max_age) else 1
    except Exception:  # noqa: BLE001
        return 1


if __name__ == "__main__":   # pragma: no cover
    sys.exit(main())
