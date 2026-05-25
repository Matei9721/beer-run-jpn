import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from migrations.runner import MigrationError, MigrationRequired, apply_migrations, validate_database_ready


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Apply or check BoozeRunJpn database migrations.")
    parser.add_argument("--database", help="SQLite database path. Defaults to the app database.")
    parser.add_argument("--check", action="store_true", help="Validate migration readiness without changes.")
    args = parser.parse_args(argv)

    try:
        if args.check:
            validate_database_ready(args.database)
            print("Database migrations are up to date.")
            return 0

        result = apply_migrations(args.database)
        if result.baselined:
            print(f"Baselined migrations: {', '.join(result.baselined)}")
        if result.applied:
            print(f"Applied migrations: {', '.join(result.applied)}")
        if result.skipped and not result.applied and not result.baselined:
            print("Database migrations are already up to date.")
        return 0
    except MigrationRequired as exc:
        print(f"Migration required: {exc}", file=sys.stderr)
        return 1
    except MigrationError as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
