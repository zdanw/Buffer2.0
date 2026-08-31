"""Generate static HTML docs, sitemap.xml, and llms.txt for crawlers and LLMs."""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT_HTML = ROOT / "frontend" / "public" / "docs" / "html"
PUBLIC = ROOT / "frontend" / "public"
SITE_URL = "https://pulseforge.app"  # override via deployment env in CI if needed

ARTICLE_SLUGS = [
    "getting-started/quick-start",
    "getting-started/onboarding",
    "guides/brand-kits",
    "guides/products",
    "guides/visual-styles",
    "guides/studio",
    "guides/automations",
    "guides/review",
    "guides/calendar",
    "guides/buffer",
    "guides/image-models",
    "guides/billing",
]

SPA_ARTICLE_IDS = [
    "quick-start",
    "onboarding",
    "brand-kits",
    "products",
    "visual-styles",
    "studio",
    "automations",
    "review",
    "calendar",
    "buffer",
    "image-models",
    "billing",
]


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    in_list = False
    for line in lines:
        if line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
            continue
        if line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
            continue
        if line.startswith("### "):
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
            continue
        if line.startswith("!["):
            m = re.match(r"!\[(.*?)\]\((.*?)\)", line)
            if m:
                alt, src = m.group(1), m.group(2)
                if src.startswith("../frontend/public/"):
                    src = src.replace("../frontend/public", "")
                out.append(f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt)}" loading="lazy" /><figcaption>{html.escape(alt)}</figcaption></figure>')
            continue
        if line.startswith("| "):
            continue
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(line[2:])}</li>")
            continue
        if in_list and not line.strip():
            out.append("</ul>")
            in_list = False
        if re.match(r"^\d+\. ", line):
            text = re.sub(r"^\d+\. ", "", line)
            out.append(f"<p><strong>{html.escape(text.split(' — ')[0] if ' — ' in text else text)}</strong></p>")
            continue
        if line.strip():
            out.append(f"<p>{html.escape(line)}</p>")
        elif in_list:
            out.append("</ul>")
            in_list = False
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def wrap_page(title: str, description: str, body: str, canonical: str, json_ld: dict | None = None) -> str:
    ld = ""
    if json_ld:
        ld = f'<script type="application/ld+json">{json.dumps(json_ld)}</script>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(title)} | PulseForge</title>
  <meta name="description" content="{html.escape(description)}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{html.escape(canonical)}" />
  <meta property="og:title" content="{html.escape(title)} | PulseForge" />
  <meta property="og:description" content="{html.escape(description)}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{html.escape(canonical)}" />
  {ld}
</head>
<body>
  <header>
    <nav>
      <a href="{SITE_URL}/">PulseForge</a> ·
      <a href="{SITE_URL}/docs">Help Center</a> ·
      <a href="{SITE_URL}/docs/faq">FAQ</a> ·
      <a href="{SITE_URL}/signup">Sign up</a>
    </nav>
  </header>
  <main>
    {body}
    <p><a href="{SITE_URL}/docs">← All guides</a></p>
  </main>
</body>
</html>
"""


def main() -> None:
    OUT_HTML.mkdir(parents=True, exist_ok=True)
    urls: list[str] = [f"{SITE_URL}/", f"{SITE_URL}/docs", f"{SITE_URL}/docs/faq"]

    for slug in SPA_ARTICLE_IDS:
        urls.append(f"{SITE_URL}/docs/{slug}")

    for rel in ARTICLE_SLUGS:
        md_path = DOCS / f"{rel}.md"
        if not md_path.exists():
            continue
        md = md_path.read_text(encoding="utf-8")
        title_line = next((l[2:] for l in md.splitlines() if l.startswith("# ")), rel)
        desc = next((l for l in md.splitlines() if l.strip() and not l.startswith("#") and not l.startswith("!")), title_line)
        slug_name = rel.replace("/", "-")
        canonical = f"{SITE_URL}/docs/html/{slug_name}.html"
        urls.append(canonical)
        body = md_to_html(md)
        page = wrap_page(title_line, desc[:300], body, canonical, {
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "headline": title_line,
            "description": desc[:300],
            "url": canonical,
        })
        (OUT_HTML / f"{slug_name}.html").write_text(page, encoding="utf-8")
        print(f"wrote html/{slug_name}.html")

    faq_md = (DOCS / "faq.md").read_text(encoding="utf-8")
    faq_body = md_to_html(faq_md)
    faq_canonical = f"{SITE_URL}/docs/html/faq.html"
    urls.append(faq_canonical)
    (OUT_HTML / "faq.html").write_text(
        wrap_page("FAQ", "PulseForge frequently asked questions", faq_body, faq_canonical, {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "name": "PulseForge FAQ",
        }),
        encoding="utf-8",
    )

    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>']
    sitemap.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    today = date.today().isoformat()
    for url in urls:
        sitemap.append("  <url>")
        sitemap.append(f"    <loc>{html.escape(url)}</loc>")
        sitemap.append(f"    <lastmod>{today}</lastmod>")
        sitemap.append("  </url>")
    sitemap.append("</urlset>")
    (PUBLIC / "sitemap.xml").write_text("\n".join(sitemap), encoding="utf-8")

    robots = f"""User-agent: *
Allow: /
Allow: /docs
Allow: /docs/
Allow: /docs/html/
Allow: /login
Allow: /signup
Disallow: /studio
Disallow: /brand
Disallow: /products
Disallow: /automations
Disallow: /review
Disallow: /calendar
Disallow: /help
Disallow: /account

Sitemap: {SITE_URL}/sitemap.xml
"""
    (PUBLIC / "robots.txt").write_text(robots, encoding="utf-8")

    llms = f"""# PulseForge

> Social content, forged at scale — multi-brand AI social media automation.

## Documentation (preferred for LLM ingestion)

- Help index (SPA): {SITE_URL}/docs
- FAQ (SPA): {SITE_URL}/docs/faq
- Static HTML mirror: {SITE_URL}/docs/html/
- Repository markdown: docs/README.md

## Guides

"""
    for article_id in SPA_ARTICLE_IDS:
        llms += f"- {SITE_URL}/docs/{article_id}\n"
    for rel in ARTICLE_SLUGS:
        slug_name = rel.replace("/", "-")
        llms += f"- {SITE_URL}/docs/html/{slug_name}.html\n"
    llms += f"\n## FAQ\n\n- {SITE_URL}/docs/faq\n- {SITE_URL}/docs/html/faq.html\n"

    (PUBLIC / "llms.txt").write_text(llms, encoding="utf-8")
    print("wrote sitemap.xml, robots.txt, llms.txt")


if __name__ == "__main__":
    main()
