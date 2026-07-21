import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from bebcare.database import SessionLocal
from bebcare.models.user import User
from bebcare.services.auth_service import get_password_hash
import secrets
import string


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def init_admin():
    db: Session = SessionLocal()
    try:
        admin_username = "admin"
        admin_email = "admin@bebcare.com"

        existing_admin = db.query(User).filter(User.username == admin_username).first()
        if existing_admin:
            print(f"管理员账户 {admin_username} 已存在，跳过初始化")
            return

        password = generate_password()
        hashed_password = get_password_hash(password)

        admin_user = User(
            username=admin_username,
            email=admin_email,
            hashed_password=hashed_password,
            is_active=True,
            is_admin=True
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        print("=" * 50)
        print("管理员账户初始化成功！")
        print("=" * 50)
        print(f"用户名: {admin_username}")
        print(f"邮箱: {admin_email}")
        print(f"密码: {password}")
        print("=" * 50)
        print("请妥善保存上述密码，登录后建议及时修改")

    except Exception as e:
        print(f"初始化失败: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_admin()