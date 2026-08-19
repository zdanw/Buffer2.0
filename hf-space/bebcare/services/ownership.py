from typing import Any, Optional, Type
from fastapi import HTTPException
from sqlalchemy.orm import Session, Query
from bebcare.models.user import User


def owned_query(db: Session, model: Type[Any], user: User) -> Query:
    return db.query(model).filter(model.owner_user_id == user.user_id)


def get_owned_or_404(
    db: Session,
    model: Type[Any],
    ident: str,
    user: User,
    *,
    id_attr: str,
) -> Any:
    row = (
        owned_query(db, model, user)
        .filter(getattr(model, id_attr) == ident)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


def stamp_owner(obj: Any, user: User) -> None:
    obj.owner_user_id = user.user_id
    obj.workspace_id = None


def assert_owned_ref(
    db: Session,
    model: Type[Any],
    ident: Optional[str],
    user: User,
    *,
    id_attr: str,
) -> None:
    if ident is None:
        return
    get_owned_or_404(db, model, ident, user, id_attr=id_attr)
