# Higgsfield prompts — PulseForge landing page

The homepage uses **CSS motion** for the hero plus these optional raster assets in `frontend/public/landing/`.

## 1. Hero — Studio + phone preview

**Aspect:** 16:9  
**Export target:** 1024×576 (do not upscale beyond ~1024px width — source is often 1024px)

```
Professional SaaS hero visual for a social media content platform called PulseForge. 
A modern smartphone in the center showing a polished Instagram feed post: soft nursery product photo, 
clean caption preview, like and comment icons. To the right, a minimal dark charcoal UI panel 
suggesting a content studio dashboard with subtle orange accent lines. 
Warm off-white environment, soft shadows, no readable text, no watermarks, 
high-end B2B marketing photography, photorealistic, shallow depth of field.
```

**Negative prompt:** purple gradient, neon, cluttered UI, stock photo smile, illegible text, watermark, logo soup

---

## 2. Workflow section background

**Aspect:** 16:9  
**Export target:** 1920×1080 (abstract — tolerates mild upscale)

```
Abstract warm background for website section divider. 
Soft gradient cream to pale peach, faint geometric curves suggesting flow and automation, 
minimal copper-orange light accents, no text, no people, clean modern SaaS aesthetic, 16:9.
```

---

## Optimized file placement

After export from Higgsfield, run optimization (or ask the agent to process):

| Asset | WebP (primary) | Fallback | Display size | Typical size |
|-------|----------------|----------|--------------|--------------|
| Hero | `hero.webp` 1024×576 | `hero.jpg` | Bento showcase card | ~15–25 KB WebP |
| Workflow | `workflow.webp` 1920×1080 | `workflow.png` 1280×720 | Testimonial section bg | ~17 KB WebP |

**Rules:**
- Serve WebP first via `<picture>` (`LandingPicture` component).
- Hero: no width upscale past 1024px (keeps sharpness).
- Workflow PNG: palette-quantized fallback for older browsers (~150–200 KB).
- Remove legacy bloated `hero.png` if present (>500 KB).

Hard-refresh after replacing files: `Ctrl+Shift+R`.

---

## Optional prompts (3 & 4)

See prior versions for testimonial desk shot and before/after split — not required for current layout.
