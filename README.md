# IncidentCommander AI v2

IncidentCommander AI is an offline-first incident-intelligence platform that converts application, infrastructure, and JSON logs into correlated incident episodes, anomaly signals, blast-radius maps, ranked root causes, change-risk evidence, and human-reviewed response runbooks.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/AzizulHakim00/IncidentCommander-AI)

> One-click deployment uses the repository's `render.yaml` and Dockerfile. Sign in to Render with GitHub, review the Blueprint, and approve the deployment.

## V2 capabilities

- Multi-file ingestion: plain text, JSON Lines, and structured CSV logs
- Metadata extraction: timestamp, severity, service, request ID, trace ID, host, dependency, latency, and status code
- TF-IDF representation, K-Means clustering, and Isolation Forest anomaly detection
- Evidence-backed root-cause ranking across database, auth, memory, dependencies, DNS, TLS, disk, traffic, exceptions, and deployment regressions
- Correlated incident episodes and cross-service request traces
- Service dependency Sankey and blast-radius ranking
- Optional deployment/change correlation
- SEV classification, health score, error rate, availability proxy, and P95 latency
- Sensitive-data detection and optional redaction
- Incident fingerprinting, SQLite incident history, and similar-incident retrieval
- Observability-quality score and recommendations
- Markdown, HTML, JSON, and analyzed-CSV exports
- Human-in-the-loop runbook checklist
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
Root-cause evidence engine + runbooks
          ↓
Command dashboard + incident memory + reports
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

Open `http://localhost:8501` and select **Load multi-service demo**.

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

### Render — recommended

Click the **Deploy to Render** button at the top of this README. The Blueprint deploys:

- Repository: `AzizulHakim00/IncidentCommander-AI`
- Branch: `main`
- Runtime: Docker
- Region: Singapore
- Plan: Free
- Health check: `/_stcore/health`
- Auto-deploy: enabled for future pushes to `main`

Expected service name: `incidentcommander-ai-azizul`.

### Streamlit Community Cloud

1. Sign in with GitHub.
2. Select this repository and the `main` branch.
3. Set `app.py` as the entry point.
4. Deploy.

## Change correlation CSV

```csv
timestamp,service,change
2026-07-26T04:00:00Z,orders,orders-service v2.4.1 deployment
```

## Safety and limitations

IncidentCommander AI ranks plausible causes from available evidence; it cannot prove causality. Availability and severity values are log-derived operational proxies. Engineers must verify telemetry, permissions, rollback safety, and business impact before production changes.

## License

MIT
