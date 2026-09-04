# Higgsfield prompts — Postence brand assets

Target audience: D2C content ops, founder-led marketers, lean agency pods.  
Tone: **modern, hip, energetic** — editorial tech, not generic AI startup.

Palette: midnight `#0B0D14`, warm paper `#F5F1E8`, vermilion `#FF4D3D`, signal blue `#406BFF`, moss `#91B89A`.

---

## A. Icon mark (monogram only)

**Aspect:** 1:1  
**Export:** 1024×1024 PNG with transparent background (or solid midnight tile)  
**Use:** Trace to SVG → favicon, sidebar, app icon

### Prompt

```
Premium app icon monogram for "Postence", an AI social presence platform for modern brand teams. 
Design ONLY the symbol — no wordmark text. 
Concept: a single continuous open-loop letter P formed by one confident rounded stroke, 
like a signal path that never fully closes — supervised, always-on presence. 
Two small nodes on the path: signal blue dot on the vertical stem, electric vermilion dot 
at the open end of the loop. 
Background: deep midnight ink rounded square with soft 18% corner radius. 
Stroke color: warm paper white, 2.5px equivalent weight, rounded caps. 
Style: modern, hip, energetic, Swiss minimalism, Linear/Stripe/Vercel quality, 
flat vector aesthetic, crisp edges, high contrast, legible at 32px. 
Feels creative-studio meets SaaS — not playful mascot, not corporate clipart.
```

### Negative prompt

```
letter text spelling Postence, full wordmark, purple gradient, neon glow, 3D render, 
glassmorphism blob, robot face, sparkle stars, magic wand, chat bubble, paper plane, 
generic filled block P, bevel, emboss, drop shadow halo, busy details, watermark, 
low contrast, blurry, pixelated, crypto coin, Instagram gradient clone
```

### Variations to try

Add one line to the main prompt:

- **Energetic:** `Slightly dynamic asymmetry — loop leans forward as if in motion.`
- **Hip/editorial:** `Ultra-minimal — 90% negative space, stroke-only, no fill shapes.`
- **D2C warmth:** `Micro warm paper grain on midnight tile, still flat and vector-clean.`

---

## B. Wordmark (text only)

**Aspect:** 16:9 or 3:1 wide  
**Export:** 2048×512 PNG, transparent background  
**Use:** Trace to SVG or use as reference for `postence-wordmark.svg`

### Prompt

```
Professional typographic wordmark logo: the single word "Postence" only. 
Custom geometric sans-serif logotype, medium-semibold weight, tight but airy kerning, 
confident and modern — appeals to hip D2C content teams and founder marketers. 
Color: midnight ink letterforms on transparent background. 
One subtle brand detail: a short vertical vermilion accent bar on the terminal of the 
final letter "e" — like a publishing signal or cursor, not an exclamation. 
Optional: extremely faint rounded pill outline behind the word at 8% opacity (barely visible). 
No icon, no tagline, no slogan, no mockup scene, no 3D, no effects. 
Flat vector logo sheet, centered, generous padding, Behance-quality brand identity presentation.
```

### Negative prompt

```
split word Post ence, double letter t, misspelling Posttence, script font, serif font, 
handwritten, graffiti, gradient text, purple, neon, glow, shadow, 3D extrusion, 
icon beside text, tagline, watermark, busy background, mockup on building, 
generic Arial, comic sans, all caps POSTENCE, extra punctuation
```

### Inverse version (for dark sidebar)

Same prompt, replace colors with:

```
Letterforms: warm paper white #F5F1E8. Vermilion accent unchanged. Transparent background.
```

---

## C. Lockup (icon + wordmark horizontal)

**Aspect:** 3:1  
**Export:** 1536×512 PNG, transparent background

### Prompt

```
Horizontal logo lockup for Postence. Left: open-loop P monogram icon on midnight rounded square. 
Right: "Postence" wordmark in modern geometric sans, midnight ink, vermilion accent on final e. 
Balanced spacing, optically centered, startup brand guidelines sheet, flat vector, 
modern hip energetic editorial tech aesthetic, white or transparent background, no mockup scene.
```

### Negative prompt

Same as A + B combined.

---

## After generation

