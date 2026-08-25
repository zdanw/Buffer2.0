"""SMTP email notifications for auto-publish."""

from __future__ import annotations

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable

from bebcare.config.settings import settings

logger = logging.getLogger(__name__)

# 连接/发送失败时重试：默认 3 次，间隔 2s → 4s → 8s
SMTP_MAX_RETRIES = 3
SMTP_RETRY_INITIAL_DELAY = 2.0
SMTP_RETRY_BACKOFF = 2.0


def is_email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def _smtp_send(msg: MIMEMultipart, to_email: str) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, [to_email], msg.as_string())


def _send_with_retry(msg: MIMEMultipart, to_email: str) -> bool:
    delay = SMTP_RETRY_INITIAL_DELAY
    for attempt in range(1, SMTP_MAX_RETRIES + 1):
        try:
            _smtp_send(msg, to_email)
            if attempt > 1:
                logger.info(
                    "Auto-publish notification sent to %s on attempt %s/%s",
                    to_email,
                    attempt,
                    SMTP_MAX_RETRIES,
                )
            return True
        except Exception as exc:
            if attempt < SMTP_MAX_RETRIES:
                logger.warning(
                    "SMTP send attempt %s/%s to %s failed: %s; retrying in %.1fs",
                    attempt,
                    SMTP_MAX_RETRIES,
                    to_email,
                    str(exc)[:200],
                    delay,
                )
                time.sleep(delay)
                delay *= SMTP_RETRY_BACKOFF
            else:
                logger.exception(
                    "Failed to send auto-publish notification to %s after %s attempts",
                    to_email,
                    SMTP_MAX_RETRIES,
                )
    return False


def _build_post_links_html(platform_posts: Iterable[dict]) -> str:
    items = []
    for entry in platform_posts:
        platform = entry.get("platform") or "unknown"
        channel = entry.get("channel")
        link = entry.get("post_link")
        label = platform
        if channel:
            label = f"{platform} ({channel})"
        if link:
            items.append(f'<li><a href="{link}">{label}</a></li>')
        else:
            post_id = entry.get("post_id")
            suffix = f" — post {post_id}" if post_id else ""
            items.append(f"<li>{label}{suffix}</li>")
    if not items:
        return "<p>（暂无帖子链接）</p>"
    return "<ul>" + "".join(items) + "</ul>"


def _build_post_links_text(platform_posts: Iterable[dict]) -> str:
    lines = []
    for entry in platform_posts:
        platform = entry.get("platform") or "unknown"
        channel = entry.get("channel")
        link = entry.get("post_link")
        label = platform
        if channel:
            label = f"{platform} ({channel})"
        if link:
            lines.append(f"- {label}: {link}")
        else:
            post_id = entry.get("post_id")
            suffix = f" (post {post_id})" if post_id else ""
            lines.append(f"- {label}{suffix}")
    return "\n".join(lines) if lines else "（暂无帖子链接）"


def send_auto_publish_notification(
    to_email: str,
    *,
    task_name: str,
    product_name: str,
    copywriting: str,
    image_url: str | None,
    platform_posts: list[dict],
) -> bool:
    """Send notification after a successful auto publish. Returns True if sent."""
    if not to_email or not to_email.strip():
        logger.warning("Auto-publish email skipped: recipient email is empty")
        return False
    if not is_email_configured():
        logger.warning(
            "Auto-publish email skipped: SMTP not configured (set SMTP_HOST and SMTP_FROM)"
        )
        return False

    subject = f"[{task_name}] 已自动发布 — {product_name}"
    copy_preview = (copywriting or "").strip()
    if len(copy_preview) > 500:
        copy_preview = copy_preview[:500] + "…"

    image_block_html = ""
    image_block_text = ""
    if image_url:
        image_block_html = f'<p><strong>配图：</strong><br><a href="{image_url}">{image_url}</a></p>'
        image_block_text = f"\n配图：{image_url}\n"

    html_body = f"""\
<html><body>
<p>任务 <strong>{task_name}</strong> 已自动发布产品 <strong>{product_name}</strong>。</p>
<p><strong>文案：</strong></p>
<pre style="white-space:pre-wrap;font-family:inherit;">{copy_preview}</pre>
{image_block_html}
<p><strong>帖子链接：</strong></p>
{_build_post_links_html(platform_posts)}
<p style="color:#666;font-size:12px;">此邮件由 PulseForge 自动发布功能发送。</p>
</body></html>"""

    text_body = f"""\
任务「{task_name}」已自动发布产品「{product_name}」。

文案：
{copy_preview}
{image_block_text}
帖子链接：
{_build_post_links_text(platform_posts)}

— PulseForge 自动发布
"""

    recipient = to_email.strip()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = recipient
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if _send_with_retry(msg, recipient):
        logger.info("Auto-publish notification sent to %s for task %s", recipient, task_name)
        return True
    return False
