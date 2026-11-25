"""Administrative commands. These run as the database owner, outside the API.

python -m atlas.cli set-password    set the seeded user's password
python -m atlas.cli dev-password    development only: give a locked seed user a password
"""

import argparse
import getpass
import sys

from sqlalchemy import create_engine, text

from atlas.api.security import hash_password
from atlas.db.seed import LOCKED_PASSWORD_HASH
from atlas.settings import get_settings

DEV_PASSWORD = "atlas-dev"


def _set_password(email: str, password: str, only_if_locked: bool = False) -> int:
    engine = create_engine(get_settings().database_owner_url.get_secret_value())
    sql = "UPDATE users SET password_hash = :hash WHERE email = :email"
    if only_if_locked:
        sql += " AND password_hash = :locked"
    with engine.begin() as connection:
        changed = connection.execute(
            text(sql),
            {"hash": hash_password(password), "email": email, "locked": LOCKED_PASSWORD_HASH},
        ).rowcount
    engine.dispose()
    return int(changed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["set-password", "dev-password"])
    parser.add_argument("--email", default=None)
    args = parser.parse_args()
    settings = get_settings()
    email = (args.email or settings.seed_user_email).lower()

    if args.command == "dev-password":
        if settings.environment != "development":
            sys.stderr.write("dev-password only runs in the development environment\n")
            return 1
        configured = settings.seed_user_password
        password = configured.get_secret_value() if configured else DEV_PASSWORD
        _set_password(email, password, only_if_locked=True)
        return 0

    configured = settings.seed_user_password
    password = configured.get_secret_value() if configured else getpass.getpass("New password: ")
    if len(password) < 12:
        sys.stderr.write("password must be at least 12 characters\n")
        return 1
    if not _set_password(email, password):
        sys.stderr.write("no such user\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
