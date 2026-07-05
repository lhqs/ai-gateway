import argparse
import asyncio
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import or_, select, text

from app.core.config import get_settings
from app.db.models import AdminUser
from app.db.session import SessionLocal, engine
from app.services.admin_auth_service import password_hasher


def generate_password(length: int = 18) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(char.islower() for char in password)
            and any(char.isupper() for char in password)
            and any(char.isdigit() for char in password)
        ):
            return password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or reset an LHQS AI Gateway admin user.")
    parser.add_argument("--email", default="lhqs@gmail.com")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--display-name", default="Admin")
    parser.add_argument("--password", default="lhqs2020")
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Reset password if the user already exists.",
    )
    return parser.parse_args()


async def ensure_admin_schema() -> None:
    sql_path = Path(__file__).resolve().parents[1] / "app" / "db" / "sql" / "007_admin_users.sql"
    statements = [statement.strip() for statement in sql_path.read_text().split(";") if statement.strip()]
    async with engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))


async def main() -> None:
    args = parse_args()
    email = args.email.strip().lower()
    username = args.username.strip().lower()
    password = args.password or generate_password()

    await ensure_admin_schema()

    async with SessionLocal() as session:
        user = await session.scalar(
            select(AdminUser).where(or_(AdminUser.email == email, AdminUser.username == username))
        )
        now = datetime.now(timezone.utc)
        created = False
        password_changed = False

        if user:
            if args.reset_password:
                user.password_hash = password_hasher.hash(password)
                user.password_changed_at = now
                user.token_version += 1
                user.status = "active"
                password_changed = True
            else:
                password = "<unchanged>"
        else:
            user = AdminUser(
                email=email,
                username=username,
                password_hash=password_hasher.hash(password),
                display_name=args.display_name,
                status="active",
                token_version=1,
                password_changed_at=now,
            )
            session.add(user)
            created = True
            password_changed = True

        await session.commit()
        await session.refresh(user)

    await engine.dispose()

    print("Admin user ready.")
    print(f"Backend database: {get_settings().database_url}")
    print(f"User ID: {user.id}")
    print(f"Email: {user.email}")
    print(f"Username: {user.username}")
    print(f"Status: {user.status}")
    if created:
        print("Action: created")
    elif password_changed:
        print("Action: password reset")
    else:
        print("Action: already exists")
        print("Password was not changed. Use --reset-password to reset it.")
    print(f"Password: {password}")


if __name__ == "__main__":
    asyncio.run(main())
