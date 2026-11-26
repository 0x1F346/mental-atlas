# Mental Atlas: design brief for the "living tissue" look

Written 2026-11-26 as a handoff from a design session. Nothing here has been
implemented, and nothing in the repository other than this folder was changed.

## What is in this folder

- `atlas.html`: the Atlas with the evidence panel open. Static reference; open it in a browser.
- `source.html`: the Sources page with upload, processing status and a transcript.
- `DESIGN_BRIEF.md`: this file.

Both HTML files are single-file mockups with inline styles. They are a visual
reference, not code to copy in: every name, quote, date and count in them is
invented, and they were not checked in a browser before handoff, so treat exact
pixel positions as approximate.

## This reverses settled decisions

The mockup draws the map the way the plan originally described it: six fixed
regions with drawn borders, a landmark at its saved position, an icon per
concept type, outlines for stated / observed / hypothesis, and fading with age.
D-018 replaced that with a WebGL force-directed graph, and D-019, D-021 and
D-022 refined it (flat, people as stars, gradient ribbons).

Implementing this design supersedes D-018, D-019, D-021 and D-022. That is the
owner's call. Confirm it with the owner at the start of the session and log a
new decision before changing the renderer.

## How it maps onto the code

Read from `web/src/map/types.ts`, `web/src/map/appearance.ts`, `docs/DECISIONS.md`
and `docs/PROGRESS.md` only. Check everything else against the code.

- **Renderer.** A new SVG/HTML renderer behind the existing `MapRenderer`
  interface (`MapRendererProps`), replacing `ForceGraphRenderer.tsx`. D-018 says
  the previous `SvgMapRenderer.tsx` was replaced; it is in git history and may be
  a quicker base than starting again. The stored region polygons, which D-018
  left unused, are what the regions are drawn from.
- **Callers stay as they are.** `/map`, `/nodes/{id}`, the evidence endpoints,
  filters and backend layout should need no change. If one seems to, stop and ask.
- **Evidence panel.** `EvidencePanel.tsx` is restyled and reordered, not rebuilt.
- **Sources.** `SourcesPage.tsx`, `SourcePage.tsx`, `UploadForm.tsx` and
  `SpeakerCheck.tsx` are restyled. The mockup merges the list and one open
  source into a two-column page; keeping them as separate routes is fine.
- **Tests.** Landmarks become real `<button>` elements, so the visually hidden
  mirror list from D-018 may no longer be needed. Keep `map.test.tsx` and the
  Playwright flow passing, including "every hypothesis shows its label".

## Visual system

Colours:

| Role | Value |
|---|---|
| Ground | `#041318` |
| Top bar | `#051A1F` |
| Panel | `#071D22` |
| Card (quotes, player) | `#0E2B31` |
| Text | `#F2F7F3`, secondary `#B7CCC8`, tertiary `#A9C2BE` |
| Primary accent (spore green) | `#8CEBB0`, with `#06231F` text on it |
| Hypothesis notice (pollen) | `#F2C36B` border, `#F6DFA6` text |
| Contradicts (coral) | `#FFB3A1` |

Concept type colours used in the mockup: person `#FF9B85`, situation `#F2C36B`,
event `#6FD6E8`, feeling `#B9A2FF`, belief `#8CEBB0`, behaviour `#F08FC0`.
Speaker colours: me `#F2C36B`, therapist `#6FD6E8`, other `#B9A2FF`.

Type: Newsreader (headings, quotes, region names in italic) and Figtree (all
UI). The mockup loads them from Google Fonts. For a private app, self-hosting
them avoids a request to a third party on every load; that adds a dependency or
font files, so ask the owner.

Atmosphere: three soft radial light pools on the ground, a faint mycelial line
layer, a low-opacity grain overlay, glass bars (`rgba(5,26,31,.78)` with a
14px blur) for the filters and legend. Quote text always sits on a solid card.

## Landmark encoding

| Meaning | Drawn as |
|---|---|
| Concept type | Icon inside the orb, plus the type colour |
| Evidence | Diameter, 28px to 66px in the mockup |
| Time since last mention | Orb opacity, 1.0 down to 0.4. The label does not fade below `#93AEAB`, so it stays readable |
| Stated | 2px solid outline |
| Observed | Solid outline plus a second ring 4px out |
| Hypothesis | 1.5px dashed outline and a fainter fill |
| Selected | Slow pulsing halo, label in a pill |

Orbs breathe (scale 1 to 1.07 over 7 to 11 seconds). All motion is switched off
under `prefers-reduced-motion`.

Relationships appear only for the selected landmark: a curved, slightly
irregular line with a wide soft glow under a thin bright stroke, and a few
short side branches. A relationship of tension is dashed coral with no glow.

## Evidence panel, top to bottom

1. Type and life area, close button.
2. Name in the serif.
3. Status line in plain language, in a dashed pollen box for a hypothesis:
   "Hypothesis: nobody has said this directly".
4. Four facts: noticed by, times seen, first seen, last seen.
5. Related items, grouped by relationship, as chips with the type icon.
6. Quote cards, newest first: speaker, date, source, a Supports or Contradicts
   tag (icon as well as colour), the quote in the serif at 20px, "Play from
   mm:ss", and "Open in transcript".

## Where the mockup and the real data differ

- **Concept types.** The mockup shows six types with icons. The vocabulary has
  seventeen (`TYPE_LABELS` in `appearance.ts`). The other eleven need icons and
  colours, or a shared fallback. The mockup's filter bar has six chips; the real
  one needs a way to hold seventeen.
- **Noticed by.** The mockup says "No one yet" for a hypothesis. The code has
  `NOTICED_LABELS.ai = 'Inferred'`. Use the code's wording unless the owner
  prefers the mockup's.
- **Life areas.** The six names in the mockup are guesses. Use the seeded ones.
- **Region shapes.** The mockup's blobs are decorative. Use the stored polygons;
  the double membrane line (solid outer, dotted inner) is the part to keep.
- **Label density.** The mockup labels all 29 landmarks. `prominentIds` already
  limits labels; keep that behaviour.
- **Later phases.** The top bar shows Patterns, Timeline and "Ask the atlas" as
  inert "soon" labels. `CLAUDE.md` limits work to V1, so build none of them;
  whether the labels appear at all is the owner's call.

## Not designed

Sign-in page, the speaker check, the test-data upload mode (D-020), error and
empty states, zoomed-out and zoomed-in label levels, and small screens. Carry
the same tokens across and ask if a layout question comes up.

## Suggested order

1. Tokens and fonts in `index.css`, top bar. No behaviour change.
2. Evidence panel restyle.
3. Sources pages restyle.
4. New map renderer, after the owner confirms the decision above.

Each of these is one commit under the repository's usual routine.
