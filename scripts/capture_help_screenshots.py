"""Capture PulseForge UI screenshots for the Help Center."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "docs" / "screenshots"
BASE = os.environ.get("PULSEFORGE_FRONTEND_URL", "http://localhost:5174")
API = os.environ.get("PULSEFORGE_API_URL", "http://localhost:8888")

DOCS_DEMO_USERNAME = os.environ.get("DOCS_DEMO_USERNAME", "docs-demo")
DOCS_DEMO_PASSWORD = os.environ.get("DOCS_DEMO_PASSWORD", "DocsDemo2026!")

SKIP_KEY = "pulseforge_onboarding_skipped"
CHECKLIST_OPEN_KEY = "pulseforge_getting_started_open"


def seed_sandbox() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_docs_sandbox.py")],
        check=True,
        cwd=str(ROOT),
    )


def login_token(username: str | None = None, password: str | None = None) -> str:
    username = username or DOCS_DEMO_USERNAME
    password = password or DOCS_DEMO_PASSWORD
    r = httpx.post(
        f"{API}/v1/auth/login/",
        data={"username": username, "password": password},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def mark_onboarding_complete(token: str) -> None:
    httpx.post(
        f"{API}/v1/auth/me/onboarding-complete",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )


def reset_onboarding_for_capture() -> None:
    import sqlite3

    db_path = ROOT / "backend" / "bebcare.db"
    if not db_path.exists():
        return
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE users SET onboarding_completed_at = NULL WHERE username = ?",
            (DOCS_DEMO_USERNAME,),
        )
        conn.commit()
    finally:
        conn.close()


def prepare_auth_storage(page: Page, token: str, *, skip_onboarding: bool) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.evaluate("(t) => localStorage.setItem('access_token', t)", token)
    if skip_onboarding:
        page.evaluate(
            """(keys) => {
                localStorage.setItem(keys.skip, '1');
                localStorage.setItem(keys.checklist, '0');
            }""",
            {"skip": SKIP_KEY, "checklist": CHECKLIST_OPEN_KEY},
        )
    else:
        page.evaluate(
            """(keys) => {
                localStorage.removeItem(keys.skip);
                localStorage.setItem(keys.checklist, '1');
            }""",
            {"skip": SKIP_KEY, "checklist": CHECKLIST_OPEN_KEY},
        )


def dismiss_help_overlays(page: Page) -> None:
    skip = page.get_by_role("button", name="Skip for now")
    if skip.count() > 0:
        skip.first.click()
        time.sleep(0.3)
    page.evaluate(
        """() => {
            document.querySelectorAll('[data-help-overlay]').forEach((el) => el.remove());
            document.querySelectorAll('[aria-live="polite"] .pointer-events-auto').forEach((el) => el.remove());
        }"""
    )


def capture(
    page: Page,
    name: str,
    path: str,
    *,
    authed: bool,
    token: str,
    show_onboarding: bool = False,
) -> None:
    if authed:
        prepare_auth_storage(page, token, skip_onboarding=not show_onboarding)
    else:
        page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        page.evaluate("() => localStorage.removeItem('access_token')")

    page.goto(f"{BASE}{path}", wait_until="networkidle")
    time.sleep(1.5)

    if authed and not show_onboarding:
        dismiss_help_overlays(page)
        time.sleep(0.5)

    page.screenshot(path=str(OUT / f"{name}.png"))
    print(f"captured {name}.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Seeding docs-demo sandbox…")
    seed_sandbox()

    token = login_token()

    pages: list[tuple[str, str, bool]] = [
        ("landing", "/", False),
        ("login", "/login", False),
        ("signup", "/signup", False),
        ("studio", "/studio", True),
        ("brand", "/brand", True),
        ("products", "/products", True),
        ("visual-styles", "/visual-styles", True),
        ("automations", "/automations", True),
        ("review", "/review", True),
        ("calendar", "/calendar", True),
        ("buffer-accounts", "/buffer-accounts", True),
        ("account", "/account", True),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        reset_onboarding_for_capture()
        capture(page, "onboarding-wizard", "/studio", authed=True, token=token, show_onboarding=True)
        mark_onboarding_complete(token)

        for name, path, authed in pages:
            capture(page, name, path, authed=authed, token=token)

        browser.close()

    manifest = [name for name, _, _ in pages] + ["onboarding-wizard"]
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
