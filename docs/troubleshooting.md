# Troubleshooting

## Cannot reach PulseForge API

**Symptom:** Yellow banner — "Cannot reach PulseForge API". Brands and products don't load.

**Fix (local dev):**

```powershell
.\scripts\backend.ps1 start
```

Default API port is `8888`. Refresh the page after the health check passes.

**Fix (production):** Verify your deployment URL, reverse proxy, and that the API service is running.

---

## Generation returns an error

1. Confirm the product has **at least one reference image**
2. Check **image credits** in the top bar
3. Open browser dev tools → Network for API error details
4. Under **Image Models**, test your provider connection

---

## Publish fails from Review

1. Select **one image** and **one copy variant**
2. Choose at least one **platform**
3. Re-upload images marked **Not on CDN**
4. Confirm the brand has a **Buffer account** bound

---

## Automations don't run

1. Task is **enabled** (toggle on)
2. CRON expression is valid (5 fields)
3. At least one **product** and (for auto mode) **platform** selected
4. On Hugging Face Spaces, note concurrency limits — heavy schedules may queue

---

## Buffer connection fails

1. Token copied completely (no extra spaces)
2. Token has publish permissions for connected profiles
3. One token per brand — re-bind in Brand kits after changing tokens

See [Buffer guide](guides/buffer.md).

---

## Regenerate Help Center screenshots

```powershell
# Start backend + frontend first
.\backend\.venv\Scripts\python.exe scripts\capture_help_screenshots.py
```

Output: `frontend/public/docs/screenshots/*.png`
