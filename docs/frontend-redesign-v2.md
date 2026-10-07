# Retail Intelligence — Cozy Intelligence v2

## Visual source of truth

The approved reference is the 3x3 screen collage supplied during the redesign. The implementation follows its visual grammar: warm cream canvas, white elevated cards, sage navigation, dusty blue live metrics, plum forecasting, terracotta attention states, rounded 16–22px surfaces, compact mono labels, friendly editorial headings, and small botanical/organic decorative shapes.

## Semantic color system

- Canvas: `#FFF9F2`
- Secondary surface: `#F5EFE7`
- Text: `#24313A`
- Live/current data: `#5B9FB3`
- Healthy/growth: `#7FA58A`
- Forecast/future: `#8B6B9E`
- Attention: `#D9785F`
- Anomaly/error: `#D95C5C`
- Discovery/insight: `#E8C66A`

Color is paired with text/icons for important states; it is never the sole meaning carrier.

## React Bits patterns used

Vendored/adapted components live under `frontend/src/components/bits/` so the project does not depend on a large runtime component package for simple effects.

- `BlurText` — page headlines
- `CountUp` — headline metrics
- `AnimatedContent` — page/section entrance
- `AnimatedList` — pipeline/process sequences
- `PillNav` — animated navigation state
- `SpotlightCard` — restrained cursor focus on cards
- `ShinyText` — selected forecast model only
- `DonutChart` — custom ECharts primitive inspired by the React Bits data-visual direction

The effects are intentionally restrained. Decorative shader/galaxy/cursor effects were rejected because they compete with analytical content.

## Motion/performance rules

- All page routes are `React.lazy` loaded.
- Forecast 3D remains a separate lazy chunk.
- Motion uses `LazyMotion` + the `m` API; full `motion` components are avoided inside the lazy boundary.
- Reduced-motion preferences are respected globally.
- Layout animation is limited to navigation/shared-state interactions.
- Charts render only when their route/component is mounted.
- Query caching is one minute by default because ready datasets are immutable.

## Backend speed hardening

- FastAPI GZip middleware compresses larger JSON responses.
- Response timing is exposed through `X-Response-Time-ms` for verification.
- Health returns measured database latency without running Spark/ML.
- Read-heavy immutable analytics responses have a bounded 120-second process-local TTL cache.
- Dashboard/forecast query paths received targeted PostgreSQL indexes.
- Forecast capability checks now use `COUNT/MIN/MAX` instead of loading the full series into pandas.
- Forecast auto mode defaults to `rf,xgb` for a fast evidence-based path; explicit requests can still run ARIMA or Prophet.
- Forecast workers now guarantee that unexpected failures transition groups to `failed` instead of leaving jobs stuck in `running`.

## Ponytail checks applied

1. Reuse the existing React/Tailwind/Motion/ECharts/R3F/TanStack stack.
2. Do not introduce a second animation or charting library.
3. Do not introduce Redis/Celery for demo-scale workloads where the current bounded worker model is sufficient.
4. Keep 3D isolated because it is visually useful but expensive.
5. Prefer browser/compositor-friendly transforms and opacity for animation.
6. Add complexity only when it removes a measured bottleneck or improves a real user task.
