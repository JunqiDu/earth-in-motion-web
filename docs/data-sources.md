# Data Sources

## Final source roles

The records below preserve discovery history. The final study is the December 2025 Lower Fraser flood, not Folly Lake. Eleven locally accessible RCM Level-1 products supported independent research; five EGS-matched acquisitions were processed and evaluated. The frozen RF v2 failed the unchanged promotion gate, so seven operational RCM-derived EGS snapshots remain the production extent source.

Historical water occurrence, freshwater mapping, elevation, and land-cover layers supported research constraints. Sentinel-2 provides a recovery-period total-water comparison, and WaterOffice gauges provide regional timing context. Neither constitutes same-day flood-pixel ground truth. Saved OSM, ALR, and official place data supply potential-exposure context. The final saved AOI road inventory is **234 ways**, with 14 direct intersections.

The restored CARTO/OpenStreetMap basemap is online display context, separate from the saved OSM exposure snapshot. It neither refreshes those metrics nor provides new satellite evidence. See [frozen research](phase3b.md), [integration](phase45-final-integration.md), and [dashboard guide](dashboard.md) for the final source-selection decision and claim boundaries.

This document records the Phase 1 feasibility snapshot confirmed on 2026-10-03. Folly Lake is a temporary test AOI, not the final hackathon study area.

## Confirmed facts

### Official services and references

- EODMS STAC API: <https://www.eodms-sgdot.nrcan-rncan.gc.ca/search>
- Public RCM CEOS-ARD collection: <https://www.eodms-sgdot.nrcan-rncan.gc.ca/search/collections/rcm-ard>
- EODMS RCM Level-1 collection: <https://www.eodms-sgdot.nrcan-rncan.gc.ca/search/collections/RCMImageProducts>
- Official NRCan example workflows: <https://github.com/eodms-sgdot/radarsat-notebooks>
- RCM CEOS-ARD open-data registry entry: <https://registry.opendata.aws/rcm-ceos-ard/>
- Nova Scotia Folly Lake inventory map: <https://novascotia.ca/fish/documents/lake-inventory-maps/6-Co-folly.pdf>

### Test AOI

- Name: Folly Lake, Colchester County, Nova Scotia
- Approximate reference point: 45.538750° N, 63.546195° W
- Search bounding box: `(-63.575, 45.515, -63.515, 45.565)`
- Search CRS: EPSG:4326 longitude/latitude; the STAC collection advertises CRS84 search coordinates with the same longitude/latitude axis values
- Selection reason: inland freshwater lake, approximately 80 hectares, no ocean coastline or tidal boundary, elongated and visually distinct shoreline, and multiple RCM acquisitions

### Search method

The notebook uses `pystac-client` with the official EODMS STAC API, the AOI bounding box, and a fixed feasibility interval from 2019-06-12 through 2026-10-03. Metadata search does not require credentials.

### Level-1 catalogue (`RCMImageProducts`)

| Field | Confirmed result |
| --- | --- |
| Product records | 497 |
| Approximate unique passes | 356, grouped by satellite ID and absolute orbit |
| Temporal coverage | 2020-01-02 to 2026-09-11 |
| Approximate unique passes by year | 2020: 20; 2021: 57; 2022: 81; 2023: 86; 2024: 63; 2025: 32; 2026: 17 |
| Approximate frequency | Median observed pass gap about 4 days; maximum gap about 140 days |
| Products | GRD (295), SLC (56), MLC (146) records |
| Platforms | RCM-1, RCM-2, RCM-3 |
| Polarizations present | HH/HV, CH/CV, and VH/VV combinations |
| Orbit directions | Ascending and descending |
| Formats | 496 GeoTIFF records and one NITF21 record |
| Access | Metadata and thumbnails are public; product ZIP assets declare bearer-token authentication |

The 497 values above are product records, not 497 independent acquisitions. Grouping by satellite and absolute orbit reduces duplicated processing/product variants but remains an approximate pass count.

If a later phase requires a Level-1 ZIP, the user must sign in to EODMS, obtain the authorized bearer token through the official account workflow, and expose it only in a local, non-versioned environment or session. It must not be pasted into the notebook, source code, documentation, or Git.

