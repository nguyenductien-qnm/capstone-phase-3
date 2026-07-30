# Design System: TechX Astro

## 1. Visual Theme & Atmosphere
A restrained, cockpit-dense interface with fluid spring-physics motion. The atmosphere is professional, technical, and slightly mysterious — like a late-night observatory control room.

## 2. Color Palette & Roles
- **Deep Space** (#0a0a0f) — Primary background surface
- **Nebula Slate** (#111119) — Card and container fill
- **Starlight White** (#f8fafc) — Primary text, maximum contrast
- **Lunar Dust** (#94a3b8) — Secondary text, descriptions, metadata
- **Midnight Border** (#2a2a40) — Card borders, 1px structural lines
- **Electric Indigo** (#6366f1) — Single accent for CTAs, active states, focus rings

## 3. Typography Rules
- **Display:** Geist (or fallback sans) — Track-tight, controlled scale, weight-driven hierarchy
- **Body:** Geist (or fallback sans) — Relaxed leading, 65ch max-width, neutral secondary color
- **Mono:** JetBrains Mono — For code, metadata, timestamps, high-density numbers
- **Banned:** Inter, generic system fonts for premium contexts. Serif fonts banned in dashboards.

## 4. Component Stylings
* **Buttons:** Flat, no outer glow. Tactile -1px translate on active. Accent fill for primary, ghost/outline for secondary.
* **Cards:** Generously rounded corners (0.75rem). No diffused whisper shadow for high-density layouts; replace with border-top dividers or clean borders.
* **Inputs:** Label above, error below. Focus ring in accent color. No floating labels.
* **Loaders:** Skeletal shimmer matching exact layout dimensions. No circular spinners.
* **Empty States:** Composed, illustrated compositions — not just "No data" text.

## 5. Layout Principles
Grid-first responsive architecture. Asymmetric splits for Hero sections.
Strict single-column collapse below 768px. Max-width containment (1400px centered).
No flexbox percentage math. Generous internal padding (py-32).
AIDA structure strictly enforced.

## 6. Motion & Interaction
Spring physics for all interactive elements. Staggered cascade reveals.
Perpetual micro-loops on active dashboard components. Hardware-accelerated transforms only.
Advanced GSAP-style motion for scroll pinning and text reveals.

## 7. Anti-Patterns (Banned)
- No emojis anywhere
- No Inter font
- No generic serif fonts (Times New Roman, Georgia, Garamond)
- No pure black (#000000)
- No neon glows or AI purple gradients
- No 3-column equal grids (use dense bento instead)
- No AI copywriting clichés ("Elevate", "Seamless", "Unleash")
- No generic placeholder names
- No fake round numbers (99.99%)
