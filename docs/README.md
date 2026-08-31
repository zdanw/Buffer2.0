# PulseForge User Documentation

Welcome to the PulseForge documentation. These guides are for **operators, marketers, and content teams** using the platform day to day.

> **In-app Help Center:** After logging in, open **Settings → Help** in the sidebar for the same content with live screenshots and search.

> **Public docs (indexable):** [/docs](/docs) — no login required. Crawlers and LLMs can also use [/llms.txt](/llms.txt), [/sitemap.xml](/sitemap.xml), and static HTML at `/docs/html/`.

## Quick links

| Guide | Description |
|-------|-------------|
| [Quick start](getting-started/quick-start.md) | First post in ~5 minutes |
| [Onboarding](getting-started/onboarding.md) | Wizard & checklist |
| [FAQ](faq.md) | Common questions |
| [Troubleshooting](troubleshooting.md) | Generation failures, CDN, API connection |

## Full guide index

### Getting started
- [Quick start](getting-started/quick-start.md)
- [Onboarding wizard](getting-started/onboarding.md)

### Content setup
- [Brand kits](guides/brand-kits.md)
- [Products & reference images](guides/products.md)
- [Visual styles](guides/visual-styles.md)

### Create & publish
- [Studio](guides/studio.md)
- [Automations](guides/automations.md)
- [Review queue](guides/review.md)
- [Publish calendar](guides/calendar.md)

### Integrations
- [Buffer setup](guides/buffer.md)
- [Image models & credits](guides/image-models.md)
- [Account & billing](guides/billing.md)

## Screenshots

UI screenshots live in `frontend/public/docs/screenshots/`. Regenerate after major UI changes:

```powershell
# 1. Seed sandbox data (docs-demo user with Luma Home catalog)
.\backend\.venv\Scripts\python.exe scripts\seed_docs_sandbox.py

# 2. Capture screenshots (auto-seeds, logs in as docs-demo, dismisses onboarding overlays)
.\backend\.venv\Scripts\python.exe scripts\capture_help_screenshots.py
```

Requires local frontend (`:5174`) and backend (`:8888`) running.

**Sandbox user:** `docs-demo` / `DocsDemo2026!` — isolated demo brand **Luma Home** with English-only sample products. Never uses your admin test data.

## Related docs

- [项目说明.md](../项目说明.md) — Chinese operator & deployment reference
- [README.md](../README.md) — Developer setup and architecture