### Public CEOS-ARD (`rcm-ard`)

| Field | Confirmed result |
| --- | --- |
| Catalogue records | 10 |
| Approximate unique passes | 8, grouped by product-title satellite and absolute orbit |
| Temporal coverage | 2025-07-14 to 2026-08-02 |
| Approximate unique passes by year | 2025: 6; 2026: 2 |
| Observed gaps | 12, 48, 32, 12, 12, 240, and 28 days; median about 28 days |
| Product / processing | MLC, Level 2, CEOS ARD `NRB - POL` |
| Instrument mode | `Medium Resolution 30m` |
| Polarizations reported by STAC | CH, CV, XC |
| Orbit / look direction | Descending, right-looking |
| Output grid spacing | 20 m × 20 m |
| Public assets | RR and RL backscatter COGs, covariance data, masks, local incidence angle, quicklooks, XML metadata, and EULA |
| Raster CRS tested | EPSG:32620 |
| Asset format tested | Cloud-Optimized GeoTIFF over HTTPS with byte-range support |
| Selected RR asset size | 74,809,647 bytes (about 71.34 MiB); only the AOI window was read |
| Access | Public S3 asset opened without credentials |
| Licence signal | The STAC collection reports `proprietary`, and each item includes an EULA asset; downstream redistribution terms still need review |

The tested 2025-07-14 RR raster was read successfully with Rasterio. Folly Lake appears dark relative to much of the surrounding land, and the shoreline is visually distinguishable. This is a qualitative feasibility observation, not a water classification result.

No full scene or large raw file was downloaded; only remote metadata, HTTP headers, and byte ranges needed for the AOI window were accessed.

## Current assumptions

- Satellite ID plus absolute orbit is a useful practical key for estimating independent passes, although it is not a complete scene-equivalence test.
- The public ARD assets are the best starting point for prototype analysis because they are window-readable and do not require an EODMS bearer token.
- The 30 m instrument-mode label and 20 m output grid spacing describe different aspects of the product and should not be treated as interchangeable measures of effective spatial resolution.

## Unresolved questions

- Why is the public CEOS-ARD temporal subset much smaller than the searchable Level-1 archive for this AOI?
- Are all eight public ARD passes geometrically and radiometrically comparable enough for later time-series analysis?
- Which EODMS account role would be required if a later phase needs Level-1 product ZIP downloads?
- What EULA and redistribution conditions apply to derived hackathon outputs?
- Which environmental phenomenon and final study area should the project select?

## Phase 3 supporting datasets

### Nova Scotia Hydrographic Network

- Open Government record: <https://open.canada.ca/data/en/dataset/2ed55c68-b7f8-4db0-15d9-bef40797a4c4>
- Publisher: Government of Nova Scotia
- Service used: `WTR_NSHN_UT83/MapServer/16` (`Wet Features`)
- Query class: `FEAT_DESC = 'Lake Water polygon'`
- Folly Lake feature: object 2385, HID `A938C361055748859F18C4E5B3FF36AE`
- Reported source area: 836,901.92 m²; reprojected area: 83.69 ha
- Use: independent nominal hydrographic geometry
- Caveat: the vector is not acquisition-date shoreline truth and may reflect mapping generalization or update lag

The public service is queried at run time. No copy of the source vector is stored in the repository.

### Sentinel-2 Collection 1 Level-2A

- Earth Search STAC API: <https://earth-search.aws.element84.com/v1>
- Collection metadata: <https://earth-search.aws.element84.com/v1/collections/sentinel-2-c1-l2a>
- Selected item: `S2B_T20TMR_20250726T151759_L2A`
- Acquisition: 2025-07-26 15:20:18 UTC
- Platform / tile / CRS: Sentinel-2B / T20TMR / EPSG:32620
- Scene cloud cover: 0.005936%; no SCL-excluded cloud pixels occur in the fixed analysis rectangle
- Pairing: 4.80 hours after the selected 2025-07-26 RCM acquisition
- Assets: B03 green and B08 NIR at 10 m; SCL at 20 m
- Radiometry: Level-2A reflectance scale 0.0001 and offset -0.1 read from STAC raster-band metadata
- Use: independent NDWI water/non-water signal

