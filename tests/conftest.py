"""Environment bootstrap for the unit suite.

Several modules read configuration at import time — `src/utils/crypto.py` demands
ENCRYPTION_KEY, and `src/services/service_providers.py` builds a
DatabaseSessionService from POSTGRES_CONNECTION_STRING — so importing anything
that transitively reaches them (chat_routes, the middleware) blows up before a
single test runs. These are placeholders: SQLAlchemy resolves the URL lazily, so
nothing here opens a connection. Real values in the environment still win.

It also applies tests/ci_exclusions.txt, the only way to leave a test out of the run.
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("ENCRYPTION_KEY", "hAAcxHzMlM1BiZWpVQlZ4b0hTZ0dJbEZzWWVQb0k9PQ=")
os.environ.setdefault(
    "POSTGRES_CONNECTION_STRING", "postgresql://tests:tests@localhost:5432/tests"
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


_EXCLUSIONS = Path(__file__).with_name("ci_exclusions.txt")


def _read_exclusions(root: Path) -> tuple[set[str], set[str]]:
    files, node_ids, problems = set(), set(), []
    lines = _EXCLUSIONS.read_text(encoding="utf-8").splitlines()
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        where = f"tests/{_EXCLUSIONS.name}:{number}"
        if len(parts) != 3 or not all(parts):
            problems.append(f"{where}: expected 'test | owner | reason'")
            continue
        target = parts[0]
        if not (root / target.split("::")[0]).is_file():
            problems.append(f"{where}: file not found: {target}")
            continue
        (node_ids if "::" in target else files).add(target)
    if problems:
        raise pytest.UsageError("\n".join(problems))
    return files, node_ids


def pytest_configure(config):
    config._ci_excluded_files, config._ci_excluded_ids = _read_exclusions(config.rootpath)


def pytest_ignore_collect(collection_path, config):
    if not collection_path.is_relative_to(config.rootpath):
        return None
    if collection_path.relative_to(config.rootpath).as_posix() in config._ci_excluded_files:
        return True
    return None


def pytest_collection_modifyitems(config, items):
    wanted = config._ci_excluded_ids
    kept = [item for item in items if item.nodeid not in wanted]
    dropped = [item for item in items if item.nodeid in wanted]
    collected_files = {item.nodeid.split("::")[0] for item in items}
    stale = sorted(
        node_id
        for node_id in wanted - {item.nodeid for item in dropped}
        if node_id.split("::")[0] in collected_files
    )
    if stale:
        raise pytest.UsageError(
            f"tests/{_EXCLUSIONS.name} names tests that no longer exist: " + ", ".join(stale)
        )
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept
