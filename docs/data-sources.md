# Data Sources

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
