from sqlalchemy import Column, String, ForeignKey


class OwnedMixin:
    owner_user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(String(36), nullable=True, index=True)
