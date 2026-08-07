"""
Create or update a User row with a properly bcrypt-hashed password.

This is the only supported way to provision a login now that the API has
no /register endpoint and passwords are hashed (not stored/compared as
plaintext). Run interactively so the password never appears in shell
history or process listings:

    python scripts/create_user.py <username> [--role Admin|PM|Finance|Developer]
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from db import SessionLocal, User
from utils.security import hash_password

VALID_ROLES = {"Admin", "PM", "Finance", "Developer"}


def create_or_update_user(username: str, password: str, role: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        hashed = hash_password(password)
        if user:
            user.password_hash = hashed
            user.role = role
            print(f"Updated existing user '{username}' (role={role}).")
        else:
            user = User(username=username, password_hash=hashed, role=role)
            db.add(user)
            print(f"Created new user '{username}' (role={role}).")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--role", default="Admin", choices=sorted(VALID_ROLES))
    args = parser.parse_args()

    password = getpass.getpass(f"Password for '{args.username}': ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    create_or_update_user(args.username, password, args.role)
