# Final integration — Stage 1: Phase 4 and Phase 5

Historical Stage 1 audit. Final Dashboard integration and presentation are now complete; see [dashboard guide](dashboard.md). The original audit scope and evidence below are preserved.

Audit date: 2026-10-04. Scope: retained EGS temporal and potential-exposure
workflow only. No Phase 4B, classifier tuning, Dashboard changes or Git commit.

## A–C. Current workflow and scientific validity

**Phase 4** converts seven operational, RCM-derived NRCan EGS acquisitions into
fixed-grid mapped-area observations, adjacent/beam-family comparisons and
endpoint transition geometry. Regional WaterOffice records provide hydrologic
context; later Sentinel-2 imagery provides recovery-period total-water agreement.

**Phase 5** translates the initial selected EGS flood snapshot into road-way and
bridge-tagged-way intersections, ALR-designation overlap, official place-point
proximity and a nine-grid inspection shortlist. It packages local evidence and
provenance for the final Dashboard.

Their retained calculations remain valid within these claim boundaries. Phase 3B
is frozen **FINAL EXPERIMENTAL FAIL**, not promoted to production. Independent
Level-1 processing and validation informed method selection; operational EGS
remains the production spatial source. The accessible Level-1 research set has
16 m/30 m inputs; matching inputs for the 5 m operational acquisitions were not
available locally. Resolution is one possible contributor, not an established
single explanation for the validation gap.

## D–H. Findings, corrections and remaining limits

### Temporal accounting and terminology

Verified observation dates are **12, 14, 15, 16, 17, 19 and 21 December 2025**
(UTC), not daily observations or a satellite-observed two-peak hydrograph.
Their EGS open-water-flood areas are respectively **54.92, 20.60, 50.72, 36.60,
37.28, 28.96 and 21.64 ha**. No new earlier satellite frame was invented.

The analytical grid is **EPSG:32610, 20 m, 300×300, 0.04 ha/pixel, 36 km²**.
It is separate from frozen experimental Phase 3B's 30 m/200×200 grid. A common
grid standardizes accounting, not beam, orbit, resolution or product response.

The fixed OBS01 EGS class-1 semantic reference is **971.88 ha**. It is not an
independent pre-flood observation or normal hydrologic water level. Raw class-1
areas of 971.88/973.28 ha remain product QA, not permanent-water growth.
Legacy `baseline` field names remain for consumer compatibility, with explicit
fixed-reference definitions in the handoff.

Endpoint identities reproduce from exported masks:

```text
54.92 = 19.48 persistent initial flood + 35.44 gross recession
21.64 = 19.48 persistent initial flood + 2.16 final-only flood
33.28 = 35.44 - 2.16 = 1,026.80 - 993.52
```

Thus 35.44 ha is **gross recession from the initial footprint**, not net decline.
The 33.28 ha net decline uses fixed-reference total mapped water.

The committed Chilliwack unit-value record verifies regional selected-window
anchors: first pulse **684 m³/s at 11 Dec 06:40 UTC**, inter-pulse low
**172 m³/s at 14 Dec 22:05 UTC**, second pulse **377 m³/s at 17 Dec 15:30 UTC**.
These are discharge, not water temperature. Hourly chart means differ from the
underlying five-minute extrema. Neither station timing nor the mixed-mode
14→15 December satellite jump identifies a pixel-level flood peak. The combined
chart uses different y-axis units; curve heights cannot be directly compared.

The historical Phase 4 discovery screen listed eight Level-1 catalogue records
and authentication constraints. It is now explicitly historical, not the final
eleven-product local inventory. A misleading coverage plot title and duplicate
notebook section numbering were corrected without changing plotted values.

### Recovery comparison

Saved Phase 4 output compares **fixed OBS01 class 1 union OBS07 class 2** with
Sentinel-2C NDWI/SCL-derived water. It does not evaluate isolated flood-class
accuracy or experimental RF performance.

