# IncidentCommander AI v3

IncidentCommander AI is an offline-first incident-intelligence platform that turns application, infrastructure, JSON Lines, and structured CSV logs into correlated incident episodes, anomaly signals, service-health scorecards, blast-radius maps, ranked root causes, change-risk evidence, and human-reviewed response plans.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/AzizulHakim00/IncidentCommander-AI)

Live deployment: https://incidentcommander-ai-azizul.onrender.com/

## Hybrid V3 experience

- Professional dark operations dashboard with responsive sidebar navigation
- Executive command center with six KPI cards, signal timeline, health gauge, root-cause confidence, and action queue
- Service-level health and impact scorecards
- Risk-intensity heatmap and latency/failure bands
- Cross-service request tracing and correlated incident episodes
- Service dependency Sankey and blast-radius visualization
- Evidence-first response center with investigation notes and human-reviewed runbooks
- Global service scope and analyst-focus controls
- Incident memory, similar-incident retrieval, and current-vs-history comparison
- Observability radar, metadata-quality recommendations, and sensitive-data audit
- Markdown, HTML, JSON, executive JSON, and analyzed CSV exports

## Analysis capabilities

- Multi-file ingestion: plain text, JSON Lines, and structured CSV logs
- Metadata extraction: timestamp, severity, service, request ID, trace ID, host, dependency, latency, and status code
- TF-IDF representation, K-Means clustering, and Isolation Forest anomaly detection
- Evidence-backed root-cause ranking across database, auth, memory, dependencies, DNS, TLS, disk, traffic, exceptions, and deployment regressions
- Optional deployment/change correlation
- SEV classification, operational-health score, error rate, availability proxy, and P95 latency
- Sensitive-data detection and optional redaction
- Incident fingerprinting and SQLite incident history
- No paid API and no autonomous production remediation

## Architecture

```text
Multi-source logs + optional change CSV
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
Hybrid V3 command dashboard + incident memory + reports
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

Open `http://localhost:8501` and select **Load guided demo**.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

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
