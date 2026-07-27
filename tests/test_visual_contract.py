from pathlib import Path


def test_cinematic_visual_contract_is_present():
    source = Path("app.py").read_text(encoding="utf-8")
    required_tokens = [
        "Cinematic V4",
        "@keyframes auroraShift",
        "@keyframes orbit",
        "@keyframes tickerMove",
        "ic-orbit",
        "ic-service-card",
        "ic-ticker-track",
        "prefers-reduced-motion",
        "Load cinematic demo",
    ]
    for token in required_tokens:
        assert token in source


def test_cinematic_app_has_valid_python_syntax():
    source = Path("app.py").read_text(encoding="utf-8")
    compile(source, "app.py", "exec")