Only public COG byte ranges for the AOI are read. No full Sentinel-2 tile is downloaded or stored.

## Phase 2 confirmed asset details

- All eight independent acquisitions expose readable public `rr`, `rl`, and `local_inc_angle` Cloud-Optimized GeoTIFF assets.
- The selected windows use EPSG:32620 and an identical 20 m grid over the fixed Phase 2 analysis rectangle.
- All eight acquisitions report relative orbit 37, descending orbit, right-looking acquisition, Level-2 MLC processing, and CEOS ARD `NRB - POL`.
- Platforms represented are RCM2 and RCM3.
- Mean local incidence angle over the analysis rectangle is approximately 27.971°–27.985° across the eight dates.
- The 2025-10-26 and 2025-11-07 searches each return two overlapping catalogue records for one satellite/orbit acquisition. Phase 2 retains one deterministic item per acquisition and does not count the duplicates as separate dates.
- All selected RR and RL windows were read remotely without credentials. No complete satellite scene was downloaded.

## Phase 3 confirmed asset details

- All eight RCM analysis windows share an identical EPSG:32620, 20 m, 110 × 50 grid with zero measured cross-date affine/extent offset.
- Product XML identifies data-mask codes 1, 2, 5, 7, and 9 as valid, invalid, layover, shadow, and layover-shadow respectively. The tested windows contain only codes 1 and 5; Phase 3 retains only code 1.
- Mean local incidence angle spans 27.97080°–27.98475° and mean gamma-to-sigma ratio spans 0.878532–0.878701 across dates.
- Sentinel-2 continuous reflectance is processed at 10 m. Categorical SCL uses nearest-neighbour resampling, and the final water/non-water/unknown class uses mode aggregation onto the native RCM 20 m grid.
- The authoritative vector, Sentinel-2 arrays, and RCM arrays remain remote/in-memory. No large data artifacts were added to Git.

## Phase 4 event data — December 2025 Lower Fraser flood

### NRCan Emergency Geomatics Service flood products

- Public archive: <https://data.eodms-sgdot.nrcan-rncan.gc.ca/public/EGS/2025/Flood/CAN/BC/>
- Product information: <https://natural-resources.canada.ca/science-data/science-research/floods-river-ice-break>
- Product guide: <https://data.eodms-sgdot.nrcan-rncan.gc.ca/public/EGS/EGS_FGP_Geodatabases/Flood_Inondation/EGS_FloodExtent_ProductGuide.pdf>
- Access: anonymous public ZIP download; extracted only in the system temporary directory during notebook execution
- Licence/credit: Government of Canada Open Government Licence terms apply; products are credited as derived from RCM imagery by Natural Resources Canada
- Role: main event-period RCM-derived flood sequence

| Acquisition UTC | Platform | Beam | Polarization | Orbit | Source resolution | Confidence |
| --- | --- | --- | --- | --- | ---: | --- |
| 2025-12-12 14:08:24 | RCM-1 | 5M22 | HH-HV | descending | 5 m | Moderate |
| 2025-12-14 14:24:23 | RCM-1 | 16M9 | HH-HV | descending | 16 m | Moderate |
| 2025-12-15 01:50:37 | RCM-3 | SC30MB | HH-HV | ascending | 30 m | Moderate |
| 2025-12-16 14:08:35 | RCM-2 | 5M22 | HH-HV | descending | 5 m | Moderate |
| 2025-12-17 14:16:34 | RCM-2 | 16M16 | HH-HV | descending | 16 m | Moderate |
| 2025-12-19 01:50:14 | RCM-1 | SC30MB | HH-HV | ascending | 30 m | Moderate |
| 2025-12-21 14:16:46 | RCM-3 | 16M16 | HH-HV | descending | 16 m | Moderate |

Class 1 permanent water and class 2 open-water flood are used. Product footprints define validity. EGS products are operational best-effort flood maps and are not optimized for every urban, forested, or vegetated setting.

