# RIPPLE — User Interface Architecture & Design Notes

This document specifies the design system, motion choreography, 3D visualization principles, and technical characteristics of the production React interface for RIPPLE.

---

## 1. Design System & Tokens

The interface uses a strict dark theme engineered for clinical operational centers and decision-support rooms. Heavy shadows and decorative glows are eliminated in favor of clean 1px structural borders and subtle surface elevations.

### Color Tokens

All design tokens are defined as CSS custom properties in `:root` and bound to Tailwind CSS utilities:

| Token | Value | Semantic Role | WCAG AA Contrast |
|---|---|---|---|
| `--bg` | `#0B0D10` | Base canvas background | Baseline |
| `--surface` | `#12151A` | Secondary background, panel containers | Baseline |
| `--raised` | `#171B21` | Elevated cards, buttons, table headers | Baseline |
| `--border` | `#232831` | Structural 1px division lines | Division |
| `--text` | `#E6E8EB` | Primary typography, headers, high-importance labels | 17.5:1 on `--bg` |
| `--secondary` | `#A6AFBC` | Secondary text, parameter descriptions | 8.8:1 on `--bg` |
| `--muted` | `#96A0AD` | Metadata labels, timestamps, tabular captions | 6.7:1 on `--surface` (exceeds 4.5:1 AA) |
| `--accent` | `#5B8CFF` | Single interactive accent, active tabs, focus ring | 6.8:1 on `--bg` |
| `--retraction-red` | `#E5484D` | Retraction notice indicators, failed tasks | Diagnostic |
| `--at-risk-amber` | `#F5A524` | At-risk clinical decisions, score increases | Diagnostic |
| `--ok-green` | `#3FB950` | Safe status, score reductions, healthy leases | Diagnostic |

### Geometry & Spacing
- **Grid:** 8px base spacing grid with 4px sub-intervals for dense data tables.
- **Border Radius:** 6px radius (`rounded-DEFAULT`) on controls, cards, and modal windows.
- **Borders:** Consistent 1px solid `var(--border)` rather than drop shadows.

### Typography
- **UI & Reading:** `Inter` (bundled locally via `@fontsource/inter`, 400/500/600 weights).
- **Identifiers & Numeric Data:** `JetBrains Mono` (bundled locally via `@fontsource/jetbrains-mono`).
- **Tabular Figures:** `font-variant-numeric: tabular-nums` enforced on all metrics, scores, timers, and latencies.
- **Type Scale:** Exactly 5 discrete steps: 10px (micro), 11px (caption), 12px (body), 13px (ui base), 15px (header/title).

---

## 2. Motion Rules & Choreography

Motion in RIPPLE is purposeful: animations only exist to communicate an underlying state change.

### Permitted Animations
- **Task Progression:** Moving tasks across coordination columns (queued -> claimed -> done) uses Framer Motion layout transitions (200ms ease-out).
- **Alert Score Adjustments:** Numerical deltas animate over 300ms accompanied by directional indicator arrows (`ArrowDown` green / `ArrowUp` amber).
- **Rule Consolidation:** When episodic feedback consolidates into a rule, the new active rule highlights once and settles into place.
- **Dock Tab Switching:** Smooth cross-fade (150ms).
- **Camera Focus:** Smooth ease-in-out camera lerp (600ms) when a node is selected in the 3D scene.

### Prohibited Patterns
- No looping background pulses or ambient particle fields.
- No glassmorphic blur or backdrop filters.
- No bounce, rubber-band overshoot, or typewriter text effects.
- No auto-rotating 3D scenes.
- **Accessibility:** Honors `prefers-reduced-motion`—disables camera tweens and wave expansion, snapping instantly to the resolved final layout state.

---

## 3. 3D Scene Architecture: Radial Hop Ripples

The 3D blast radius visualization is the signature component of RIPPLE, designed to communicate evidentiary distance rather than decorate the screen.

### Concept: Distance From Center = Graph Hop Distance
- **Hop 0 (Center):** The Retraction notice (`SYN-RET-001`), the epicenter of the ripple.
- **Hop 1 (Radius 18 units):** Directly retracted clinical trials (`SYN-TR-0001`).
- **Hop 2 (Radius 36 units):** Contaminated systematic reviews and meta-analyses (`SYN-REV-001`).
- **Hop 3 (Radius 54 units):** Impacted clinical guidelines (`SYN-GL-001`).
- **Hop 4 (Radius 72 units):** Hospital formulary decisions placed at risk (`DEC-CARDIO-001`, `DEC-CARDIO-002`).

### High-Performance Draw Calls (InstancedMesh)
Instead of individual Three.js meshes, every entity is rendered via `InstancedMesh` grouped by distinct geometric topology:
- **Retraction:** Octahedron
- **Trial:** Sphere
- **Review:** Box
- **Guideline:** Icosahedron
- **Decision:** Dodecahedron (colored amber if `at_risk`)
- **Committee / Person:** Cone

Edges are rendered as a single batch `LineSegments` geometry with 0.25 opacity.

### Signature Animation ("Ripple Wave")
When a retraction notice is selected or when a trace completes:
1. A thin wave ring expands radially outward from the origin.
2. Nodes scale up with an ease-out curve at $t = \text{hop} \times 200\,\text{ms}$.
3. Incident connecting edges draw on as the wavefront crosses them.
4. Total animation duration is bounded under 1.5 seconds without recurring loops.

### Accessibility & Fallback
- **Automatic Fallback:** If WebGL is unavailable or context is lost, the stage automatically switches to a 2D Evidence Cascade view displaying nodes in outward concentric shells.
- **Manual Toggle:** Users can manually switch to the 2D view using the stage controls.
- **Screen Reader Drawer:** An accessible keyboard-navigable list drawer is accessible via button or shortcut.

---

## 4. Performance & Bundle Budget

| Chunk | Raw Size | Gzip Size | Budget Target | Status |
|---|---|---|---|---|
| Main App (`index.js`) | 204.25 KB | 53.95 KB | < 250 KB gzip | **Passed (78% below budget)** |
| 3D Scene (`BlastScene3D.js`) | 6.74 KB | 2.73 KB | Dynamic chunk | **Passed** |
| Three.js Core (`three-chunk.js`) | 1,180.87 KB | 325.32 KB | Lazy loaded | **Passed** |
| Stylesheet (`index.css`) | 45.20 KB | 19.12 KB | - | **Passed** |

- **Polling Strategy:** Polling intervals are strictly decoupled: Tasks and Agents poll at 1,000ms; Rankings and Memory poll at 2,000ms; Blast radius and Explain queries execute on-demand with TanStack Query structural sharing.

---

## 5. Known Limitations

1. **Groq LLM TPM Limits:** The Groq free-tier endpoint has token-per-minute (TPM) limits. Rapid repetitive analyst plan executions may trigger rate-limiting, causing the agent to fall back to the deterministic fixed planner.
2. **Software WebGL Performance:** In virtualized or headless environments without GPU hardware acceleration (e.g. CI containers running SwiftShader), 3D canvas rendering relies on software rasterization. The app automatically detects this or allows immediate 1-click fallback to the 2D cascade view.
