# Automations

![Automations](../frontend/public/docs/screenshots/automations.png)

Schedule recurring content generation with CRON expressions.

## Task modes

| Mode | On each run |
|------|-------------|
| **Auto publish** | Generate → publish to Buffer |
| **Manual publish** | Generate → save drafts to Review |

## Key fields

- **Products** — one or many; each run covers selected products in order
- **Platforms** — required for auto mode
- **Images / copy per run** — how many variants to generate
- **Scene reference & vision prompt** — same options as Studio
- **Email notification** — optional alert on publish

**CRON format:** `minute hour day month weekday` — e.g. `0 9 * * *` = daily at 09:00.