### Public RCM CEOS-ARD brackets

- Catalogue/API: <https://www.eodms-sgdot.nrcan-rncan.gc.ca/search>
- Collection: `rcm-ard`
- Access: anonymous public Cloud-Optimized GeoTIFF byte-range reads
- Role: actual RCM pre-event and post-event observations; not substituted for EGS semantic classes
- Common metadata: RCM3, relative orbit 166, ascending, Medium Resolution 30 m, CH/CV/XC, CEOS-ARD representation

Pre-event, 2025-11-08 01:42:39 UTC:

- `cc0e02e8-8d8e-439f-ae81-9173f232fb89`
- `fd241276-682d-4a1b-872c-aaedd88c4a05`

Post-event, 2026-01-07 01:42:38 UTC:

- `16ebbe33-a94e-49b5-b8e8-3bac29612416`
- `b5e0a452-3c67-4a0c-97c6-14d51a9e3c55`

Two adjacent records are mosaicked per date. The `rr`, `data_mask`, `local_inc_angle`, and `gamma_to_sigma_ratio` assets are read. Valid coverage is 96.26% before and 95.81% after; the mutually valid fixed-threshold water areas are 756.84 ha and 727.24 ha. These values are conditional on the Phase 3 CEOS-ARD classifier and are not directly interchangeable with the EGS semantic-area series.

### Sentinel supporting data

Sentinel-2 Collection 1 Level-2A:

- STAC: <https://earth-search.aws.element84.com/v1>
- Pre-event item: `S2B_T10UEV_20251202T190649_L2A`, acquired 2025-12-02 19:10:52 UTC, scene cloud 35.78%
- Recovery item: `S2C_T10UEV_20251227T191058_L2A`, acquired 2025-12-27 19:11:08 UTC, scene cloud 5.13%
- Assets: B03 green and B08 NIR at 10 m; SCL at 20 m
- CRS: source UTM tile is read from asset metadata; categorical results are aggregated to the fixed EPSG:32610 20 m grid
- Access: anonymous public COG byte ranges
- Role: independent optical recovery-period validation and a supporting before/recovery change mask

Sentinel-1 GRD metadata screening found 11 IW VV/VH records intersecting the AOI from 1–28 December 2025. Earth Search supplies Level-1 measurement assets with requester-pays access and calibration/noise XML. They were not forced into the quantitative workflow because a reproducible anonymous calibrated route was unavailable. The coverage result remains documented rather than silently omitted.

### Official event and historical context

- EmergencyInfoBC Fraser Valley East flood warning, updated 2025-12-10: <https://www.emergencyinfobc.gov.bc.ca/event/floodwatch-fraservalley-09122025/>
- City of Abbotsford event summary, 2025-12-23: <https://www.abbotsford.ca/council/your-council-community/blog/abbotsford-shows-resilience-and-compassion-face-disaster>
- Province of British Columbia road update, 2025-12-13: <https://news.gov.bc.ca/releases/2025TT0126-001250>
- Province of British Columbia flood update, 2025-12-14: <https://news.gov.bc.ca/releases/2025EMCR0057-001253>
- Fraser Valley Regional District atmospheric-river update, 2025-12-20: <https://www.fvrd.ca/EN/meta/news/news-archives/2025/atmospheric-river-update-saturday-dec-20.html?media=contrast>

These reports establish event timing, affected communities, evacuations, and regional infrastructure impacts. They are contextual validation and are not used as pixel-level labels.

### Infrastructure context

- Source: OpenStreetMap contributors via the Overpass API
- Query: all ways tagged `highway` in the fixed AOI, with tags and geometry
- Licence: Open Database Licence (ODbL); attribution to OpenStreetMap contributors is required
- Role: preliminary road and bridge intersection screening
- Caveat: completeness and tagging vary; geometric intersection means potential exposure only, not proven damage

No credentials, raw satellite scenes, extracted EGS archives, or road snapshots are stored in Git. The notebook downloads only public products or reads AOI windows at run time.

## Phase 5 impact and context data

