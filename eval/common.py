"""Shared helpers for the Logos eval kit."""
import csv
import importlib.util
import os
import sys
import types
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_DIR = EVAL_DIR.parent
DATA_DIR = EVAL_DIR / "data"
LABELS_DIR = EVAL_DIR / "labels"
RESULTS_DIR = EVAL_DIR / "results"

SAMPLE_CSV = DATA_DIR / "sample.csv"
FALLACY_LABELS_CSV = LABELS_DIR / "fallacy_labels.csv"
CLAIM_LABELS_CSV = LABELS_DIR / "claim_labels.csv"

VERDICTS = ["TRUE", "FALSE", "MISLEADING", "UNVERIFIABLE"]


def _stub_streamlit():
    """Lets milei-logos.py import without Streamlit installed (only its prompts and LLM calls are used)."""
    st = types.ModuleType("streamlit")
    st.cache_data = lambda fn=None, **_: fn if fn else (lambda f: f)
    sys.modules["streamlit"] = st


def load_logos():
    """Import milei-logos.py as a module so the eval uses the exact same prompts and model calls."""
    try:
        import streamlit  # noqa: F401
    except ImportError:
        _stub_streamlit()
    os.chdir(REPO_DIR)  # so load_dotenv() finds the repo's .env
    spec = importlib.util.spec_from_file_location("logos", REPO_DIR / "milei-logos.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
