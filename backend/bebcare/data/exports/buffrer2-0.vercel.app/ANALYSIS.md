# Remote assets analysis — buffrer2-0.vercel.app

**Analyzed:** 2026-08-14 (updated after authenticated export)  
**Frontend:** [https://buffrer2-0.vercel.app/assets](https://buffrer2-0.vercel.app/assets)  
**API proxy:** Vercel `api/index.cjs` → `zongsechenai-bebcare-buffer.hf.space`

## Export result (authenticated)

| Metric | Value |
|--------|-------|
| Products exported | **8** |
| Categories | Audio Monitor, Bottle Warmer, Air Purifiers, Wearable Breast Pump, Video Monitor, Night Lights |
| Local import | `python scripts/import_products_export.py` |
| Brand assignment | All linked to **Bebcare** (`brand_id` …002) |

### Product catalog (remote)

| Product | Category | Images (product / scene) |
|---------|----------|--------------------------|
| Bebcare Warm Go Warmer | Bottle Warmer | 4 / 2 |
| Bebcare Flow | Wearable Breast Pump | 4 / 6 |
| Video Baby Monitor | Video Monitor | 19 / 9 |
| Bebcare Air Purifiers | Air Purifiers | 8 / 0 |
| Audio Baby Monitor | Audio Monitor | 22 / 0 |
| Bebcare Lola | Night Lights | 16 / 0 |
| Bebcare Luna | Night Lights | 11 / 0 |
| Bebcare Linda | Night Lights | 15 / 0 |

See `products-summary.json` for counts; full CDN URLs in `products-export.json` (116 images total imported locally).

## Access findings (initial)

| Check | Result |
|-------|--------|
| `/assets` page | Redirects to `/login` (JWT required) |
| `GET /v1/products/` without token | `401 Not authenticated` |
| Authenticated export | **Success** via `scripts/export_remote_assets.py` |

## Local copies created

| File | Contents |
|------|----------|
| `products-export.json` | Placeholder (0 products) until authenticated export runs |
| `export-manifest.json` | Export status + analysis metadata |
| `dimensions-baby-pack-snapshot.json` | Full copy of `dimensions_data.py` (4 baby product types) |
| `../brand_kits/bebcare.json` | Legacy prompt skills → **Bebcare** brand kit |
| `../brand_kits/generic.json` | Neutral **Generic** brand kit |

## Brand migration (hard-coded skills preserved)

Legacy baby/Bebcare behavior is now stored as the **Bebcare** system brand:

- **ID:** `00000000-0000-0000-0000-000000000002`
- **Slug:** `bebcare`
- **Vertical pack:** `baby_family`
- **Includes:** copy/image/vision system prompts, narrative perspectives, writing styles, emoji hints, copy example, fallback selling points, Nunito logo rule

**Generic** brand (`00000000-0000-0000-0000-000000000001`) has neutral prompts and no baby fallbacks.

### Database

Seeded locally via `python scripts/apply_brands_sqlite.py` (or `python scripts/seed_brands.py` after `alembic upgrade head` on startup).

Products should set `brand_id` to Bebcare to retain previous generation behavior.

## Recommended next step

Run the export script with production `ADMIN_PASSWORD`, then:

```bash
python scripts/import_products_export.py  # if we add import script
```

Or manually import `products-export.json` after a successful remote pull.
