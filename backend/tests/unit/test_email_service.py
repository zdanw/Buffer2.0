"""Unit tests for email notification service."""

from unittest.mock import MagicMock, patch

from bebcare.services import email_service


def test_is_email_configured_false_when_missing():
    with patch.object(email_service.settings, "smtp_host", None):
        with patch.object(email_service.settings, "smtp_from", None):
            assert email_service.is_email_configured() is False


def test_is_email_configured_true_when_set():
    with patch.object(email_service.settings, "smtp_host", "smtp.test"):
        with patch.object(email_service.settings, "smtp_from", "noreply@test.local"):
            assert email_service.is_email_configured() is True


def test_send_auto_publish_skips_without_smtp():
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


def test_send_auto_publish_sends_when_configured():
    mock_smtp = MagicMock()
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    with patch.object(email_service, "is_email_configured", return_value=True):
        with patch.object(email_service.settings, "smtp_host", "smtp.test"):
            with patch.object(email_service.settings, "smtp_port", 587):
                with patch.object(email_service.settings, "smtp_from", "noreply@test.local"):
                    with patch.object(email_service.settings, "smtp_user", None):
                        with patch.object(email_service.settings, "smtp_password", None):
                            with patch.object(email_service.settings, "smtp_use_tls", True):
                                with patch("bebcare.services.email_service.smtplib.SMTP", mock_smtp):
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
    mock_server.starttls.assert_called_once()
    mock_server.sendmail.assert_called_once()