RCM time is 21 Dec 14:16:46 UTC; Sentinel-2 time is 27 Dec 19:11:07.775 UTC:
**6.2044187 days apart**, not same-day validation. Existing counts are
TP=15,774, FP=8,017, FN=357, TN=64,367 (88,515 evaluated pixels).
F1=0.79024097 and IoU=0.65322180 reproduce arithmetically; rounded headline
values remain **0.790/0.653**. These counts and timestamps were transcribed from
existing executed output into `recovery_validation.json`; optical imagery was
not processed again. Timing, optical/SAR physics and masking remain limitations.

### Potential exposure and provenance

The current CSV contains **234 unique AOI-clipped road ways**, not the stale
232 stated in earlier prose. The archived response contains 238 envelope-return
ways; `exposed_roads.geojson` retains only the **121 ways within 250 m**.
The direct result is unchanged: **14 ways, 345.7434178 m total overlap**.

Three bridge-tagged ways are present in the full clipped CSV. Lougheed Highway /
BC 7 directly overlaps by **8.7172 m**. Taylor Road is **132.2793 m away**, not
a direct intersection. North Nicomen Road is about **343.2199 m away**.
Therefore one is direct and two are within 250 m. Repeated names can represent
different OSM ways, not duplicate roads. These are tagged road features, not
verified bridge damage or structural positions.

ALR overlap remains **36.6451804 ha / 66.72465%** of the initial mapped flood
snapshot. Only the verified overlap geometry is retained, not full AOI ALR
boundaries. It cannot support active-crop area, crop loss or full-AOI ALR area.
The notebook now reuses that overlap instead of silently refreshing the service.

The retained 25 nearest official place points are contextual locations, not a
complete settlement inventory. The closest point is about **303.7898 m** away;
there is no population-exposure estimate. Regional Highway 1 closure reporting
is not attributed to this compact AOI.

The nine retained grids are G042, G015, G047, G018, G019, G034, G026, G022 and
G009. Selection is:

```text
gain > 0 AND (increase > 5.88 pp OR direct road count > 0 OR direct bridge count > 0)
```

They are sorted by observed percentage-point increase, then gain area: an
inspection shortlist, not a composite risk score. G042 remains +21.50 pp and
G015 +6.78947 pp. Folly Lake's 5.88 pp is empirical method-variability context,
not a universal threshold or significance test. Nominal 1 km boundary squares
may extend outside the AOI; their coverage denominator is the AOI-clipped mask.

The original small Overpass payload is now retained with source metadata and
hashes. Its OSM base timestamp is **2026-10-03T20:40:11Z**. Exact HTTP retrieval
time/resolved endpoint were not recorded and are explicitly unknown, not
invented. Full original ALR polygons and the national place inventory are not
retained; provenance states these limits. Snapshot calculations reproduce the
existing exposure and grid outputs without refreshing external services.

No unsupported damage, closure, crop-loss, economic-loss or causal claims were
added. No duplicate/stale artifact was sufficiently safe to delete: compatibility
tables and historical figures remain for reproducibility, not as new results.

## I–J. Exact changed files

| File | Change |
|---|---|
| `notebooks/04_change_detection.ipynb` | Source-selection boundary, historical discovery scope, chart/total-water wording, section numbering, cached hydrology reuse and additive export metadata. Scientific algorithms retained. |
| `notebooks/05_impact_analysis.ipynb` | Frozen road/place/ALR snapshot reuse, 234-way correction, selection/claim definitions, recovery metrics read from provenance, derived compatibility endpoint view and additive export metadata. |
| `analysis/phase45_contract.py` (new) | Small metadata-only method-selection, recovery, exposure and hash helpers; no classifier or external queries. |
| `scripts/phase45_validate.py` (new) | Read-only offline regression of existing temporal, geometry, exposure and provenance contracts. |
| `tests/test_phase45.py` (new) | Four offline regression tests, including selected notebook cells from both repository and notebook working directories. |
| `data/processed/phase4/recovery_validation.json` (new) | Existing recovery counts, exact timestamps, metrics, source and claim boundary. |
| `data/processed/phase4/temporal_audit.json` | Additive source-selection/recovery metadata and new artifact hash. |
| `data/processed/phase5/road_source_snapshot.json` (new) | Unchanged copy of the existing cached source response; no fresh OSM query. |
| `data/processed/phase5/source_provenance.json` (new) | Source identities, scopes, recorded dates, hashes and explicitly missing provenance. |
| `data/processed/phase5/phase6_handoff.json` | Additive method selection, recovery/provenance pointers, exposure definitions and grid boundary; existing consumer interfaces retained. |
| `data/processed/phase5/evidence_chain.csv` | Frozen production-source decision and total-water recovery limitation. |
| `data/processed/phase5/limitations.csv` | Total-water comparison, failed experimental gate, separate grid and snapshot-scope limitations. |
| `docs/analysis-method.md` | Phase 4/5 production decision, temporal/recovery scope, retained snapshot semantics and exact selection definitions. |
| `docs/data-sources.md` | Verified road counts/scopes, source preservation and missing-provenance disclosure. |
| `docs/decisions.md` | Fixed semantic-reference terminology and current Phase 5 shortlist wording. |
| `docs/phase45-final-integration.md` (new) | This A–Q audit and handoff report. |

