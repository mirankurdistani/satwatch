# 🛸 SatWatch

**Open source Starlink maneuver detection and conjunction risk monitoring system.**

SatWatch tracks all active Starlink satellites in real time, detects orbital maneuvers by comparing consecutive TLE epochs, calculates conjunction risk between satellite pairs, and presents everything in a live dashboard.

## Why SatWatch?

- SpaceX Starlink performs **50,000+ avoidance maneuvers every 6 months**
- Each maneuver introduces positional uncertainty of up to 40 km for several days
- No open source tool monitors this in real time — until now

## Features

- 📡 Real-time TLE ingestion from Space-Track.org (11,927+ satellites)
- 🚀 Automatic maneuver detection via epoch comparison
- ☄️ Deorbit candidate identification (altitude < 300 km)
- ⚠️ Conjunction risk scoring for satellite pairs
- 📊 Live Streamlit dashboard with pipeline trigger
- 🔄 Automated 4-step pipeline: ingest → analyze → scan → report

## Live Demo

🌍 **[starwatch.streamlit.app](https://starwatch.streamlit.app)** — canlı dashboard, gerçek veri

## Quickstart

```bash
git clone https://github.com/mirankurdistani/satwatch.git
cd satwatch
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your Space-Track credentials to .env
python satwatch_pipeline.py
streamlit run dashboard.py
```

## Data Source

All data sourced from [Space-Track.org](https://www.space-track.org) — the official US Space Surveillance Network catalog, operated by US Space Command.

## License

MIT License — free to use, modify, and distribute.

## Contributing

Pull requests welcome. See [ISSUES](https://github.com/mirankurdistani/satwatch/issues) for planned features.

---

*Built as an open source contribution to space situational awareness. Intended for submission to NASA code.nasa.gov and ESA Space Debris Office.*
