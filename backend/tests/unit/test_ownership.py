from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from bebcare.services.ownership import stamp_owner, get_owned_or_404, assert_owned_ref
from bebcare.models.user import User


def test_stamp_owner_sets_user_and_null_workspace():
    user = User(user_id="u-1")
    obj = MagicMock()
    stamp_owner(obj, user)
    assert obj.owner_user_id == "u-1"
    assert obj.workspace_id is None


def test_get_owned_or_404_raises_404_when_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
    user = User(user_id="u-1")
    with pytest.raises(HTTPException) as ei:
        get_owned_or_404(db, MagicMock(), "id-1", user, id_attr="brand_id")
    assert ei.value.status_code == 404


def test_assert_owned_ref_skips_none():
    assert_owned_ref(MagicMock(), MagicMock(), None, User(user_id="u-1"), id_attr="id")
