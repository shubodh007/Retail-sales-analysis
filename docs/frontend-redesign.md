# Frontend redesign — Cozy Intelligence

## Design decision

The frontend was redesigned around a simple question: **can a non-technical user understand what the data is saying within 10 seconds?**

The winning direction is **Cozy Intelligence**: warm paper surfaces, soft depth, expressive but semantic color, plain-English page titles, and restrained motion. It avoids both the cold corporate BI look and the neon/cyber AI-dashboard look.

## Palette

| Role | Token | Hex |
|---|---|---|
| Main canvas | Warm Cloud | `#FFF9F2` |
| Secondary surface | Soft Linen | `#F5EFE7` |
| Text | Deep Slate | `#24313A` |
| Secondary text | Slate | `#64727B` |
| Borders | Warm Mist | `#E7E0D8` |
| Current / sales | Dusty Blue | `#5B9FB3` |
| Healthy / growth | Sage | `#7FA58A` |
| Forecast / future | Soft Plum | `#8B6B9E` |
| Action / attention | Terracotta | `#D9785F` |
| Serious anomaly | Coral | `#D95C5C` |
| Discovery / note | Butter | `#E8C66A` |

### Semantic rule

- Blue = what happened / current data
- Plum = what may happen / forecast
- Sage = healthy growth / positive state
- Terracotta = attention / action
- Coral = anomaly / error
- Butter = discovery / explanation

Color is never the only carrier of meaning; icons and text accompany important states.

## Alternatives debated

### A. Dark command-center
Rejected as the primary visual direction. It is attractive for technical users but makes the project feel like an infrastructure console and reduces the friendly/explanatory quality requested.

### B. White SaaS blue dashboard
Rejected. Clear, but generic and visually indistinguishable from common admin templates.

### C. Pastel/cozy dashboard
Rejected in its pure form. Pleasant, but low contrast and too soft for dense analytics.

### Winner: Cozy Intelligence

Warm neutral canvas + muted colorful data accents gives the project personality while keeping charts readable.

## React Bits selections

The implementation uses the ideas that provide useful interaction rather than decoration:

1. **CountUp** — KPI numbers; already vendored in `components/bits/CountUp.tsx`.
2. **BlurText** — one-shot page headline reveal.
3. **AnimatedContent** — lightweight section entrance using the existing Motion dependency.
4. **SpotlightCard** — subtle cursor-aware focus on important cards; deliberately low contrast.
5. **PillNav** — shared active navigation pill with Motion `layoutId`.
6. **ShinyText** — restrained forecast/model emphasis only.
7. **AnimatedList** — pipeline stages in System, where staggered entry communicates sequence.

Rejected for this product: neon borders, liquid chrome, aurora backgrounds, galaxy effects, custom cursors, pixel transitions and aggressive 3D card tilts. They compete with charts and do not improve comprehension.

React Bits currently lists 150 animated components plus application UI blocks; the selected set is intentionally small and semantic rather than decorative. See the official index at https://www.reactbits.dev/get-started/index.

## Ponytail rules applied

The frontend follows the Ponytail ladder:

1. Reuse existing components before adding another abstraction.
2. Reuse installed Motion, ECharts, React Three Fiber and TanStack Query before adding dependencies.
3. Prefer native inputs/selects for simple controls.
4. Keep experiential animation optional and reduced-motion aware.
5. Do not add a component library solely for visual fashion.
6. Keep the 3D horizon isolated/lazy-loaded so the normal analytics experience remains useful without it.

## Page-by-page UX

- **Overview:** answers “How is the business doing?” and adds three plain-English insight cards.
- **Sales:** answers “How are sales behaving?” with readable filters and trend exploration.
- **Products:** answers “What is selling?” and keeps search/sort/drill-down as the core interaction.
- **Markets:** answers “Where is revenue coming from?” and preserves country drill-down.
- **Customers:** answers “Who are the customers?” while keeping RFM methodology visible.
- **Forecast:** answers “What may happen next?” with blue history, plum forecast, confidence band, model explanation and model-comparison evidence.
- **Anomalies:** answers “What looks unusual?” without claiming a statistical flag is a causal explanation.
- **Data Lab:** answers “Can I trust the data?” before exposing downstream analytics.
- **System:** answers “How did this number get here?” with a sequenced pipeline view.

## Accessibility and performance

- Reduced-motion preference is respected by the shared Motion components and chart animation.
- Important state uses color + text/icon rather than color alone.
- Warm-neutral text uses a dark slate anchor for contrast rather than low-contrast pastel body text.
- No new animation engine was introduced.
- Existing ECharts tree-shaking remains intact.
- Existing lazy 3D boundary remains intact.
