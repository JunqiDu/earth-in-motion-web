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

The current scientific result is a **lower final mapped extent after a variable seven-acquisition sequence, with localized persistence and redistribution**. Regional hydrology and acquisition/product differences both contribute to the non-monotonic record. This is not a daily flood trajectory, measured event peak, or long-term climate trend. Phase 5 consolidates the endpoint potential-exposure case without overstating infrastructure, community, or agricultural damage.

## Near-term milestones

1. **Complete:** review RCM products, access constraints, preprocessing, and independent validation.
2. **Complete:** screen real events and select the December 2025 Lower Fraser case.
3. **Complete:** map a fixed semantic reference plus seven acquisition snapshots, quantify 1 km endpoint grids, audit acquisition comparability, and evaluate multi-source agreement.
4. **Complete — Phase 5:** quantify priority grids, road/bridge proximity, official place context, ALR overlap, evidence chain, claims, limitations, and reusable maps.
5. **Complete — Phase 6:** build the Streamlit experience around `data/processed/phase5/`, preserving provenance, uncertainty language, the seven-observation event trajectory, exposure caveats, supported claims, and restricted claims.

The final dashboard separates its narrative responsibilities: Overview explains the event and high-level workflow; Detect identifies local hotspots; Map provides the complete local layer explorer; Monitor presents temporal evolution; Impact presents purpose-built potential-exposure views; Evidence & Method documents validation and limitations.

## Scientific and Phase 6 handoff

- `data/processed/phase4/event_observations.csv` as the canonical seven-acquisition table
- `egs_open_water_flood_frames.geojson`, `egs_permanent_water_reference.geojson`, and `endpoint_transition.geojson` as the temporal spatial contract
- `acquisition_comparisons.csv` and `beam_family_comparisons.csv` for adjacent and like-beam QA
- `event_hydrology.csv` for compact daily regional gauge context
- `event_hydrology_unit_values.csv`, `hydrologic_stage_summary.csv`, and `rcm_stage_alignment.csv` for the committed two-pulse regional hydrologic context and timestamp alignment
- `temporal_audit.json` for definitions, missing fields, diagnosis, endpoint identities, and hashes

- `final_case_metrics.csv` for the compact headline metrics
- `temporal_series.csv` as a deprecated generated two-row compatibility view
- `event_trajectory.csv` as a retained generated compatibility view; Map and Monitor now read the canonical Phase 4 temporal contract directly
- `priority_grid_impact.csv` and `priority_grids.geojson` for explanatory grid content
- `road_exposure.csv`, `bridge_exposure.csv`, and `exposed_roads.geojson` for infrastructure context
- `community_proximity.csv` for named-place context
- `flood_gain.geojson`, `flood_gain_zones.geojson`, and `alr_gain_overlap.geojson` for map layers
- `evidence_chain.csv` and `official_event_sources.csv` for provenance and official context
- `limitations.csv`, notebook-supported claims, and notebook-restricted claims for mandatory caveats
- four PNG analytical maps in `assets/phase5/` retained as provenance exports; normal Dashboard startup renders local vectors dynamically
- `phase6_handoff.json` as the machine-readable manifest
