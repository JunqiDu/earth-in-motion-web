# Project Plan

## Goal

Use RADARSAT Constellation Mission (RCM) Earth observation data to detect, map, and monitor environmental change over time in Canada.

## Challenge concepts

- **Detect:** identify meaningful change between observations.
- **Map:** present the location and spatial extent of detected change.
- **Monitor:** support repeatable comparison of conditions over time.

## Planned workflow

```text
EODMS / RCM
    -> Jupyter exploration
    -> preprocessing
    -> change analysis
    -> processed outputs
    -> Streamlit web prototype
```

## Current scope

Phases 1–4 are complete. The final prototype case is the **December 2025 Fraser Valley / Lower Fraser flood**, analyzed in a fixed 6 km × 6 km Chilliwack-area AOI. The evidence chain combines seven NRCan EGS RCM-derived flood products, public RCM CEOS-ARD pre/post brackets, Sentinel-2 recovery validation, official emergency reporting, and an initial OpenStreetMap road/bridge overlay.

The current scientific result is a short-term **recovering flood with localized residual/persistent expansion**, not a long-term climate or landscape trend. Phase 5 will turn the validated analysis into an impact-focused, provenance-aware product without overstating infrastructure damage.

## Near-term milestones

1. **Complete:** review RCM products, access constraints, preprocessing, and independent validation.
2. **Complete:** screen real events and select the December 2025 Lower Fraser case.
3. **Complete:** map before/near-event/recovery water extent, quantify 1 km grids, compare empirical noise, and evaluate multi-source agreement.
4. **Next — Phase 5:** deepen road/bridge/community impact analysis in the two benchmark-exceeding grid cells and define small derived output files with provenance.
5. **Then:** build the Streamlit experience around the validated products, uncertainty language, timeline, agreement layers, and impact context.
