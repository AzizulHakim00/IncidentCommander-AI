# IncidentCommander AI v5

IncidentCommander AI is an offline-first incident-intelligence platform that turns application, infrastructure, JSON Lines, and structured CSV logs into correlated incident episodes, anomaly signals, service-health scorecards, blast-radius maps, ranked root causes, change-risk evidence, and human-reviewed response plans.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/AzizulHakim00/IncidentCommander-AI)

Live deployment: https://incidentcommander-ai-azizul.onrender.com/

## Live Showcase V5

- Dedicated **Live Incident Studio** multipage experience
- Four deterministic scenarios with 220–260 events each:
  - Database Meltdown
  - Payment Cascade
  - Memory Storm
  - Auth Attack
- Mixed demonstration formats: plain logs, JSON Lines, and structured CSV
- Repository-contained H.264 incident replay video with autoplay and loop controls
- Three custom SVG visual stories: architecture, service blast radius, and incident timeline
- Scenario gallery, animated KPI wall, incident ticker, health charts, and story timeline
- One-click scenario handoff into the full Command Center through Streamlit session state
- Downloadable scenario data for demonstrations and testing
- No external media host, stock-image dependency, or paid API

## Cinematic V4 experience

- Animated aurora background and moving grid atmosphere
- Cinematic landing hero with orbiting AI core and scanning effects
- Animated live-status pulses, severity badges, KPI progress lines, and signal ticker
- Glassmorphism metric cards with hover motion and accent glows
- Executive incident command center with health gauge, severity donut, area timeline, and root-cause confidence
- Animated service health cards with conic health rings
- Rich anomaly heatmap, latency/failure bands, distributed traces, and deployment correlation
- Polished dependency Sankey and blast-radius visualizations
- Evidence-first response center with human-reviewed runbooks and analyst notes
- Responsive mobile behaviour and reduced-motion accessibility fallback
- Markdown, HTML, JSON, executive JSON, and analyzed CSV exports

## Analysis capabilities

- Multi-file ingestion: plain text, JSON Lines, and structured CSV logs
- Metadata extraction: timestamp, severity, service, request ID, trace ID, host, dependency, latency, and status code
- TF-IDF representation, K-Means clustering, and Isolation Forest anomaly detection
- Evidence-backed root-cause ranking across database, authentication, memory, dependencies, DNS, TLS, disk, traffic, exceptions, and deployment regressions
- Correlated incident episodes and cross-service request traces
- Optional deployment/change correlation
- SEV classification, operational-health score, error rate, availability proxy, and P95 latency
- Sensitive-data detection and optional redaction
- Incident fingerprinting, SQLite incident history, and similar-incident comparison
- No paid API and no autonomous production remediation

## Architecture

```text
Generated demo scenarios / uploaded logs / optional change CSV
          ↓
Parser and metadata normalization
          ↓
Redaction and observability audit
          ↓
TF-IDF + clustering + anomaly detection
          ↓
Episode correlation + dependency/blast-radius analysis
          ↓
Presentation analytics + evidence-backed action queue
          ↓
Cinematic command dashboard + live studio + incident memory + reports
```

## Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`. Use **Load cinematic demo** in the Command Center or open **Live Incident Studio** from Streamlit navigation.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

CI validates the analysis engine, parser, correlation, redaction, history, reporting, presentation analytics, Python syntax, cinematic visual contract, scenario generation, SVG media, video packaging, and Live Incident Studio.

## Docker

```bash
docker build -t incidentcommander-ai .
docker run --rm -p 8501:8501 incidentcommander-ai
```

## Deployment

The repository includes a Render Docker Blueprint, Streamlit configuration, health checks, and auto-deploy from `main`.

- Service: `incidentcommander-ai-azizul`
- Runtime: Docker
- Region: Singapore
- Health check: `/_stcore/health`
- Auto-deploy: enabled

## Change correlation CSV

```csv
timestamp,service,change
2026-07-26T04:00:00Z,orders,orders-service v2.4.1 deployment
```

## Safety and limitations

IncidentCommander AI ranks plausible causes from available evidence; it cannot prove causality. Availability, health, and severity values are operational proxies derived from submitted logs. Engineers must verify telemetry, permissions, rollback safety, and business impact before production changes.

## License

MIT
