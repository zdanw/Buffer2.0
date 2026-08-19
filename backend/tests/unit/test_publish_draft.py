"""Publish-from-draft must not wrap HTTPException as 500."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from bebcare.api import task_routes
from bebcare.schemas.task import DraftPublishRequest
from bebcare.services.buffer_account_service import BufferAccountUnavailable


def test_publish_draft_buffer_unavailable_stays_http_400():
    draft = SimpleNamespace(
        status="pending",
        images=["http://img.example/a.jpg"],
        copywritings=["hello"],
        product_id="prod-1",
        draft_id="draft-1",
    )
    request = DraftPublishRequest(
        selected_image_index=0,
        selected_copy_index=0,
        platforms=["instagram"],
    )
    user = SimpleNamespace(user_id="user-1")

    with (
        patch.object(task_routes, "get_owned_or_404", return_value=draft),
        patch.object(
            task_routes, "persist_image_url_to_cdn", return_value="https://cdn/a.jpg"
        ),
        patch.object(
            task_routes,
            "resolve_buffer_api_token",
            side_effect=BufferAccountUnavailable("Buffer account is not configured"),
        ),
    ):
        with pytest.raises(HTTPException) as ei:
            task_routes.publish_draft("draft-1", request, db=object(), current_user=user)

    assert ei.value.status_code == 400
    assert "500" not in str(ei.value.status_code)
    assert "Publish failed" not in str(ei.value.detail)
