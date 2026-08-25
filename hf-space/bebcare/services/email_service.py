"""SMTP email notifications for auto-publish."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable

from bebcare.config.settings import settings

logger = logging.getLogger(__name__)


def is_email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email.strip()
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, [to_email.strip()], msg.as_string())
        logger.info("Auto-publish notification sent to %s for task %s", to_email, task_name)
        return True
    except Exception:
        logger.exception("Failed to send auto-publish notification to %s", to_email)
        return False
