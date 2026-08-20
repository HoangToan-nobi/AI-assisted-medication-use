#!/usr/bin/env python3
"""Production entrypoint: validate config, migrate auth schema, then serve."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings, validate_production_auth_settings


def main() -> None:
    settings = get_settings()
    validate_production_auth_settings(settings)

    # Import after validation so an invalid production configuration cannot
    # mutate the database before the container exits.
    from scripts.migrate_auth import migrate

    migrate()
    if settings.enable_demo_accounts:
        from scripts.seed_demo_users import main as seed_demo_users

        seed_demo_users()

    port = os.environ.get("PORT", "8000")
    os.execvp(
        "uvicorn",
        ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", port],
    )


if __name__ == "__main__":
    main()
