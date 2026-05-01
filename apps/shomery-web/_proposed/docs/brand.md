# Shomery — Brand Detail

Extended brand guidance. CLAUDE.md has the essentials; this file has the full guidance for designers and copywriters.

## Color palette

| Role | Hex | Use |
|---|---|---|
| Accent | `#10B981` | Buttons, links, brand mark, motif edge |
| Accent hover | `#059669` | Button hover/active states |
| Tint | `#ECFDF5` | Subtle callout backgrounds, selected rows, scope banners |
| Ink | `#111111` | Body text, headings on light bg |
| Soft text | `#6B7280` | Secondary text, captions |
| Paper | `#FFFFFF` | Default background |
| Tertiary bg | `#F9FAFB` | Settings page canvas, iOS-style off-white |
| Warning (priority) | `#F59E0B` | High-priority badges, "needs attention" semantics |
| Border (default) | `rgba(0,0,0,0.1)` 0.5px | Card borders, dividers |
| Border (emphasis) | `rgba(0,0,0,0.2)` 0.5px | Active card borders, focused inputs |

## Channel-icon colors

When showing third-party messaging brands inside Shomery, use their actual brand color — not Shomery's accent. These are third-party identities, distinct from Shomery's own brand.

| Channel | Color |
|---|---|
| KakaoTalk | `#FEE500` |
| WhatsApp | `#25D366` |
| Telegram | `#0088CC` |
| Email | Emerald tint `#ECFDF5` (Shomery's neutral-info) |
| SMS | Neutral gray |

WhatsApp green and Shomery's Emerald are different hues — one is teal-leaning, one is yellow-leaning — so they stay distinguishable next to each other in the Settings notifications list.

## Typography

Inter only. Two weights:

- **Regular (400)** — body text, captions, paragraphs
- **Bold (700)** — headings, emphasis, button labels

Don't use Light, Thin, Medium, ExtraBold, or Italic. Don't introduce a second typeface.

Sizes:

| Element | Size |
|---|---|
| Hero headline | 22–24px Bold |
| Section heading | 16–18px Bold |
| Body (UI) | 13–14px Regular |
| Body (long-form) | 14–16px Regular |
| Caption / metadata | 11–12px Regular |

## Voice

Confident, calm, plain-spoken. One idea per sentence.

**Banned words and phrases.** Replace claims with specifics.

- *synergy, leverage, paradigm, robust, seamless, frictionless*
- *AI-powered, AI-driven, intelligent, smart*
- *solutions* (you sell a product, not solutions)
- *enterprise-grade* (the security team decides that)
- *revolutionary, game-changing, disruptive*
- *cutting-edge, next-generation, world-class*

Bad: *"Our AI-powered platform leverages cutting-edge ML to deliver world-class email intelligence."*

Better: *"Shomery reads every email, summarizes it in 200 words, and saves it to your Drive."*

Tone shifts by audience but voice stays consistent:

| Audience | Tone shift |
|---|---|
| SMB owner | Confident, slightly direct. Answers fast. |
| Security buyer | More precise. Use specific terms (DPA, SOC 2, GDPR Article 44). |
| Existing customer | Warm, helpful, no selling. |

## Motif

Accent edge — 3px `#10B981` left border on:

- Email summary cards (the rendered .md)
- Hero callouts (e.g., "Your data stays in your Drive")
- Slide-deck templates (when reports are generated)

**Do not** use the motif on:

- Empty states (would be too prominent)
- Settings rows (visual noise)
- Sidebar nav rows (the active-row highlight does that job already)

## Mode

Light mode only in v1. Pure white background. No dark UI surfaces. Dark mode is a v2 consideration.

## Logo and brand mark

The brand mark is a 14×14px Emerald square with subtly rounded corners (`border-radius: 3px`). The wordmark is "Shomery" in Inter Regular at 14–16px ink.

**Lockup:** brand mark + 8px gap + wordmark, both vertically centered.

**Minimum size:** 12px tall. Below that, use the mark alone.

**Backgrounds:** light only. White, paper, or pale tint. Never on colored or dark backgrounds in v1.

## Anti-patterns to avoid

- Multiple accent colors. Emerald is the only accent. Adding "secondary accent purple for highlights" dilutes brand recognition.
- Stock photos of people in headsets. Use real product screenshots or no people at all.
- Motion or bounce animation. Animations only where they explain motion (a card sliding in, a list item collapsing).
- Drop shadows beyond the 0.5px border tokens. Shadow-heavy UI looks dated and conflicts with the Apple-clean direction.
- Bold mid-sentence in copy. Bold is for headings and labels only.
