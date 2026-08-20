from bebcare.database import Base
import bebcare.models  # noqa: F401
from bebcare.db.rls_tables import APP_RLS_TABLES


def test_rls_table_list_covers_orm_tables():
    orm = {t.name for t in Base.metadata.sorted_tables}
    assert set(APP_RLS_TABLES) == orm


def test_credit_tables_in_rls_list():
    assert "image_credit_grants" in APP_RLS_TABLES
    assert "image_credit_reservations" in APP_RLS_TABLES