1. Pick the cleanest 1:1 icon and widest wordmark.
2. Trace to SVG (Figma, Illustrator, or vectorize) — do not ship blurry PNG in nav.
3. Replace:
   - `frontend/public/postence-favicon.svg`
   - `frontend/public/postence-wordmark.svg`
   - `frontend/public/postence-wordmark-inverse.svg`
   - `frontend/src/components/brand/postenceMark.svg.tsx`

Reference concepts: `frontend/public/brand/postence-icon-concept.png`, `postence-wordmark-concept.png`

---

## Landing imagery (optional)

See sections 1–3 below for hero/workflow raster assets.

## 1. Hero — energetic product story (primary)

**Aspect:** 16:9  
**Export target:** 1024×576  
**Use:** Bento showcase card (`LandingPicture` asset `hero`)

```
Cinematic SaaS hero for Postence, an AI social presence platform for modern brand teams. 
A confident young content operator at a warm minimalist desk, candid mid-laugh energy, 
natural window light, cream and charcoal interior. In the foreground, a sleek smartphone 
showing a vibrant Instagram Reel frame with bold product visuals — not a generic office stock photo. 
Floating subtly around the phone: three small platform cues (Instagram gradient ring, TikTok note, 
Facebook blue accent) as soft glass chips, not logos with text. 
Background hints at an editorial studio: mood board, coffee, laptop with blurred dark UI. 
Color accents: vermilion red and signal blue light leaks, warm paper tones, midnight shadows. 
Feels hip, fast, creative, premium D2C energy — Glossier meets Linear meets content studio. 
Photorealistic, shallow depth of field, motion-implied composition, golden-hour warmth, 
no purple AI gradient, no robots, no sparkles, no watermarks, no readable UI text.
```

**Negative prompt:**
```
purple gradient, neon cyberpunk, robot, AI brain, magic wand, sparkles, clipart icons, 
corporate stock handshake, boring gray office, oversaturated HDR, watermark, 
illegible text, logo soup, 3D blob, crypto aesthetic, uncanny face, stiff pose
```

---

## 2. Hero alternate — pure product (no people)

**Aspect:** 16:9  
**Export target:** 1024×576  
**Use:** Landing hero right column if replacing phone mock video still

```
Modern editorial tech hero visual for Postence social presence software. 
Three smartphones arranged in a dynamic staggered composition, each showing a different 
native social format: Instagram carousel, TikTok vertical reel, Facebook feed card — 
same brand story adapted per screen. Devices float above warm paper surface with soft shadow. 
Subtle signal lines connect the screens like a living network (vermilion and blue accents). 
Midnight ink background fading to cream, high-end product photography, crisp, energetic, 
minimal, Swiss layout, no people, no readable text, no watermarks.
```

**Negative prompt:** same as above

---

## 3. Workflow section background

**Aspect:** 16:9  
**Export target:** 1920×1080  
**Use:** Testimonial / principle section (`workflow`)

```
Abstract energetic background for a modern editorial SaaS website section. 
Warm paper base with flowing signal lines moving left to right — one idea splitting into 
multiple channels — vermilion and signal blue strokes on charcoal ink, moss green completion dots. 
Feels like motion design still frame: hip, confident, fast, not chaotic. 
Minimal grain, soft vignette, no text, no people, 16:9.
```

**Negative prompt:**
```
purple gradient, galaxy, blockchain, matrix rain, busy pattern, low-res, text, watermark
```

---

## 4. Brand icon concept (optional reference)

**Aspect:** 1:1  
**Export target:** 1024×1024 (trace to SVG afterward)

```
App icon for Postence. Minimal open-loop letter P formed by one continuous white stroke 
on midnight ink rounded square. Small blue node on stem, vermilion node at loop opening — 
living signal concept. Flat vector aesthetic, premium B2B, Stripe-quality, no 3D, no emoji, 
no purple, no sparkle.
```

---

## File placement

| Asset | WebP | Fallback | Display |
|-------|------|----------|---------|
| Hero | `hero.webp` 1024×576 | `hero.jpg` | Bento / showcase |
| Workflow | `workflow.webp` 1920×1080 | `workflow.png` | Section bg |

Hard-refresh after replacing: `Ctrl+Shift+R`.