## K–L. Intentionally unchanged and recomputation boundary

- All frozen Phase 3B algorithms, results, notebook, gate and configuration.
- All existing production observation/metric CSVs, GeoJSON geometry, hydrology
  values and four Phase 5 PNG exports; no satellite, SNAP or optical pipeline run.
- Existing scientific thresholds, hotspot conclusions, endpoint calculations,
  exposure geometry and official source snapshots.
- `app.py`, Dashboard, broad main README and unrelated Phase 1/2 work.

Only metadata and evidence/limitation text outputs were updated. Read-only
regression recalculated arithmetic/intersections **in memory**, not new
production science exports. Selected Phase 5 calculation cells were executed
with network connections blocked, excluding export and PNG-writing cells.
Previously saved notebook outputs are historical execution evidence; updated
source/markdown states the current interpretation.

## M–P. Verification and Git summary

Checks completed:

- Offline `phase45_validate.py`: PASS for hashes/paths, unique UTC observations,
  CRS/geometry, pixel area, endpoint identities, six adjacent and three
  beam-family comparisons, gauge anchors, exposure and shortlist regression.
- Four standard-library `unittest` tests: PASS. Selected Phase 5 calculations
  work from both repository root and `notebooks/`, with network blocked; Phase 4
  stage alignment reuses its committed snapshot.
- New Python scripts/modules compile; both notebook schemas and every code-cell
  syntax validate. No full expensive notebook rerun was required.
- 182 protected tracked files match their pre-task SHA-256 values, including
  frozen 3B, existing analysis modules, `app.py` and main README.
- `git diff --check`: PASS. Existing production numerical CSVs, all Phase 4/5
  GeoJSON and historical PNG contents are unchanged from HEAD (27 artifacts).

The tests emit a non-fatal Rasterio/Affine `PendingDeprecationWarning` about
future matrix-multiplication syntax inside `from_origin`; all checks pass. No
dependency or scientific calculation was changed to suppress a library warning.

Git scope: **9 modified tracked files and 7 new files**, all listed above.
No deletion, commit, branch manipulation or Dashboard migration was performed.

## Q. Readiness and how to verify

**READY for final Dashboard integration**, using EGS production extent and the
clarified temporal/recovery/potential-exposure contracts. Readiness is not an
operational flood-mapping certification or a changed Phase 3B GO result.
This was the Stage 1 readiness checkpoint. Stage 2 Dashboard integration is now
complete; see [the final dashboard guide](dashboard.md). The historical record
below does not authorize another scientific rerun or change the Phase 3B gate.

No manual Phase 4/5 rerun is needed for the metadata delivered in this pass.
Run the read-only checks from the repository root:

```sh
conda activate space-hackathon-2026
python scripts/phase45_validate.py
python -m unittest discover -s tests -p test_phase45.py -v
git diff --check
```

The Phase 5 source calculations now reuse local snapshots. A full Phase 4
`Run All` still includes its original EO discovery/read steps and may require
network/cache inputs; it is not necessary for this audit and is not advertised
as fully offline.
