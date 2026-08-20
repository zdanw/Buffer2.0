import uuid
import pytest
from bebcare.database import Base, SessionLocal, engine
from bebcare.models.image_provider import ImageProviderConfig
from bebcare.utils.crypto import encrypt_secret
from bebcare.providers.registry import resolve_system_image_provider
import bebcare.models  # noqa: F401


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


def test_resolve_system_missing(db_session):
    # Ensure no leftover system rows from other tests affect this assert strongly:
    # delete system rows in this session's view then resolve.
    db_session.query(ImageProviderConfig).filter(
        ImageProviderConfig.is_system == True  # noqa: E712
    ).delete(synchronize_session=False)
    db_session.flush()
    with pytest.raises(ValueError, match="平台图像供应商"):
        resolve_system_image_provider(db_session)


def test_resolve_system_ok(db_session):
    row = ImageProviderConfig(
        id=str(uuid.uuid4()),
        owner_user_id=None,
        name="Platform",
        provider_type="openai_compatible",
        base_url="https://example.com/v1",
        api_key_encrypted=encrypt_secret("sk-test"),
        supports_list_models=False,
        default_model="demo-model",
        is_active=True,
        is_default=True,
        is_system=True,
    )
    db_session.add(row)
    db_session.flush()
    _provider, model = resolve_system_image_provider(db_session, None)
    assert model == "demo-model"
