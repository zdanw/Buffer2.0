from sqlalchemy.orm import Session
from bebcare.database import SessionLocal
from bebcare.models.user import User
from bebcare.services.auth_service import get_password_hash
from bebcare.config.settings import settings
import logging

logger = logging.getLogger(__name__)


def init_admin_user(db: Session) -> None:
    admin_username = getattr(settings, 'admin_username', 'admin')
    admin_email = getattr(settings, 'admin_email', 'admin@bebcare.com')
    admin_password = getattr(settings, 'admin_password', None)

    existing_admin = db.query(User).filter(User.username == admin_username).first()
    if existing_admin:
        logger.info(f"管理员账户 {admin_username} 已存在，跳过初始化")
        return

    if not admin_password:
        raise RuntimeError(
            f"首次创建管理员账户需要配置 ADMIN_PASSWORD。"
            f"请在 .env 中设置后重启，或运行: python scripts/reset_admin_password.py"
        )

    hashed_password = get_password_hash(admin_password)

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

    logger.info("管理员账户初始化成功：username=%s email=%s（密码不写入日志）", admin_username, admin_email)


def initialize_data() -> None:
    db: Session = SessionLocal()
    try:
        init_admin_user(db)
        logger.info("数据初始化完成")
    except Exception as e:
        logger.error(f"数据初始化失败: {str(e)}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    initialize_data()