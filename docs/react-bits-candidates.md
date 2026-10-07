# React Bits candidates (discovery only — nothing installed)

Source inspected: official repo `DavidHDev/react-bits` + `https://reactbits.dev/llms.txt`
(2026-09-30). Free library, MIT + Commons Clause. Four variants per component;
ours would be **TS-TW** (TypeScript + Tailwind). Install method if selected:
**manual copy** into `frontend/src/components/bits/` (no shadcn CLI — we have no
components.json/radix setup in Phase 1, and manual copy keeps the diff reviewable).

Global rule: one animation dependency max. Candidates pull from three engines
(gsap, motion, three/ogl) — selecting across engines is forbidden without a
dedicated decision. Most Backgrounds are rejected outright as anti-industrial.

## 1. Hero typography → BlurText (candidate)

- Purpose: single restrained reveal of the Data Lab / overview headline.
- Why it fits: blur-to-sharp reads as "focus pulling", calm, one-shot — no loops.
- Deps: `motion`. Perf: fine (transform/opacity, one-shot, respect reduced-motion).
- Alternative: SplitText (staggered chars) — livelier, but needs `gsap`; pick ONE engine.
- Verdict: shortlist. Decide motion-vs-gsap once, then take BlurText OR SplitText, never both.

## 2. Navigation interaction → PillNav (candidate)

- Purpose: sliding active highlight for the 8-area nav when it exists.
- Why it fits: minimal pill + easing; reads as instrument switchgear, not decoration.
- Deps: verify per variant (typically motion or CSS-only). Perf: trivial.
- Rejected: GooeyNav (playful blob — wrong register), BubbleMenu, Dock.
- Verdict: shortlist for Phase 2 nav.

## 3. Section entrance → FadeContent (candidate)

- Purpose: mount/scroll entrance wrapper for cards and sections.
- Why it fits: directional fade/slide, threshold trigger, no theatrics.
- Deps: verify (likely motion or CSS). Perf: IntersectionObserver-based, cheap.
- Rejected: GradualBlur/GradualBlur-cinematic (heavy blur = readability risk on charts).
- Verdict: shortlist; share the chosen engine with #1.

## 4. Metric transitions → CountUp (strong fit)

- Purpose: animated KPI numerals (revenue, rows, MAPE deltas) on value change.
- Why it fits: numbers changing IS the content in analytics; formatting/decimals built in.
- Deps: none/heavy-free (verify; historically dependency-light). Perf: trivial.
- Sibling: Counter (components group) — same job; pick one.
- Verdict: **recommend**. Highest value-per-byte in the whole catalogue for this project.

## 5. Hover interactions → GlareHover (candidate, restrained use)

- Purpose: subtle moving sheen on clickable cards only.
- Why it fits (conditionally): steel-on-paper sheen can feel machined; must be toned down.
- Rejected: BorderGlow, ElectricBorder, StarBorder (glow = banned by visual direction),
  SpotlightCard, TiltedCard (3D tilt fights chart readability).
- Verdict: maybe; only if hover feedback proves lacking. Default is CSS transitions.

## 6. Loading / progress → Stepper (strong fit)

- Purpose: multi-step pipeline progress: upload → validate → profile → curate.
- Why it fits: communicates STATE (our animation rule), perfect for the Spark job flow.
- Deps: verify (expected light). Perf: trivial.
- Micro alternatives: LatticeLoader / StatusMark (agent-status rows) — overkill for Phase 1.
- Verdict: **recommend** for Data Lab job states.

## 7. Forecast transitions → AnimatedList (candidate)

- Purpose: staggered reveal of model-comparison rows when a forecast run completes.
- Why it fits: list semantics preserved; stagger communicates "results arriving".
- Deps: verify (likely motion). Shares engine with #1/#3 if motion wins.
- Rejected: PixelTransition/PixelSwap (gimmicky for financial data), Shuffle (playful).
- Verdict: shortlist for Phase 4 forecast UI.

## 8. Background treatment → DotGrid or Noise only (conditional)

- Purpose (if any): faint engineering-grid texture or film grain on hero/shell — static-leaning.
- Why these two only: DotGrid ≈ graph paper (industrial); Noise ≈ material texture.
  Both can run near-static (or CSS-only fallback).
- Rejected: EVERYTHING else — Aurora/SoftAurora, LiquidChrome, Ballpit, Galaxy,
  Iridescence, Plasma, Hyperspeed, Beams, Threads (decorative motion that fights
  chart readability and the no-neon rule).
- Verdict: default is NO background animation. Revisit only with a static-first mock.

## Phase 2 verdict (actually used)

- **CountUp — USED** (vendored `src/components/bits/CountUp.tsx`, TS-TW, `motion`
  engine). KPI numerals on /overview. Only animation dependency added.
- **FadeContent — EVALUATED, REJECTED**: pulls gsap + ScrollTrigger, a second
  engine. Replaced by `src/components/Reveal.tsx` (IntersectionObserver + CSS,
  ~30 lines, reduced-motion aware). Same job, zero bytes of new deps.
- **Stepper — DEFERRED**: no staged progress events exist in the upload flow;
  adding it would decorate, not communicate.
- **BlurText / PillNav / DotGrid / Noise — DEFERRED** to the phase that owns
  hero/nav/background work. Default remains no decorative animation.

| Engine | Pulled by | Approx. cost |
|---|---|---|
| motion | BlurText, FadeContent?, AnimatedList? | ~40 KB |
| gsap | SplitText | ~70 KB |
| three/ogl | backgrounds | already carried for R3F; no NEW engine for 2D |

Recommendation: standardize on **motion** if shortlisted text/section/list items are taken;
**gsap only** if SplitText beats BlurText. Never both. ECharts keeps its own internal
animation (chart readability first; disabled under prefers-reduced-motion).
