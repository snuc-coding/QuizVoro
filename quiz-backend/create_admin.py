"""
create_admin.py — Command-line script to create an administrator account.

Usage (from the quiz-backend/ directory):
    python create_admin.py

This script:
  1. Prompts for username, email, and password (with confirmation).
  2. Validates inputs.
  3. Hashes the password with Argon2.
  4. Creates the admin in PostgreSQL.

Run this ONCE after setting up the database for the first time.
Do NOT expose admin creation as a public REST API endpoint.

Windows PowerShell example:
    cd quiz-backend
    python create_admin.py
"""

import getpass
import sys
from pathlib import Path

# Add the quiz-backend directory to Python's path so "from app.xxx import ..." works.
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.services.auth_service import create_admin


def main() -> None:
    print("=" * 50)
    print("  Cognizant Quiz Club — Create Admin Account")
    print("=" * 50)
    print()

    username = input("Enter admin username: ").strip()
    if not username:
        print("ERROR: Username cannot be empty.")
        sys.exit(1)

    email = input("Enter admin email: ").strip()
    if not email or "@" not in email:
        print("ERROR: Please enter a valid email address.")
        sys.exit(1)

    password = getpass.getpass("Enter password (min 8 characters): ")
    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters.")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("ERROR: Passwords do not match.")
        sys.exit(1)

    print()
    print(f"Creating admin: username='{username}', email='{email}'")
    print("Hashing password with Argon2 (this may take a moment)...")

    db = SessionLocal()
    try:
        admin = create_admin(db, username, email, password)
        print()
        print(f"✓ Admin created successfully! ID: {admin.id}")
        print(f"  Username: {admin.username}")
        print(f"  Email:    {admin.email}")
        print()
        print("You can now log in via: POST /api/v1/admin/login")
    except ValueError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Is the database running and are migrations applied?")
        print("  Run: alembic upgrade head")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
