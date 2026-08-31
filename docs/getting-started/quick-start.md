# Quick start — your first post in 5 minutes

PulseForge turns product photos and brand rules into platform-ready social posts. This is the shortest path from a blank account to a published (or queued) post.

![Studio](../frontend/public/docs/screenshots/studio.png)

## Before you begin

- A PulseForge account ([sign up](http://localhost:5174/signup) on your deployment)
- At least one product image (packshot or lifestyle photo)
- Optional: a [Buffer](https://buffer.com) account for publishing

## Steps

### 1. Create your account

Sign up with email and password. You receive **trial image credits** to test generation.

### 2. Complete onboarding (or skip)

On first login, a wizard helps you:

- Name a brand and describe its voice, **or** choose **Generic**
- Add one product with at least one image

You can skip and configure everything later in the sidebar.

### 3. Add a product (if you skipped the wizard)

Go to **Products → Add product**:

- Product name and category
- Upload **product images** (clear shots of the item)
- Optionally upload **scene images** (item in a real room or setting)

### 4. Generate in Studio

Open **Studio**:

1. Select your product
2. Choose platforms (Instagram, Facebook, TikTok, …)
3. Click **Generate both** for caption + image
4. Preview in the phone mockup on the right

![Products](../frontend/public/docs/screenshots/products.png)

### 5. Publish or save for review

- **Publish** — sends to Buffer immediately (requires Buffer token bound to your brand)
- **Save to Review** — queues a draft for human approval

### 6. Optional — schedule with Automations

Under **Automations**, create a CRON task:

- **Auto publish** — generate and post on schedule
- **Manual publish** — generate drafts into the **Review** queue

![Automations](../frontend/public/docs/screenshots/automations.png)

## Tips

- Use the **Getting started** checklist (bottom-right) to jump between steps
- Complete brand + product + first generation to earn **bonus free credits**
- Start with **manual** automations until you trust output quality

## Next steps

- [Onboarding wizard details](onboarding.md)
- [Connect Buffer](../guides/buffer.md)
- [FAQ](../faq.md)
