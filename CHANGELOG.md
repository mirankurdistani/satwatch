# Changelog

## [1.0.0] — 2026-05-22

### Added
- Real-time TLE ingestion from Space-Track.org (11,927+ Starlink satellites)
- Orbital maneuver detection by comparing consecutive TLE epochs
- Deorbit candidate identification (altitude < 300 km threshold)
- Anomaly scoring system based on fleet mean motion deviation
- GP history analysis with delta-v calculation (vis-viva equation)
- Probability of Collision (Pc) calculator based on Chan methodology
- Async conjunction scanner using ThreadPoolExecutor
- 3D interactive globe visualization with Plotly
- Live Streamlit dashboard deployed at starwatch.streamlit.app
- Automated 6-hour pipeline via macOS launchd
- SQLite database with satellites, change_log, conjunction_log tables
- 17 unit tests covering altitude, delta-v, risk, distance calculations
- GitHub Actions CI/CD pipeline
- MIT License, CONTRIBUTING.md, .env.example

### Submitted to
- NASA Open Source (code@nasa.gov) — 2026-05-22
- ESA Space Debris Office (sdo@esa.int) — 2026-05-22
