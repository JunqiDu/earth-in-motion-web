# Final Dashboard and Demo Guide

## Source-selection story

The prototype has two stages: independent RCM Level-1 research and method selection, followed by temporal and potential-exposure communication using the retained operational EGS source. RF v2 improved over RF v1 but failed the unchanged scientific gate. Do not present experimental RF output as the final flood map.

## Seven pages

| Page | Main responsibility |
|---|---|
| Overview | Event summary, source-selection story, and high-level workflow |
| Map | Seven stored acquisitions, a paused one-pass player, and spatial exploration |
| Monitor | Discrete EGS observations and regional hydrology on a shared timeline |
| Impact | Snapshot-based infrastructure, ALR-designation, and place context |
| Detect | Endpoint local changes, particularly G042 and G015 |
| Research & Method | Frozen independent Level-1 experiments and the EGS-retention decision |
| Evidence & Sources | Validation, provenance, supported claims, and limitations |

## Map and Monitor behavior

Map starts paused. Drag the single acquisition slider to choose a stored observation. **Play one pass** advances through all seven observations once and stops. Available UTC dates are 12, 14, 15, 16, 17, 19, and 21 December 2025. Contextual exposure overlays retain the 12 December snapshot; they are not recomputed for each frame.

Monitor aligns the discrete extent series with saved regional hydrology. The units and sampling differ: mapped EGS flood area is measured in hectares, while Chilliwack discharge is measured in cubic metres per second. Their agreement supplies regional timing context, not pixel-level validation or a measured satellite flood peak. A dotted acquisition-order line does not interpolate flood geometry.

The final display restores a CARTO/OpenStreetMap basemap. Scientific layers are local, but basemap resources require internet. No satellite download, RF training, or OSM exposure query runs at startup. Preserve CARTO/OSM attribution in screenshots.

## Suggested two-minute demo

1. **Overview:** introduce the 36 km² Lower Fraser case and explain that RCM research led to a defensible source-selection decision.
2. **Map:** click Play one pass, then drag the slider to compare two observations. Explain that playback visits real stored acquisitions only.
3. **Monitor:** identify the regional two-pulse context and distinguish it from seven discrete satellite observations.
4. **Impact:** show 14 directly intersecting road ways and the ALR overlap. Say “potential exposure,” not “confirmed damage.”
5. **Research & Method:** show the frozen RF v2 result and explain why EGS remains operational. Use Evidence & Sources for validation questions.

## Numbers to keep distinct

- Initial flood footprint: **54.92 ha**; final footprint: **21.64 ha**.
- Initial footprint persistence: **19.48 ha**; gross recession: **35.44 ha**; final-only mapping: **2.16 ha**; net decline: **33.28 ha**.
- Saved AOI road inventory: **234 ways**; direct intersections: **14 ways / 0.345743 km**.
- Direct bridge-tagged way: **1**, not a confirmed damaged bridge.
- ALR-designated overlap: **36.645 ha / 66.7%**, not a crop map or crop-loss estimate.
- Primary RF v2 median **IoU 0.353 / F1 0.522**; legacy IoU 0.409 uses a different reference path.
- Recovery total-water Sentinel-2 agreement: **F1 0.790 / IoU 0.653**, approximately **6.2 days apart**, not RF or same-day flood-class accuracy.

## Delivery boundary

The scientific workflow is frozen. No remaining-six Level-1 run, Phase 4B promotion, new calibration, or threshold adjustment is pending. The five-slide final deck is a local deliverable, explicitly Git-ignored. It does not change the source contracts.
