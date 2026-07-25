from pathlib import Path


def test_streamlit_entrypoint_has_valid_python_syntax():
    source = Path("app.py").read_text(encoding="utf-8")
    compile(source, "app.py", "exec")
