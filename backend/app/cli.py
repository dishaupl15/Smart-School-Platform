import argparse
from getpass import getpass

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.school import School
from app.services.bootstrap_admin import create_initial_admin


def bootstrap_admin_command() -> None:
    parser = argparse.ArgumentParser(description="Create the initial school administrator.")
    parser.add_argument("--name", required=True, help="Administrator's full name.")
    parser.add_argument("--email", help="Administrator email address.")
    parser.add_argument("--username", help="Administrator username.")
    parser.add_argument("--school-code", required=True, help="School code for the administrator.")
    parser.add_argument("--school-name", help="Create this school when the code does not exist.")
    args = parser.parse_args()
    if not args.email and not args.username:
        parser.error("Provide --email or --username.")
    if not args.school_code.strip() or len(args.school_code.strip()) > 50:
        parser.error("--school-code must contain between 1 and 50 characters.")
    if args.school_name and len(args.school_name.strip()) > 200:
        parser.error("--school-name must not exceed 200 characters.")

    password = getpass("New administrator password: ")
    confirmation = getpass("Confirm administrator password: ")
    if password != confirmation:
        parser.error("Passwords do not match.")

    with SessionLocal() as db:
        try:
            school = db.execute(
                select(School).where(
                    func.lower(School.school_code) == args.school_code.strip().casefold()
                )
            ).scalar_one_or_none()
            if school is None:
                if not args.school_name or not args.school_name.strip():
                    parser.error(
                        "The school code does not exist; provide --school-name to create it."
                    )
                db.add(
                    School(
                        name=args.school_name.strip(),
                        school_code=args.school_code.strip().upper(),
                    )
                )
                db.flush()
            user = create_initial_admin(
                db,
                full_name=args.name,
                email=args.email,
                username=args.username,
                school_code=args.school_code,
                password=password,
            )
        except (ValueError, RuntimeError) as error:
            db.rollback()
            parser.error(str(error))
    print(f"Created administrator {user.id}.")


if __name__ == "__main__":
    bootstrap_admin_command()
