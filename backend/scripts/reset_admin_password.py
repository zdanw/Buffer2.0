import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from bebcare.database import SessionLocal, engine, Base
from bebcare.models import User
from bebcare.services.auth_service import get_password_hash
import secrets
import string

Base.metadata.create_all(bind=engine)


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


def reset_admin_password(password: str | None = None):
    db: Session = SessionLocal()
    try:
        admin_username = os.getenv("ADMIN_USERNAME", "admin")

        admin_user = db.query(User).filter(User.username == admin_username).first()
        if not admin_user:
            print(f"管理员账户 {admin_username} 不存在")
            return

        if not password:
            password = os.getenv("ADMIN_PASSWORD") or generate_password()

        admin_user.hashed_password = get_password_hash(password)
        admin_user.is_active = True
        admin_user.is_admin = True
        db.commit()

        print("=" * 50)
        print("管理员密码重置成功！")
        print("=" * 50)
        print(f"用户名: {admin_username}")
        print(f"邮箱: {admin_user.email}")
        print(f"新密码: {password}")
        print("=" * 50)
        print("请妥善保存上述密码，登录后建议及时修改")

    except Exception as e:
        print(f"重置失败: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="重置管理员密码")
    parser.add_argument(
        "--password",
        "-p",
        default=None,
        help="新密码；也可设环境变量 ADMIN_PASSWORD；都不传则随机生成",
    )
    args = parser.parse_args()
    reset_admin_password(args.password)