### OpenStreetMap roads and bridges

- Source: OpenStreetMap contributors through the Overpass API
- Query: ways tagged `highway` within the Phase 4 WGS84 query envelope; geometries are then reprojected and clipped to the exact EPSG:32610 AOI
- Attributes retained: OSM ID, name, reference, highway, bridge, surface, and access
- Licence: Open Database Licence (ODbL); attribution to OpenStreetMap contributors is required
- Use: line intersection and 50/100/250 m proximity context
- Caveat: coverage and tagging are not guaranteed complete; spatial overlap does not establish damage or closure

The **current committed snapshot contains 234 unique clipped ways**, verified
against `road_exposure.csv` and the archived 238-way Overpass response. The older
232 statement was stale. Fourteen ways still directly intersect over 345.7434 m.
`exposed_roads.geojson` retains only 121 ways within 250 m, not all AOI roads.
The response is preserved as `data/processed/phase5/road_source_snapshot.json`;
its OSM base timestamp is 2026-10-03T20:40:11Z. The cache did not record which
Overpass endpoint succeeded or an exact HTTP retrieval timestamp; neither is
inferred. This is a lightweight ODbL source snapshot, not a new query.

### Official geolocated place names

- Dataset: Geolocated placenames in Canada
- Open Government record: <https://open.canada.ca/data/en/dataset/fe945388-1dd9-4a4a-9a1e-5c552579a28c>
- CSV endpoint: <https://ised-isde.canada.ca/app/scr/sittibc/web/api/openData/MAG_EXO.CSV>
- Publisher/lineage: Innovation, Science and Economic Development Canada; names and coordinates sourced from NRCan's Canadian Geographical Names Database and CIRNAC
- Licence: Open Government Licence — Canada
- Use: named point context and minimum distance to mapped flood gain
- Caveat: points are not settlement boundaries or population surfaces

### B.C. Agricultural Land Reserve

- Dataset record: <https://catalogue.data.gov.bc.ca/dataset/92e17599-ac8a-47c8-877c-107768cb373c>
- ArcGIS layer: <https://delivery.maps.gov.bc.ca/arcgis/rest/services/whse/bcgw_pub_whse_legal_admin_boundaries/MapServer/23>
- Publisher: Government of British Columbia
- Use: intersection of mapped flood gain with ALR-designated polygons
- Result: 36.65 ha, or 66.7% of mapped gain, intersects ALR designation
- Caveat: the ALR is a legal land designation, not observed crop cover; overlap does not prove agricultural damage or loss

### Additional official impact reports

- City of Abbotsford, 11 December 2025, Highway 1 closure and evacuation orders: <https://www.abbotsford.ca/city-hall/news-media/highway-1-closed-between-sumas-way-and-no-3-road-and-evacuation-orders>
- Fraser Valley Regional District / EmergencyInfoBC, 10 December 2025, Wilson Road evacuation order: <https://www.emergencyinfobc.gov.bc.ca/app/uploads/sites/893/2025/12/2025-12-10-Evacuation-ORDER-and-ALERT-Wilson-Road-Area.pdf>

Together with the Phase 4 official sources, these establish the wider event timeline and impact context. They are not used as exact pixel or asset labels.

Phase 5 stores compact derived handoff files, four preserved PNGs and the small
archived Overpass response. No credentials or raw satellite scenes are added.
`source_provenance.json` records retained source identities, scope, hashes and
known omissions. Only the ALR/gain intersection and 25 nearest official place
points are retained; full ALR polygons and a full place inventory are not
available from those exports. Existing exact-retrieval-time/source-version gaps
are disclosed rather than manufactured. Phase 4 WaterOffice records preserve
per-row URLs and unit-value approval fields; they are regional discharge and
water-level context, not temperature or pixel-level truth.

The retained production spatial source is operational RCM-derived EGS. Phase
3B's final experimental Level-1 method failed the GO gate and remains frozen
research evidence. The 20 m EGS accounting grid and 30 m Level-1 research grid
are separate. See [integration audit](phase45-final-integration.md) for the
production-source and recovery-comparison contracts.
