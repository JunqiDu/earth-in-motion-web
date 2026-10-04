# Earth in Motion

Earth in Motion is a flood-monitoring prototype that uses RADARSAT Constellation Mission (RCM) imagery to study the December 2025 Lower Fraser flood in British Columbia. We independently evaluated Level-1 SAR flood detection, then combined trusted operational flood products with hydrology, transportation, and agricultural data to visualize flood evolution and potential impacts in an accessible dashboard.

Developed for **Mission Accepted Space Hackathon 2026, Challenge 3**, the final case uses a fixed **36 km² Chilliwack-area study region**.

The project combines independent RCM Level-1 research with a carefully selected operational mapping source. Scientific analysis is complete and frozen; the dashboard communicates the retained evidence rather than rerunning it.

## What the prototype does

- **Detect:** identify mapped open-water expansion and local hotspots.
- **Map and monitor:** explore seven observed flood snapshots alongside regional hydrology.
- **Contextualize:** show potential exposure of roads, bridge-tagged ways, ALR-designated land, and official place points.

## Two-stage workflow

### 1. Independent RCM research and method selection

Eleven local RCM Level-1 GRD products were inventoried. Five EGS-matched acquisitions were calibrated and terrain-corrected with **ESA SNAP 14**, then analyzed on a fixed **30 m grid**. Research progressed through interpretable SAR thresholds, a Lee-filter comparison, multisource constraints, and historical-label Random Forest models. EGS flood labels were used for evaluation, not RF training.

| Primary five-date evaluation | Median IoU | Median F1 |
|---|---:|---:|
| RF v1 | 0.296 | 0.457 |
| Final RF v2 | 0.353 | 0.522 |

Final RF v2 did not meet the unchanged acceptance criteria: **FINAL EXPERIMENTAL FAIL**. The research is closed, not awaiting further tuning. Its legacy-reference IoU of 0.409 and separate neighboring-area checks are supporting diagnostics, not substitutes for the primary five-date gate.

The finest imagery in the accessible local Level-1 set was **16 m**, with other products at **30 m**. Some operational EGS snapshots used 5 m acquisitions whose matching Level-1 products were not in this local set. Resolution is a plausible contributor to disagreement, not a proven explanation or evidence that EGS is error-free.

### 2. Operational evidence and impact communication

The final prototype retains **NRCan EGS RCM-derived open-water flood products** as its operational extent source. Phase 4 audits the discrete acquisitions on a separate **20 m grid**; Phase 5 packages temporal, exposure, and provenance outputs; the Streamlit dashboard presents them with explicit limitations.

The Level-1 experimental models do not replace the EGS production outputs. The dashboard reads saved scientific data and does not download scenes, retrain models, or refresh exposure queries at startup.

## Data and roles

| Source | Role |
|---|---|
| RCM Level-1 GRD via EODMS | Main independent SAR research and method evaluation |
| NRCan EGS RCM-derived products | Retained operational flood mapping and acquisition sequence |
| ECCC historical water occurrence, freshwater mapping, elevation and land-cover inputs | Research constraints and contextual features, with their recorded provenance |
| Sentinel-2 | Independent recovery-period total-water agreement check |
| WaterOffice hydrometric observations | Regional two-pulse event context, not pixel-level ground truth |
| Saved OSM ways, B.C. ALR designation, official place points | Potential-exposure and geographic overlays |
| CARTO / OpenStreetMap basemap | Online visual context only; not a scientific input |

Exact sources, dates, and claim boundaries are recorded in [data sources](docs/data-sources.md), [analysis methods](docs/analysis-method.md), and the processed manifests.

## Dashboard

| Page | Question answered |
|---|---|
| Overview | What changed, and how was the result selected? |
| Map | Where do the observed snapshots and contextual layers lie? |
| Monitor | How do discrete RCM-derived observations align with regional hydrology? |
| Impact | Which assets or designated land could be exposed? |
| Detect | Where are the strongest local endpoint changes? |
| Research & Method | What did independent Level-1 research achieve, and why was EGS retained? |
| Evidence & Sources | What supports the conclusions, and what are their limits? |

Map starts **paused**. Its single acquisition slider selects a stored frame; **Play one pass** advances through the observations once and stops. The available dates are **12, 14, 15, 16, 17, 19, and 21 December 2025 (UTC)**. No intermediate flood geometry is invented.

All analytical CSV/GeoJSON layers are local. The restored **CARTO/OSM basemap requires internet** for geographical context; this is distinct from the saved science and does not trigger satellite or exposure-data queries. See the [dashboard and demo guide](docs/dashboard.md).

### Selected results and their meaning

- **54.92 ha:** initial selected EGS open-water flood extent, not a measured event peak.
- **35.44 ha:** gross recession from that initial footprint; **33.28 ha** is the net endpoint decline.
- **234** saved AOI road ways; **14** directly intersect the initial mapped footprint, totaling **0.346 km** of geometric overlap.
- **36.65 ha / 66.7%:** mapped initial flood extent overlapping ALR designation, not demonstrated crop loss.

Intersections and proximity represent **potential exposure only**, not confirmed damage.

## Repository structure

```text
app.py                         Final seven-page Streamlit prototype
analysis/                      Reusable research and integration code
config/                        Registered processing configuration
notebooks/                     Research notebooks and frozen conclusions
scripts/                       Preflight, validation, and controlled export tools
tests/                         Automated regression tests
data/processed/phase3b/         Frozen Level-1 research evidence and gate
data/processed/phase4/          Canonical temporal record, frames, and hydrology
data/processed/phase5/          Exposure outputs and dashboard handoff
assets/phase5/                 Retained analytical PNG exports
docs/                          Methods, decisions, sources, and run instructions
presentation/                  Local final deck; PPTX and build files are Git-ignored
```

Raw products, DEMs, calibrated caches, model caches, and SNAP intermediates remain local and are excluded from Git. Canonical Map/Monitor inputs are the Phase 4 observation and stage-alignment tables plus stored frame geometry. Phase 5 trajectory files are compatibility views, not temporal sources of truth.

## Run

From the repository root, using the existing environment:

```bash
conda activate space-hackathon-2026
python -m streamlit run app.py
```

Open <http://localhost:8501>. SNAP and raw Level-1 downloads are not required to view the saved prototype.

For a new environment:

```bash
conda env create --file environment.yml
conda activate space-hackathon-2026
```

Optional read-only contract and dashboard checks:

```bash
python scripts/phase45_validate.py
python -m unittest discover -s tests -p test_dashboard.py -v
```

See [environment instructions](docs/environment.md), [frozen Phase 3B](docs/phase3b.md), [research comparison](docs/phase3b_method_research.md), [Phase 4/5 integration](docs/phase45-final-integration.md), and [completed project scope](docs/project-plan.md). These records preserve failed experiments as well as the final source-selection decision.

## Limits

The fixed EGS permanent-water layer is a **semantic reference**, not an independently observed normal or pre-event water level. A common grid does not remove beam, resolution, orbit, radiometry, or product-processing differences. Seven snapshots are not a continuous hydrograph or a measured satellite flood peak. Regional gauges contextualize two hydrologic pulses but do not validate individual pixels.

The Sentinel-2 check compares recovery-period **total mapped water**, approximately **6.2 days apart**, not same-day flood-class or RF accuracy. Exposure overlays retain the **12 December snapshot**. The project does not infer flood depth, confirmed infrastructure damage, crop loss, population exposure, or climate attribution.
