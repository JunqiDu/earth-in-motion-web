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

Phases 1–5 are complete. The final prototype case is the **December 2025 Fraser Valley / Lower Fraser flood**, analyzed in a fixed 6 km × 6 km Chilliwack-area AOI. The evidence chain combines seven NRCan EGS RCM-derived flood products, public RCM CEOS-ARD pre/post brackets, Sentinel-2 recovery validation, official emergency reporting, refined OpenStreetMap road/bridge exposure, official place-name context, and B.C. Agricultural Land Reserve overlap.

The current scientific result is a short-term **recovering flood with localized residual/persistent expansion**, not a long-term climate or landscape trend. Phase 5 has consolidated the impact case without overstating infrastructure, community, or agricultural damage. Phase 6 should present the retained small derived outputs rather than rerunning raw discovery or analysis.

## Near-term milestones

1. **Complete:** review RCM products, access constraints, preprocessing, and independent validation.
2. **Complete:** screen real events and select the December 2025 Lower Fraser case.
3. **Complete:** map before/near-event/recovery water extent, quantify 1 km grids, compare empirical noise, and evaluate multi-source agreement.
4. **Complete — Phase 5:** quantify priority grids, road/bridge proximity, official place context, ALR overlap, evidence chain, claims, limitations, and reusable maps.
5. **Next — Phase 6:** build the Streamlit experience around `data/processed/phase5/` and `assets/phase5/`, preserving provenance, uncertainty language, the event timeline, exposure caveats, supported claims, and restricted claims.

## Phase 6 handoff

- `final_case_metrics.csv` for the compact headline metrics
- `temporal_series.csv` for the near-event/recovery timeline
- `priority_grid_impact.csv` and `priority_grids.geojson` for explanatory grid content
- `road_exposure.csv`, `bridge_exposure.csv`, and `exposed_roads.geojson` for infrastructure context
- `community_proximity.csv` for named-place context
- `flood_gain.geojson`, `flood_gain_zones.geojson`, and `alr_gain_overlap.geojson` for map layers
- `evidence_chain.csv` and `official_event_sources.csv` for provenance and official context
- `limitations.csv`, notebook-supported claims, and notebook-restricted claims for mandatory caveats
- four PNG analytical maps in `assets/phase5/` for immediate reuse
- `phase6_handoff.json` as the machine-readable manifest
