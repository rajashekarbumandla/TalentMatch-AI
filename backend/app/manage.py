"""
Server-side account maintenance (run from the backend/ folder):

    python -m app.manage list-users
    python -m app.manage create-user  --email a@b.com --name "Asha Rao" --password "Temp1234" [--admin]
    python -m app.manage reset-password --email a@b.com --password "NewPass123"
    python -m app.manage delete-user  --email a@b.com      # deletes the account AND all its data

Use reset-password if the only admin forgets their password (there is no email
service, so this is the recovery path). delete-user exists mainly for automated tests;
in the app, accounts are disabled instead of deleted.
"""
import argparse
import sys

from app.database import SessionLocal, init_db
from app.services import user_service


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.manage", description="TalentMatch AI account maintenance")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-users")
    create = sub.add_parser("create-user")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--password", required=True)
    create.add_argument("--admin", action="store_true")
    reset = sub.add_parser("reset-password")
    reset.add_argument("--email", required=True)
    reset.add_argument("--password", required=True)
    delete = sub.add_parser("delete-user")
    delete.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    init_db()
    with SessionLocal() as db:
        try:
            if args.command == "list-users":
                for u in user_service.list_users(db):
                    print(f"{u.email:35} {u.role:6} {'active' if u.is_active else 'disabled':9} {u.full_name}")
                return 0
            if args.command == "create-user":
                user = user_service.create_user(db, args.name, args.email, args.password, "admin" if args.admin else "hr")
                print(f"Created {user.role} account {user.email}")
                return 0
            user = user_service.get_by_email(db, args.email)
            if user is None:
                print(f"No account with email {args.email}", file=sys.stderr)
                return 1
            if args.command == "reset-password":
                user_service.set_password(db, user, args.password)
                if not user.is_active:
                    user.is_active = True
                    db.commit()
                print(f"Password reset for {user.email} (account active)")
                return 0
            db.delete(user)  # ON DELETE CASCADE removes the user's jobs, candidates, analyses and results
            db.commit()
            print(f"Deleted {user.email} and all of their data")
            return 0
        except user_service.AccountError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())
