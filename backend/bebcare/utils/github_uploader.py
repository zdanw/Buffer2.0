import logging

logger = logging.getLogger(__name__)

import base64
import re
import uuid
import requests
import time
from bebcare.config.settings import settings
from datetime import datetime
import os


class _NonRetryableUploadError(Exception):
    """Auth/config errors that should not be retried."""


class GitHubUploader:
    def __init__(self):
        self.token = settings.github_token
        self.username = settings.github_username
        self.repo = settings.github_repo
        self.branch = settings.github_branch
        self.base_url = f"https://api.github.com/repos/{self.username}/{self.repo}"

    def _ensure_configured(self):
        missing = [
            name
            for name, value in (
                ("github_token", self.token),
                ("github_username", self.username),
                ("github_repo", self.repo),
                ("github_branch", self.branch),
            )
            if not value
        ]
        if missing:
            raise _NonRetryableUploadError(
                f"GitHub CDN not configured: missing {', '.join(missing)}"
            )

    @staticmethod
    def _sanitize_filename(file_name: str) -> str:
        base = os.path.basename(file_name or "image.jpg")
        name, ext = os.path.splitext(base)
        if not ext or len(ext) > 8:
            ext = ".jpg"
        name = re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE).strip("._") or "image"
        return f"{name[:80]}{ext.lower()}"

    def upload_file(self, file_content, file_name, directory="images"):
        try:
            self._ensure_configured()
        except _NonRetryableUploadError:
            logger.error(
                "[CDN] GitHub upload aborted: missing config "
                "(token=%s username=%s repo=%s branch=%s)",
                bool(self.token),
                bool(self.username),
                bool(self.repo),
                bool(self.branch),
            )
            raise

        safe_name = self._sanitize_filename(file_name)
        name, ext = os.path.splitext(safe_name)

        if isinstance(file_content, bytes):
            raw = file_content
        else:
            raw = file_content.read()
            if hasattr(file_content, "seek"):
                file_content.seek(0)

        if not raw:
            raise _NonRetryableUploadError("Refusing to upload empty file content")

        content = base64.b64encode(raw).decode("utf-8")
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }

        logger.info(
            "[CDN] GitHub upload start repo=%s/%s branch=%s bytes=%s file_name=%s",
            self.username,
            self.repo,
            self.branch,
            len(raw),
            safe_name,
        )

        last_error = None
        # Unique path per attempt avoids 409 collisions on second-precision names
        for attempt in range(3):
            new_filename = (
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
                f"{uuid.uuid4().hex[:12]}_{name}{ext}"
            )
            path = f"{directory}/{new_filename}"
            url = f"{self.base_url}/contents/{path}"
            data = {
                "message": f"Upload image: {new_filename}",
                "content": content,
                "branch": self.branch,
            }

            try:
                response = requests.put(url, json=data, headers=headers, timeout=90)
            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    "[CDN] GitHub network error attempt=%s/%s path=%s err=%s",
                    attempt + 1,
                    3,
                    path,
                    e,
                )
                time.sleep(2.0 * (attempt + 1))
                continue

            if response.status_code in (200, 201):
                cdn_url = (
                    f"https://cdn.jsdelivr.net/gh/{self.username}/"
                    f"{self.repo}@{self.branch}/{path}"
                )
                logger.info(
                    "[CDN] GitHub upload ok status=%s path=%s cdn_url=%s",
                    response.status_code,
                    path,
                    cdn_url,
                )
                return cdn_url

            body = (response.text or "")[:500]
            if response.status_code in (401, 403):
                logger.error(
                    "[CDN] GitHub auth/permission error status=%s path=%s body=%s",
                    response.status_code,
                    path,
                    body,
                )
                raise _NonRetryableUploadError(
                    f"GitHub auth/permission error ({response.status_code}): {body}"
                )

            if response.status_code == 409:
                last_error = Exception(f"GitHub path conflict (409): {body}")
                logger.warning(
                    "[CDN] GitHub 409 conflict path=%s, regenerating path...", path
                )
                continue

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 5.0 * (attempt + 1)
                )
                last_error = Exception(f"GitHub rate limited (429): {body}")
                logger.warning(
                    "[CDN] GitHub rate limited status=429 wait=%.1fs body=%s",
                    wait,
                    body,
                )
                time.sleep(wait)
                continue

            last_error = Exception(
                f"Failed to upload to GitHub ({response.status_code}): {body}"
            )
            logger.warning(
                "[CDN] GitHub upload failed attempt=%s/%s status=%s path=%s body=%s",
                attempt + 1,
                3,
                response.status_code,
                path,
                body,
            )
            time.sleep(2.0 * (attempt + 1))

        logger.error(
            "[CDN] GitHub upload exhausted retries repo=%s/%s file_name=%s last_error=%s",
            self.username,
            self.repo,
            safe_name,
            last_error,
        )
        raise last_error or Exception("Failed to upload to GitHub")


github_uploader = GitHubUploader()
