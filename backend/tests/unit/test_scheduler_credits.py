from unittest.mock import MagicMock, patch
import pytest

from bebcare.services.credit_grant_service import CreditError
from bebcare.scheduler.apscheduler_service import _run_platform_image_generation


def test_byok_mode_skips_reserve():
    fn = MagicMock(return_value={"image_urls": ["https://x"]})
    with patch(
        "bebcare.scheduler.apscheduler_service.reserve_one"
    ) as reserve:
        out = _run_platform_image_generation("u1", "byok", fn)
    assert out["image_urls"] == ["https://x"]
    reserve.assert_not_called()
    fn.assert_called_once()


def test_platform_mode_insufficient_raises_without_calling_generate():
    fn = MagicMock()
    with patch(
        "bebcare.scheduler.apscheduler_service.create_generate_task"
    ), patch(
        "bebcare.scheduler.apscheduler_service.Session"
    ) as sess_cls, patch(
        "bebcare.scheduler.apscheduler_service.reserve_one",
        side_effect=CreditError("insufficient"),
    ), patch(
        "bebcare.scheduler.apscheduler_service.update_generate_task"
    ):
        sess_cls.return_value = MagicMock()
        with pytest.raises(Exception, match="平台出图额度不足"):
            _run_platform_image_generation("u1", "platform", fn)
    fn.assert_not_called()
