import pandas as pd

from incidentcommander.presentation import (
    anomaly_heatmap,
    executive_actions,
    health_band,
    root_cause_table,
    service_scorecards,
)


def sample_frame():
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-07-27T00:00:00Z", "2026-07-27T00:01:00Z"]),
            "service": ["orders", "orders"],
            "level": ["ERROR", "WARN"],
            "is_anomaly": [True, False],
            "status_code": [503, 200],
            "duration_ms": [1500.0, 250.0],
        }
    )


def test_health_band_boundaries():
    assert health_band(90) == "Healthy"
    assert health_band(50) == "High risk"
    assert health_band(10) == "Critical"


def test_service_scorecards_include_health_and_impact():
    blast = pd.DataFrame([{"service": "orders", "impact_score": 88}])
    cards = service_scorecards(sample_frame(), blast)
    assert cards.iloc[0]["impact_score"] == 88
    assert cards.iloc[0]["health_score"] < 100


def test_anomaly_heatmap_and_root_causes():
    heatmap = anomaly_heatmap(sample_frame())
    assert not heatmap.empty
    causes = root_cause_table([{"cause": "Database", "confidence": 0.8, "evidence_hits": 3}])
    assert causes.iloc[0]["confidence_percent"] == 80.0


def test_executive_actions_are_evidence_backed():
    result = {
        "summary": {"severity": "SEV-2", "p95_latency_ms": 1500},
        "root_causes": [{"cause": "Database", "confidence": 0.8, "evidence_hits": 3, "runbook": ["Check DB"]}],
    }
    blast = pd.DataFrame([{"service": "orders", "impact_score": 90}])
    actions = executive_actions(result, blast, pd.DataFrame())
    assert actions[0]["title"].startswith("Validate")
    assert any("latency" in item["title"].lower() for item in actions)
