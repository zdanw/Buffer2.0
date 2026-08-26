"""Resend email notifications for auto-publish."""

from __future__ import annotations

import logging
import time
from typing import Iterable

import resend

from bebcare.config.settings import settings

logger = logging.getLogger(__name__)

# 发送失败时重试：默认 3 次，间隔 2s → 4s → 8s
RESEND_MAX_RETRIES = 3
RESEND_RETRY_INITIAL_DELAY = 2.0
RESEND_RETRY_BACKOFF = 2.0


def is_email_configured() -> bool:
    return bool(settings.resend_api_key and settings.resend_from)


def _resend_send(*, to_email: str, subject: str, html: str, text: str) -> None:
    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.resend_from,
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": text,
        }
    )


def _send_with_retry(*, to_email: str, subject: str, html: str, text: str) -> bool:
    delay = RESEND_RETRY_INITIAL_DELAY
    for attempt in range(1, RESEND_MAX_RETRIES + 1):
        try:
            _resend_send(to_email=to_email, subject=subject, html=html, text=text)
            if attempt > 1:
                logger.info(
                    "Auto-publish notification sent to %s on attempt %s/%s",
                    to_email,
                    attempt,
                    RESEND_MAX_RETRIES,
                )
            return True
        except Exception as exc:
            if attempt < RESEND_MAX_RETRIES:
                logger.warning(
                    "Resend send attempt %s/%s to %s failed: %s; retrying in %.1fs",
                    attempt,
                    RESEND_MAX_RETRIES,
                    to_email,
                    str(exc)[:200],
                    delay,
                )
                time.sleep(delay)
                delay *= RESEND_RETRY_BACKOFF
            else:
                logger.exception(
                    "Failed to send auto-publish notification to %s after %s attempts",
                    to_email,
                    RESEND_MAX_RETRIES,
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
            "Auto-publish email skipped: Resend not configured "
            "(set RESEND_API_KEY and RESEND_FROM)"
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
    if _send_with_retry(
        to_email=recipient, subject=subject, html=html_body, text=text_body
    ):
        logger.info("Auto-publish notification sent to %s for task %s", recipient, task_name)
        return True
    return False
