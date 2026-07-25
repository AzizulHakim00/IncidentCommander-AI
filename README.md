# IncidentCommander AI

IncidentCommander AI is a deployable incident-intelligence dashboard that turns raw application and infrastructure logs into anomaly signals, error clusters, ranked probable root causes, and evidence-based response runbooks.

## Features

- Multi-format plain-text log upload
- Timestamp, severity, and service parsing
- TF-IDF log representation
- Isolation Forest anomaly detection
- K-Means error clustering
- Evidence-based root-cause ranking
- Service and severity analytics
- Filterable log explorer
- Downloadable Markdown incident report and analyzed CSV
- Fully local operation with no paid API

## Architecture

```text
Log file
  -> Parser and normalization
  -> TF-IDF feature extraction
  -> Anomaly detection + clustering
  -> Root-cause signature engine
  -> Streamlit dashboard + report export
```

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501` and click **Load demo incident**.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Docker

```bash
docker build -t incidentcommander-ai .
docker run --rm -p 8501:8501 incidentcommander-ai
```

## Deploy to Streamlit Community Cloud

1. Make the repository public or grant Streamlit access to the private repository.
2. Create an app from this repository.
3. Select `app.py` as the entry point.
4. Deploy.

## Model limitations

The root-cause engine ranks probable causes from log evidence; it does not prove causality and does not execute remediation. Production changes must be reviewed by an engineer.

## License

MIT
