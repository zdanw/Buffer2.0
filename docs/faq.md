# Frequently asked questions

## What is PulseForge?

PulseForge is a multi-brand social content platform. You define brand voice and product assets, then AI generates platform-specific copy and images. Content can auto-publish via Buffer or go through a Review queue first.

## What is the difference between auto and manual publish?

| Mode | Behavior |
|------|----------|
| **Auto publish** | CRON task generates and sends posts to Buffer — no human step |
| **Manual publish** | CRON task generates drafts into **Review** — you pick image + copy, then publish |

Start with manual until output quality is consistent.

## Why do I need a Buffer token?

PulseForge does not post directly to Instagram or Facebook. [Buffer](https://buffer.com) handles scheduling and delivery. Each **brand kit** binds to **one** Buffer API token.

See [Buffer setup guide](guides/buffer.md).

## How do image credits work?

- Each image generation uses **one platform credit** by default
- Signup and onboarding include free credits
- Subscribe on the **Account** page for monthly packs
- Add your own API key under **Image Models** (BYOK) to bypass platform credits

## Why must images be on CDN before publishing?

Generated images may start on temporary URLs. Buffer needs stable public links. PulseForge uploads to GitHub CDN. In **Review**, images marked **Not on CDN** must be re-uploaded before publish.

## Why did generation fail?

Common causes:

1. **No product reference images** — add at least one in Products
2. **No credits left** — check the top bar or Account page
3. **API unreachable** — yellow banner: start the backend or check your deployment
4. **Image provider misconfigured** — test connection under Image Models

## How do I write a CRON expression?

Five fields: `minute hour day month weekday`

| Example | Meaning |
|---------|---------|
| `0 9 * * *` | Every day at 09:00 |
| `30 14 * * 1` | Mondays at 14:30 |
| `0 */6 * * *` | Every 6 hours |

The Automations form validates your expression.

## What is the Generic brand?

A fallback when you don't need brand-specific rules. Products without a brand kit still generate with neutral voice. Create a named brand for consistent tone and Buffer binding.

## How are logos handled in generated images?

Per brand kit:

| Setting | Effect |
|---------|--------|
| **Preserve** | Keep logos visible on packaging in reference photos |
| **Omit** | Generate without logos |
| **Composite** | Add your brand logo on export |

## What language is content generated in?

- **Social copy** — English by default, tuned per platform
- **Image prompts** — Chinese internally (for the image model)
- **App UI** — English or 中文 via the sidebar language toggle

## Where is the full user guide?

Log in → **Settings → Help** in the sidebar, or read the [docs index](README.md).
