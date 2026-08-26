"""Unit tests for email notification service."""

from unittest.mock import patch

from bebcare.services import email_service


def test_is_email_configured_false_when_missing():
    with patch.object(email_service.settings, "resend_api_key", None):
        with patch.object(email_service.settings, "resend_from", None):
            assert email_service.is_email_configured() is False


def test_is_email_configured_true_when_set():
    with patch.object(email_service.settings, "resend_api_key", "re_test"):
        with patch.object(email_service.settings, "resend_from", "noreply@test.local"):
            assert email_service.is_email_configured() is True


def test_send_auto_publish_skips_without_resend():
    with patch.object(email_service, "is_email_configured", return_value=False):
        assert (
            email_service.send_auto_publish_notification(
                "user@test.local",
                task_name="Daily",
                product_name="Product A",
                copywriting="Hello world",
                image_url="https://cdn.example/img.jpg",
                platform_posts=[{"platform": "instagram", "post_link": "https://instagram.com/p/1"}],
            )
            is False
        )


def _resend_settings_ctx():
    return patch.multiple(
        email_service.settings,
        resend_api_key="re_test",
        resend_from="PulseForge <noreply@test.local>",
    )


def test_send_auto_publish_sends_when_configured():
    with patch.object(email_service, "is_email_configured", return_value=True):
        with _resend_settings_ctx():
            with patch("bebcare.services.email_service.resend.Emails.send") as mock_send:
                ok = email_service.send_auto_publish_notification(
                    "user@test.local",
                    task_name="Daily",
                    product_name="Product A",
                    copywriting="Hello world",
                    image_url="https://cdn.example/img.jpg",
                    platform_posts=[
                        {
                            "platform": "instagram",
                            "channel": "brand",
                            "post_link": "https://instagram.com/p/abc",
                        }
                    ],
                )
    assert ok is True
    mock_send.assert_called_once()
    params = mock_send.call_args[0][0]
    assert params["to"] == ["user@test.local"]
    assert params["from"] == "PulseForge <noreply@test.local>"
    assert "Daily" in params["subject"]
    assert "html" in params and "text" in params


def test_send_retries_then_succeeds():
    with patch.object(email_service, "is_email_configured", return_value=True):
        with _resend_settings_ctx():
            with patch(
                "bebcare.services.email_service.resend.Emails.send",
                side_effect=[RuntimeError("temporary"), {"id": "ok"}],
            ) as mock_send:
                with patch("bebcare.services.email_service.time.sleep") as sleep_mock:
                    with patch.object(email_service, "RESEND_MAX_RETRIES", 3):
                        with patch.object(email_service, "RESEND_RETRY_INITIAL_DELAY", 0.01):
                            ok = email_service.send_auto_publish_notification(
                                "user@test.local",
                                task_name="Daily",
                                product_name="Product A",
                                copywriting="Hello",
                                image_url=None,
                                platform_posts=[
                                    {"platform": "instagram", "post_link": "https://x"}
                                ],
                            )
    assert ok is True
    assert mock_send.call_count == 2
    sleep_mock.assert_called_once()


def test_send_retries_exhausted_returns_false():
    with patch.object(email_service, "is_email_configured", return_value=True):
        with _resend_settings_ctx():
            with patch(
                "bebcare.services.email_service.resend.Emails.send",
                side_effect=RuntimeError("permanent failure"),
            ) as mock_send:
                with patch("bebcare.services.email_service.time.sleep") as sleep_mock:
                    with patch.object(email_service, "RESEND_MAX_RETRIES", 3):
                        with patch.object(email_service, "RESEND_RETRY_INITIAL_DELAY", 0.01):
                            with patch.object(email_service, "RESEND_RETRY_BACKOFF", 2.0):
                                ok = email_service.send_auto_publish_notification(
                                    "user@test.local",
                                    task_name="Daily",
                                    product_name="Product A",
                                    copywriting="Hello",
                                    image_url=None,
                                    platform_posts=[],
                                )
    assert ok is False
    assert mock_send.call_count == 3
    assert sleep_mock.call_count == 2
