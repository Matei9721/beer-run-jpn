"""Identify image releases that share the same ordered migration contract."""

import hashlib
from pathlib import Path


def schema_channel(migration_root: Path | None = None) -> str:
    root = migration_root or Path(__file__).resolve().parents[1] / "src/beer_run/migrations"
    versions = sorted((root / "versions").glob("[0-9]*.py"))
    if not versions:
        raise ValueError("No ordered migrations found")
    digest = hashlib.sha256()
    for path in [root / "runner.py", *versions]:
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(content.encode() + b"\0")
    return f"schema-{versions[-1].name.split('_', 1)[0]}-{digest.hexdigest()[:16]}"


if __name__ == "__main__":
    print(schema_channel())
