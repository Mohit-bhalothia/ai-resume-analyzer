from pathlib import Path
from typing import Optional

from .config import get_settings

try:
    import pandas as pd
except Exception as e:  # pragma: no cover - pandas should be installed
    raise ImportError("pandas is required for data loading. Install it via requirements.txt") from e


_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_path(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (_PROJECT_ROOT / path).resolve()


def load_csv(path: Optional[str] = None) -> pd.DataFrame:
    settings = get_settings()
    csv_path = path or getattr(settings, "training_csv_path", None)
    if csv_path is None:
        raise ValueError("No CSV path provided and no default configured.")

    p = _resolve_path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"CSV not found: {p}")

    return pd.read_csv(p)


def load_training_data(path: Optional[str] = None) -> pd.DataFrame:
    settings = get_settings()
    return load_csv(path or settings.training_csv_path)


def load_resumes(path: Optional[str] = None) -> pd.DataFrame:
    settings = get_settings()
    return load_csv(path or settings.resumes_csv_path)


__all__ = ["load_training_data", "load_resumes", "load_csv"]
