from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.data_loader import load_training_data, load_resumes
from pydantic import BaseModel
import hashlib
from app.matcher import get_global_matcher
from app.data_loader import load_training_data
import io

try:
    from pdfminer.high_level import extract_text as pdf_extract_text
except ImportError:
    pdf_extract_text = None


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load model and job embeddings at startup so first request is fast."""
    try:
        td = load_training_data()
        if td.shape[0] > 0:
            matcher = get_global_matcher()
            rows = td.fillna("").to_dict(orient="records")
            matcher.fit(rows)
    except Exception:
        pass
    yield
    # shutdown if needed
    pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Basic CORS configuration for local dev; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    """
    Simple health check endpoint.
    """
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@app.get("/", tags=["root"])
def root() -> dict:
    """
    Root endpoint - helpful for quick manual testing.
    """
    return {"message": "AI Resume Analyzer & Job Matcher API"}


@app.get("/debug/datasets", tags=["debug"])
def debug_datasets() -> dict:
    """
    Load configured CSV datasets and return a small summary for local testing.
    """
    def _truncate(val: object, length: int = 300) -> str:
        s = "" if val is None else str(val)
        return s if len(s) <= length else s[:length] + "..."

    try:
        td = load_training_data()
    except Exception as e:
        return {"error": f"failed to load training CSV: {e}"}

    try:
        rd = load_resumes()
    except Exception as e:
        return {"error": f"failed to load resumes CSV: {e}"}

    def _summarize(df):
        return {
            "rows": int(df.shape[0]),
            "cols": list(df.columns),
            "preview": [
                {c: _truncate(v) for c, v in row.items()} for row in df.head(3).fillna("").astype(str).to_dict(orient="records")
            ],
        }

    return {"training": _summarize(td), "resumes": _summarize(rd)}


class MatchRequest(BaseModel):
    # Either provide raw `text` to match, or a `key` (filename|size|mtime) for deterministic fallback.
    key: str | None = None
    text: str | None = None


class CompareRequest(BaseModel):
    resume_text: str
    job_description: str


def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file content."""
    if pdf_extract_text is None:
        raise ValueError("pdfminer.six is not installed")
    try:
        text = pdf_extract_text(io.BytesIO(file_content))
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


@app.post("/debug/match", tags=["debug"]) 
def debug_match(req: MatchRequest) -> dict:
    """Deterministic match: pick a job from training data based on a hashed key.

    This is a lightweight deterministic matcher useful for the dashboard until
    a real resume parser + matching model is wired in.
    """
    try:
        return _debug_match_impl(req)
    except Exception as e:
        return {"error": str(e)}


def _debug_match_impl(req: MatchRequest) -> dict:
    td = load_training_data()
    if td.shape[0] == 0:
        return {"error": "no training data available"}

    matcher = get_global_matcher()
    rows = td.fillna("").to_dict(orient="records")
    matcher.fit(rows)  # No-op if already fitted with same data

    if req.text:
        matches = matcher.match_text(req.text, top_k=1)
        if not matches:
            return {"error": "no matches"}
        m = matches[0]
        # Score is already normalized to 0-100 range
        # Handle both old and new CSV column names
        job_desc = (m.get("job_description") or m.get("description") or "")
        if not job_desc:
            # Build description from new dataset fields
            parts = []
            if m.get("location"):
                parts.append(f"Location: {m.get('location')}")
            if m.get("experience"):
                parts.append(f"Experience: {m.get('experience')}")
            if m.get("skills_required"):
                parts.append(f"Skills: {m.get('skills_required')}")
            if m.get("category"):
                parts.append(f"Category: {m.get('category')}")
            job_desc = " | ".join(parts) if parts else ""
        
        return {
            "index": int(m["index"]),
            "company_name": m.get("company_name", "") or m.get("company", ""),
            "position_title": m.get("position_title", "") or m.get("job_title", "") or m.get("title", ""),
            "job_description": job_desc,
            "score": float(m.get("score", 0)),
        }

    # fallback deterministic hashing by key
    if not req.key:
        return {"error": "provide either `text` or `key`"}

    # Try to resolve `key` to a resume's textual content first (preferred).
    # Look up in the resumes CSV for a matching identifier and common text columns.
    try:
        resumes = load_resumes()
    except Exception:
        resumes = None

    resume_text = None
    if resumes is not None and resumes.shape[0] > 0:
        # try exact match across likely identifier columns
        candidate = None
        key_str = str(req.key)
        # common filename/id columns to try
        id_cols = [c for c in resumes.columns if any(x in c.lower() for x in ("file", "name", "id", "key"))]
        for col in id_cols:
            matches = resumes[resumes[col].astype(str).fillna("").str.contains(key_str, case=False, na=False)]
            if matches.shape[0] > 0:
                candidate = matches.iloc[0]
                break

        # if no id-like column matched, try any column for the key substring
        if candidate is None:
            for col in resumes.columns:
                matches = resumes[resumes[col].astype(str).fillna("").str.contains(key_str, case=False, na=False)]
                if matches.shape[0] > 0:
                    candidate = matches.iloc[0]
                    break

        # Pull text from common text columns (including Resume_str from the CSV)
        if candidate is not None:
            for text_col in ("Resume_str", "resume_str", "text", "resume_text", "content", "parsed_text", "raw_text", "body"):
                if text_col in resumes.columns:
                    v = candidate.get(text_col)
                    if v is not None and str(v).strip() != "":
                        resume_text = str(v)
                        break
            # fallback: try to concatenate likely free-text columns
            if resume_text is None:
                # try columns with long strings
                long_cols = [c for c in resumes.columns if resumes[c].astype(str).map(len).median() > 50]
                if long_cols:
                    parts = [str(candidate.get(c, "")) for c in long_cols]
                    resume_text = "\n".join([p for p in parts if p])

    # If we found resume text, perform semantic matching using the global matcher
    if resume_text:
        matches = matcher.match_text(resume_text, top_k=1)
        if not matches:
            return {"error": "no matches"}
        m = matches[0]
        # Handle both old and new CSV column names
        job_desc = (m.get("job_description") or m.get("description") or "")
        if not job_desc:
            parts = []
            if m.get("location"):
                parts.append(f"Location: {m.get('location')}")
            if m.get("experience"):
                parts.append(f"Experience: {m.get('experience')}")
            if m.get("skills_required"):
                parts.append(f"Skills: {m.get('skills_required')}")
            if m.get("category"):
                parts.append(f"Category: {m.get('category')}")
            job_desc = " | ".join(parts) if parts else ""
        
        return {
            "index": int(m["index"]),
            "company_name": m.get("company_name", "") or m.get("company", ""),
            "position_title": m.get("position_title", "") or m.get("job_title", "") or m.get("title", ""),
            "job_description": job_desc,
            "score": float(m.get("score", 0)),
        }

    # If we couldn't find resume text, fall back to deterministic hashing (legacy behavior)
    h = hashlib.sha256(req.key.encode("utf-8")).digest()
    idx = int.from_bytes(h, "big") % int(td.shape[0])
    row = td.iloc[int(idx)]
    score = 40 + (int.from_bytes(h, "big") % 61)  # deterministic 40-100

    # Handle both old and new CSV column names
    job_desc = str(row.get("job_description", "") or row.get("description", ""))
    if not job_desc:
        parts = []
        if row.get("location"):
            parts.append(f"Location: {row.get('location')}")
        if row.get("experience"):
            parts.append(f"Experience: {row.get('experience')}")
        if row.get("skills_required"):
            parts.append(f"Skills: {row.get('skills_required')}")
        if row.get("category"):
            parts.append(f"Category: {row.get('category')}")
        job_desc = " | ".join(parts) if parts else ""
    
    return {
        "index": int(idx),
        "company_name": str(row.get("company_name", "") or row.get("company", "")),
        "position_title": str(row.get("position_title", "") or row.get("job_title", "") or row.get("title", "")),
        "job_description": job_desc[:800],
        "score": int(score),
    }


@app.post("/api/parse-pdf", tags=["api"])
async def parse_pdf(file: UploadFile = File(...)) -> dict:
    """Parse a PDF file and extract text."""
    if not file.filename.endswith('.pdf'):
        return {"error": "File must be a PDF"}
    
    try:
        content = await file.read()
        text = extract_text_from_pdf(content)
        return {
            "filename": file.filename,
            "text": text,
            "text_length": len(text)
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/match-jobs", tags=["api"])
def match_jobs(req: MatchRequest) -> dict:
    """Get top job matches for a resume. Returns top 5 matches for better variety."""
    td = load_training_data()
    if td.shape[0] == 0:
        return {"error": "no training data available", "matches": []}

    matcher = get_global_matcher()
    rows = td.fillna("").to_dict(orient="records")
    matcher.fit(rows)  # No-op if already fitted with same data

    resume_text = None
    
    # If text is provided directly, use it
    if req.text:
        resume_text = req.text
    # Otherwise, try to find resume text from CSV using key
    elif req.key:
        try:
            resumes = load_resumes()
            if resumes is not None and resumes.shape[0] > 0:
                key_str = str(req.key)
                candidate = None
                # Try to match by ID or filename
                id_cols = [c for c in resumes.columns if any(x in c.lower() for x in ("file", "name", "id", "key"))]
                for col in id_cols:
                    matches = resumes[resumes[col].astype(str).fillna("").str.contains(key_str, case=False, na=False)]
                    if matches.shape[0] > 0:
                        candidate = matches.iloc[0]
                        break
                
                # Extract resume text
                if candidate is not None:
                    for text_col in ("Resume_str", "resume_str", "text", "resume_text", "content", "parsed_text", "raw_text", "body"):
                        if text_col in resumes.columns:
                            v = candidate.get(text_col)
                            if v is not None and str(v).strip() != "":
                                resume_text = str(v)
                                break
        except Exception:
            pass

    if not resume_text:
        return {"error": "could not extract resume text", "matches": []}

    # Get top 5 matches for better variety
    matches = matcher.match_text(resume_text, top_k=5)
    return {
        "matches": [
            {
                "index": int(m["index"]),
                "company_name": m.get("company_name", "") or m.get("company", ""),
                "position_title": m.get("position_title", "") or m.get("job_title", "") or m.get("title", ""),
                "job_description": m.get("job_description", "") or m.get("description", "")[:500],
                "score": float(m.get("score", 0)),
            }
            for m in matches
        ]
    }


@app.post("/api/compare-cv-jd", tags=["api"])
def compare_cv_jd(req: CompareRequest) -> dict:
    """Compare a CV/resume with a specific job description and return match score."""
    matcher = get_global_matcher()
    result = matcher.compare_with_jd(req.resume_text, req.job_description)
    return result


@app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
def dashboard() -> str:
    """
    Simple interactive dashboard for local use.
    """
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <title>AI Resume Analyzer Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
            :root {
                --bg: #050816;
                --bg-alt: #0f172a;
                --card: #020617;
                --accent: #22c55e;
                --accent-soft: rgba(34, 197, 94, 0.15);
                --accent-2: #6366f1;
                --text: #e5e7eb;
                --muted: #9ca3af;
                --border: #1f2933;
                --error: #f97373;
            }
            * { box-sizing: border-box; }
            body {
                margin: 0;
                font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background: radial-gradient(circle at top left, #1e293b 0, #020617 35%, #020617 100%);
                color: var(--text);
            }
            .shell {
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 32px 16px;
            }
            .layout {
                width: 100%;
                max-width: 1120px;
                display: grid;
                grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
                gap: 24px;
            }
            @media (max-width: 900px) {
                .layout {
                    grid-template-columns: minmax(0, 1fr);
                }
            }
            .card {
                background: linear-gradient(145deg, rgba(15,23,42,0.96), rgba(15,23,42,0.98));
                border-radius: 18px;
                padding: 20px 20px 18px;
                border: 1px solid rgba(148,163,184,0.15);
                box-shadow:
                    0 28px 80px rgba(15,23,42,0.85),
                    0 0 0 1px rgba(15,23,42,0.8);
                position: relative;
                overflow: hidden;
            }
            .card::before {
                content: "";
                position: absolute;
                inset: -40%;
                background:
                    radial-gradient(circle at 0 0, rgba(59,130,246,0.14) 0, transparent 50%),
                    radial-gradient(circle at 100% 0, rgba(34,197,94,0.13) 0, transparent 55%);
                opacity: 0.7;
                pointer-events: none;
            }
            .card-inner {
                position: relative;
                z-index: 1;
            }
            .heading {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 8px;
                margin-bottom: 14px;
            }
            .title {
                font-size: 22px;
                font-weight: 650;
                letter-spacing: 0.02em;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .pill {
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 999px;
                border: 1px solid rgba(148,163,184,0.55);
                color: var(--muted);
                background: linear-gradient(120deg, rgba(15,23,42,0.9), rgba(15,23,42,0.5));
            }
            .subtitle {
                font-size: 13px;
                color: var(--muted);
            }
            .badge-row {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                margin: 10px 0 16px;
            }
            .badge {
                padding: 4px 9px;
                border-radius: 999px;
                font-size: 11px;
                display: inline-flex;
                align-items: center;
                gap: 4px;
                border: 1px solid rgba(148,163,184,0.4);
                background: rgba(15,23,42,0.9);
                color: var(--muted);
            }
            .badge-dot {
                width: 6px;
                height: 6px;
                border-radius: 999px;
                background: var(--accent);
            }
            .badge-dot.secondary {
                background: var(--accent-2);
            }
            .upload-zone {
                margin-top: 8px;
                padding: 16px;
                border-radius: 16px;
                border: 1px dashed rgba(148,163,184,0.5);
                background: radial-gradient(circle at top left, rgba(34,197,94,0.09), rgba(15,23,42,0.85));
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .upload-row {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: 10px;
            }
            .file-input {
                position: relative;
                overflow: hidden;
                display: inline-flex;
            }
            .file-input input[type="file"] {
                position: absolute;
                inset: 0;
                opacity: 0;
                cursor: pointer;
            }
            .btn {
                border: none;
                border-radius: 999px;
                padding: 9px 16px;
                font-size: 13px;
                font-weight: 550;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                cursor: pointer;
                transition: transform 0.1s ease, box-shadow 0.1s ease, background 0.15s ease;
                white-space: nowrap;
            }
            .btn-primary {
                background: linear-gradient(135deg, var(--accent), #4ade80);
                color: #022c22;
                box-shadow: 0 10px 30px rgba(16,185,129,0.45);
            }
            .btn-primary:hover {
                transform: translateY(-1px);
                box-shadow: 0 14px 40px rgba(16,185,129,0.55);
            }
            .btn-ghost {
                background: rgba(15,23,42,0.7);
                border: 1px solid rgba(148,163,184,0.5);
                color: var(--muted);
            }
            .btn-ghost:hover {
                background: rgba(15,23,42,0.9);
            }
            .btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                box-shadow: none;
                transform: none;
            }
            .hint {
                font-size: 11px;
                color: var(--muted);
            }
            .status-chip {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 5px 10px;
                border-radius: 999px;
                background: var(--accent-soft);
                color: #bbf7d0;
                font-size: 11px;
            }
            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 999px;
                background: var(--accent);
                box-shadow: 0 0 0 4px rgba(34,197,94,0.25);
            }
            .status-chip.error {
                background: rgba(248,113,113,0.14);
                color: #fecaca;
            }
            .status-chip.error .status-dot {
                background: var(--error);
                box-shadow: 0 0 0 4px rgba(248,113,113,0.2);
            }
            .status-row {
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
                gap: 10px;
                margin-top: 14px;
            }
            .status-label {
                font-size: 12px;
                color: var(--muted);
            }
            .score-card {
                background: radial-gradient(circle at top, rgba(37,99,235,0.42), rgba(15,23,42,0.98));
                border-radius: 16px;
                padding: 12px 14px 14px;
                border: 1px solid rgba(129,140,248,0.4);
                position: relative;
                overflow: hidden;
            }
            .score-card::before {
                content: "";
                position: absolute;
                inset: 0;
                background:
                    radial-gradient(circle at 15% 0, rgba(59,130,246,0.55) 0, transparent 45%),
                    radial-gradient(circle at 90% 0, rgba(236,72,153,0.4) 0, transparent 55%);
                opacity: 0.35;
                mix-blend-mode: screen;
                pointer-events: none;
            }
            .score-inner {
                position: relative;
                z-index: 1;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
            }
            .score-main {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .score-circle {
                width: 62px;
                height: 62px;
                border-radius: 50%;
                background:
                    conic-gradient(from 220deg, #4ade80 0 var(--score-deg, 40deg), rgba(31,41,55,0.8) var(--score-deg, 40deg) 360deg);
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 16px 40px rgba(22,163,74,0.7);
            }
            .score-circle-inner {
                width: 75%;
                height: 75%;
                border-radius: 50%;
                background: rgba(15,23,42,0.96);
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
            }
            .score-value {
                font-size: 20px;
                font-weight: 650;
            }
            .score-label {
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.12em;
                color: #a5b4fc;
            }
            .score-meta {
                font-size: 12px;
                color: #c7d2fe;
            }
            .score-meta span {
                display: block;
                color: rgba(191,219,254,0.8);
            }
            .score-tags {
                display: inline-flex;
                flex-wrap: wrap;
                gap: 6px;
                margin-top: 6px;
            }
            .score-tag {
                font-size: 10px;
                padding: 3px 8px;
                border-radius: 999px;
                border: 1px solid rgba(129,140,248,0.7);
                background: rgba(15,23,42,0.88);
                color: #e0e7ff;
            }
            .panel {
                display: flex;
                flex-direction: column;
                gap: 10px;
                margin-top: 16px;
            }
            .panel-label {
                font-size: 12px;
                color: var(--muted);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .panel-pill {
                padding: 3px 8px;
                border-radius: 999px;
                font-size: 10px;
                background: rgba(15,23,42,0.9);
                border: 1px solid rgba(148,163,184,0.4);
                color: var(--muted);
            }
            .panel-body {
                background: rgba(15,23,42,0.95);
                border-radius: 12px;
                border: 1px solid rgba(30,64,175,0.55);
                padding: 10px 12px;
                min-height: 90px;
                font-size: 12px;
                color: #e5e7eb;
                display: flex;
                flex-direction: column;
                gap: 6px;
            }
            .panel-body p {
                margin: 0;
            }
            .panel-body ul {
                margin: 0;
                padding-left: 16px;
            }
            .panel-body li {
                margin-bottom: 2px;
            }
            .log {
                max-height: 160px;
                overflow-y: auto;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                font-size: 11px;
                color: var(--muted);
            }
            .log-line {
                padding: 3px 0;
                border-bottom: 1px dashed rgba(55,65,81,0.6);
            }
            .log-line:last-child {
                border-bottom: none;
            }
            .log-time {
                color: rgba(148,163,184,0.9);
                margin-right: 4px;
            }
            .log-label {
                color: #e5e7eb;
            }
            .log-ok {
                color: #4ade80;
            }
            .log-error {
                color: #f97373;
            }
            .aside {
                display: flex;
                flex-direction: column;
                gap: 16px;
            }
            .aside-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 4px;
            }
            .aside-title {
                font-size: 14px;
                font-weight: 550;
            }
            .chip {
                font-size: 10px;
                padding: 3px 8px;
                border-radius: 999px;
                border: 1px solid rgba(148,163,184,0.5);
                color: var(--muted);
                background: rgba(15,23,42,0.9);
            }
            .list {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            .list-item {
                padding: 10px 12px;
                border-radius: 12px;
                background: radial-gradient(circle at 0 0, rgba(56,189,248,0.22), rgba(15,23,42,0.96));
                border: 1px solid rgba(59,130,246,0.6);
            }
            .list-item:nth-child(2) {
                background: radial-gradient(circle at 0 0, rgba(34,197,94,0.2), rgba(15,23,42,0.96));
                border-color: rgba(22,163,74,0.6);
            }
            .list-item:nth-child(3) {
                background: radial-gradient(circle at 0 0, rgba(244,114,182,0.22), rgba(15,23,42,0.96));
                border-color: rgba(219,39,119,0.6);
            }
            .list-title {
                font-size: 13px;
                font-weight: 540;
            }
            .list-sub {
                font-size: 11px;
                color: var(--muted);
                margin-top: 2px;
            }
            .list-meta {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 8px;
                font-size: 11px;
                color: rgba(191,219,254,0.9);
            }
            .list-tag-row {
                display: flex;
                flex-wrap: wrap;
                gap: 4px;
            }
            .list-tag {
                font-size: 10px;
                padding: 3px 7px;
                border-radius: 999px;
                background: rgba(15,23,42,0.9);
                border: 1px solid rgba(148,163,184,0.4);
                color: rgba(209,213,219,0.96);
            }
            .footer {
                margin-top: 14px;
                font-size: 11px;
                color: var(--muted);
                display: flex;
                justify-content: space-between;
                gap: 8px;
                flex-wrap: wrap;
            }
            .footer a {
                color: #60a5fa;
                text-decoration: none;
            }
            .footer a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="shell">
            <div class="layout">
                <section class="card">
                    <div class="card-inner">
                        <div class="heading">
                            <div>
                                <div class="title">
                                    AI Resume Analyzer
                                    <span class="pill">Local dev dashboard</span>
                                </div>
                                <div class="subtitle">
                                    Upload a resume, preview an ATS-style score, and ping the API health in one place.
                                </div>
                            </div>
                        </div>

                        <div class="badge-row">
                            <span class="badge">
                                <span class="badge-dot"></span>
                                FastAPI · Python
                            </span>
                            <span class="badge">
                                <span class="badge-dot secondary"></span>
                                spaCy · Transformers
                            </span>
                            <span class="badge">
                                <span class="badge-dot secondary"></span>
                                Admin/job matching ready
                            </span>
                        </div>

                        <div class="upload-zone">
                            <div class="upload-row">
                                <div class="file-input">
                                    <button class="btn btn-ghost" type="button">
                                        <span>Choose PDF resume</span>
                                    </button>
                                    <input id="resumeFile" type="file" accept="application/pdf" />
                                </div>
                                <button id="analyzeBtn" class="btn btn-primary" type="button">
                                    <span>Analyze (demo)</span>
                                </button>
                                <button id="healthBtn" class="btn btn-ghost" type="button">
                                    Check API health
                                </button>
                            </div>
                            <div class="hint" id="fileHint">
                                No file selected yet. This demo keeps everything in the browser; backend parsing endpoints can be added later.
                            </div>
                        </div>

                        <div class="status-row">
                            <div class="status-label">
                                Backend status
                                <div id="statusChip" class="status-chip">
                                    <span class="status-dot"></span>
                                    Idle – click “Check API health”
                                </div>
                            </div>
                            <div class="status-label">
                                Last action
                                <span id="lastAction" class="pill">None yet</span>
                            </div>
                        </div>

                        <div class="score-card" style="margin-top: 16px;">
                            <div class="score-inner">
                                <div class="score-main">
                                    <div class="score-circle" id="scoreCircle" style="--score-deg: 120deg;">
                                        <div class="score-circle-inner">
                                            <div id="scoreValue" class="score-value">–</div>
                                            <div class="score-label">ATS Score</div>
                                        </div>
                                    </div>
                                    <div>
                                        <div id="scoreHeadline" class="score-meta">
                                            Upload a resume to simulate scoring.
                                        </div>
                                        <div class="score-tags" id="scoreTags">
                                            <span class="score-tag">Skills coverage</span>
                                            <span class="score-tag">JD similarity</span>
                                            <span class="score-tag">Experience match</span>
                                        </div>
                                    </div>
                                </div>
                                <div>
                                    <div class="panel-label" style="margin-bottom: 6px;">
                                        Quick controls
                                    </div>
                                    <button id="resetBtn" class="btn btn-ghost" type="button" style="width: 100%; justify-content: center;">
                                        Reset dashboard state
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div class="panel">
                            <div class="panel-label">
                                Request log
                                <span class="panel-pill">Browser → FastAPI</span>
                            </div>
                            <div class="panel-body log" id="log">
                                <div class="log-line">
                                    <span class="log-time">–</span>
                                    <span class="log-label">Dashboard ready.</span>
                                    <span> Use the buttons above to talk to your API.</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <aside class="aside">
                    <section class="card">
                        <div class="card-inner">
                            <div class="aside-header">
                                <div class="aside-title">Job Matches</div>
                                <span class="chip">AI-powered</span>
                            </div>
                            <div class="subtitle" style="margin-bottom: 10px;">
                                Top job matches based on your resume content.
                            </div>
                            <div class="list" id="jobMatchesList">
                                <div class="list-item">
                                    <div class="list-sub">Upload and analyze a resume to see job matches.</div>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section class="card">
                        <div class="card-inner">
                            <div class="aside-header">
                                <div class="aside-title">Compare CV with Job Description</div>
                                <span class="chip">Custom JD</span>
                            </div>
                            <div class="subtitle" style="margin-bottom: 10px;">
                                Paste a job description to see how your CV matches.
                            </div>
                            <div class="upload-zone" style="margin-top: 10px;">
                                <textarea id="jobDescriptionInput" placeholder="Paste job description here..." style="width: 100%; min-height: 120px; padding: 10px; border-radius: 8px; border: 1px solid rgba(148,163,184,0.5); background: rgba(15,23,42,0.9); color: var(--text); font-size: 12px; font-family: inherit; resize: vertical;"></textarea>
                                <button id="compareBtn" class="btn btn-primary" type="button" style="width: 100%; margin-top: 8px;">
                                    Compare with CV
                                </button>
                            </div>
                            <div id="compareResult" style="margin-top: 12px; display: none;">
                                <div class="score-card">
                                    <div class="score-inner">
                                        <div class="score-main">
                                            <div class="score-circle" id="compareScoreCircle" style="--score-deg: 120deg;">
                                                <div class="score-circle-inner">
                                                    <div id="compareScoreValue" class="score-value">–</div>
                                                    <div class="score-label">Match</div>
                                                </div>
                                            </div>
                                            <div>
                                                <div id="compareScoreHeadline" class="score-meta">
                                                    Comparison result will appear here.
                                                </div>
                                                <div id="compareMatchLevel" class="score-tags"></div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section class="card">
                        <div class="card-inner">
                            <div class="aside-header">
                                <div class="aside-title">How this is wired</div>
                                <span class="chip">Dev hints</span>
                            </div>
                            <div class="panel-body">
                                <p style="font-size: 11px;">
                                    This dashboard is a single FastAPI route (<code>/dashboard</code>) that returns HTML + CSS + JS.
                                    It already talks to the backend via <code>/health</code>.
                                </p>
                                <ul style="font-size: 11px;">
                                    <li>Hook a real resume parsing endpoint to the “Analyze” button.</li>
                                    <li>Stream scores & job matches into the tiles on the left.</li>
                                    <li>Extend this panel with admin‑only actions (create/update jobs).</li>
                                </ul>
                            </div>
                            <div class="footer">
                                <span>Open API docs at <code>/docs</code> for more endpoints.</span>
                            </div>
                        </div>
                    </section>
                </aside>
            </div>
        </div>

        <script>
            const healthBtn = document.getElementById("healthBtn");
            const analyzeBtn = document.getElementById("analyzeBtn");
            const resetBtn = document.getElementById("resetBtn");
            const resumeFile = document.getElementById("resumeFile");
            const fileHint = document.getElementById("fileHint");
            const statusChip = document.getElementById("statusChip");
            const lastAction = document.getElementById("lastAction");
            const logEl = document.getElementById("log");
            const scoreCircle = document.getElementById("scoreCircle");
            const scoreValue = document.getElementById("scoreValue");
            const scoreHeadline = document.getElementById("scoreHeadline");
            const scoreTags = document.getElementById("scoreTags");
            const compareBtn = document.getElementById("compareBtn");
            const jobDescriptionInput = document.getElementById("jobDescriptionInput");
            const compareResult = document.getElementById("compareResult");
            const compareScoreCircle = document.getElementById("compareScoreCircle");
            const compareScoreValue = document.getElementById("compareScoreValue");
            const compareScoreHeadline = document.getElementById("compareScoreHeadline");
            const compareMatchLevel = document.getElementById("compareMatchLevel");

            const appendLog = (label, detail, kind = "info") => {
                const now = new Date();
                const time = now.toLocaleTimeString();
                const line = document.createElement("div");
                line.className = "log-line";
                const spanTime = document.createElement("span");
                spanTime.className = "log-time";
                spanTime.textContent = time;
                const spanLabel = document.createElement("span");
                spanLabel.className = "log-label";
                spanLabel.textContent = " " + label + " ";
                const spanDetail = document.createElement("span");
                spanDetail.textContent = detail || "";
                if (kind === "ok") {
                    spanDetail.classList.add("log-ok");
                } else if (kind === "error") {
                    spanDetail.classList.add("log-error");
                }
                line.appendChild(spanTime);
                line.appendChild(spanLabel);
                line.appendChild(spanDetail);
                logEl.appendChild(line);
                logEl.scrollTop = logEl.scrollHeight;
            };

            const setStatus = (text, ok = true) => {
                statusChip.textContent = "";
                statusChip.classList.toggle("error", !ok);
                const dot = document.createElement("span");
                dot.className = "status-dot";
                statusChip.appendChild(dot);
                const t = document.createTextNode(" " + text);
                statusChip.appendChild(t);
            };

            const setScore = (score, circleEl = scoreCircle, valueEl = scoreValue, headlineEl = scoreHeadline) => {
                if (isNaN(score)) {
                    valueEl.textContent = "–";
                    circleEl.style.setProperty("--score-deg", "40deg");
                    headlineEl.textContent = "Upload a resume to simulate scoring.";
                    return;
                }
                const clamped = Math.max(0, Math.min(100, score));
                const deg = (clamped / 100) * 320 + 40;
                circleEl.style.setProperty("--score-deg", deg + "deg");
                valueEl.textContent = Math.round(clamped).toString();
                if (clamped >= 80) {
                    headlineEl.textContent = "Great match! This profile should stand out for most job filters.";
                } else if (clamped >= 60) {
                    headlineEl.textContent = "Solid fit. A few targeted tweaks could push this into the top tier.";
                } else if (clamped >= 40) {
                    headlineEl.textContent = "Moderate match. Consider sharpening skills & keywords for the target role.";
                } else {
                    headlineEl.textContent = "Low match. Use this as a baseline and expand relevant experience/skills.";
                }
            };

            let lastMatch = null;
            let lastFileKey = null;

            // deterministic client-side hash (fallback) — simple djb2
            const deterministicScoreFromKey = (key) => {
                let h = 5381;
                for (let i = 0; i < key.length; i++) {
                    h = ((h << 5) + h) + key.charCodeAt(i);
                    h = h & 0xffffffff;
                }
                return 40 + (Math.abs(h) % 61);
            };

            const updateJobMatchesFromData = (matches) => {
                const jobListEl = document.getElementById("jobMatchesList");
                if (!jobListEl) return;
                
                if (matches && matches.length > 0) {
                    jobListEl.innerHTML = '';
                    matches.forEach((match, idx) => {
                        const item = document.createElement('div');
                        item.className = 'list-item';
                        // Extract some keywords from job description for tags
                        const desc = (match.job_description || '').toLowerCase();
                        // Extract meaningful words (length > 4, not common stop words)
                        const stopWords = ['the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'will', 'your', 'work', 'team'];
                        const words = desc.split(/[\\s,\\.;:()]+/).filter(w => 
                            w.length > 4 && !stopWords.includes(w.toLowerCase())
                        ).slice(0, 4);
                        
                        const score = typeof match.score === 'number' ? match.score.toFixed(1) : match.score;
                        item.innerHTML = `
                            <div class="list-title">${(match.position_title || 'Position').substring(0, 50)} · ${(match.company_name || 'Company').substring(0, 30)}</div>
                            <div class="list-sub">${(match.job_description || '').substring(0, 120)}...</div>
                            <div class="list-meta">
                                <div class="list-tag-row">
                                    ${words.map(t => `<span class="list-tag">${t}</span>`).join('')}
                                </div>
                                <div>Match: <strong>${score}%</strong></div>
                            </div>
                        `;
                        jobListEl.appendChild(item);
                    });
                } else {
                    jobListEl.innerHTML = '<div class="list-item"><div class="list-sub">No matches found. Try analyzing a resume first.</div></div>';
                }
            };

            const updateJobMatches = async (key) => {
                const jobListEl = document.getElementById("jobMatchesList");
                if (!jobListEl) return;
                
                try {
                    const res = await fetch('/api/match-jobs', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ key })
                    });
                    const data = await res.json();
                    updateJobMatchesFromData(data.matches || []);
                } catch (err) {
                    console.error('Failed to load job matches:', err);
                    jobListEl.innerHTML = '<div class="list-item"><div class="list-sub">Error loading matches.</div></div>';
                }
            };

            resumeFile.addEventListener("change", () => {
                const file = resumeFile.files[0];
                if (!file) {
                    fileHint.textContent = "No file selected yet. This demo keeps everything in the browser.";
                    return;
                }
                // Do NOT call the matcher here. Only update UI; user must click Analyze.
                fileHint.textContent = "Selected: " + file.name + " (" + (file.size / 1024).toFixed(1) + " KB)";
                lastAction.textContent = "Selected resume file";
                appendLog("File", "Selected " + file.name);
                // clear any previous match so Analyze will request a fresh match
                lastMatch = null;
                lastFileKey = null;
                // reset score visuals until Analyze is clicked
                setScore(NaN);
                setStatus("Ready to analyze — click Analyze", true);
                // Reset job matches
                const jobListEl = document.getElementById("jobMatchesList");
                if (jobListEl) {
                    jobListEl.innerHTML = '<div class="list-item"><div class="list-sub">Upload and analyze a resume to see job matches.</div></div>';
                }
            });

            healthBtn.addEventListener("click", async () => {
                setStatus("Pinging /health…", true);
                lastAction.textContent = "Checking API health";
                appendLog("Request", "GET /health");
                try {
                    const res = await fetch("/health");
                    const data = await res.json();
                    if (data && data.status === "ok") {
                        setStatus("API is healthy · " + (data.environment || "dev"), true);
                        appendLog("Response", "status=ok environment=" + (data.environment || "n/a"), "ok");
                    } else {
                        setStatus("API responded unexpectedly", false);
                        appendLog("Response", "Unexpected payload from /health", "error");
                    }
                } catch (err) {
                    console.error(err);
                    setStatus("Failed to reach API", false);
                    appendLog("Error", "Could not reach /health (" + err + ")", "error");
                }
            });

            analyzeBtn.addEventListener("click", async () => {
                const file = resumeFile.files[0];
                if (!file) {
                    appendLog("Analyze", "No file selected – using demo score", "error");
                    lastAction.textContent = "Tried to analyze without file";
                    setScore( deterministicScoreFromKey((new Date()).toString()) );
                    return;
                }
                
                lastAction.textContent = "Analyzing resume...";
                setStatus("Analyzing...", true);
                
                // Always extract text from PDF - never use filename-based matching
                // This ensures accurate matching based on CV content
                let resumeText = null;
                try {
                    const formData = new FormData();
                    formData.append('file', file);
                    appendLog("Parse", "Extracting text from PDF...", "info");
                    const parseRes = await fetch('/api/parse-pdf', {
                        method: 'POST',
                        body: formData
                    });
                    const parseData = await parseRes.json();
                    if (parseData && parseData.text && parseData.text.trim().length > 50) {
                        resumeText = parseData.text;
                        appendLog("Parse", `Extracted ${parseData.text_length} chars from PDF`, "ok");
                    } else {
                        appendLog("Parse", "PDF text extraction failed or too short", "error");
                    }
                } catch (err) {
                    appendLog("Parse", "PDF parsing failed: " + err, "error");
                }

                // Must have resume text to proceed - no fallback to filename hashing
                if (!resumeText || resumeText.trim().length < 50) {
                    setScore(NaN);
                    appendLog("Analyze", "Could not extract sufficient text from PDF. Please ensure the PDF contains readable text.", "error");
                    setStatus("Analysis failed - PDF text extraction failed", false);
                    return;
                }

                // Always use resume text for matching - ensures content-based accuracy
                try {
                    const res = await fetch('/debug/match', {
                        method: 'POST', 
                        headers: { 'Content-Type': 'application/json' }, 
                        body: JSON.stringify({ text: resumeText })
                    });
                    const text = await res.text();
                    let data;
                    try {
                        data = JSON.parse(text);
                    } catch (_) {
                        appendLog("Analyze", "Server error: " + (text || res.statusText || "Internal Server Error"), "error");
                        setScore(NaN);
                        appendLog("Analyze", "Failed to match resume with jobs", "error");
                        setStatus("Analysis failed", false);
                        return;
                    }
                    if (data && !data.error) {
                        lastMatch = data;
                        // Store resume text hash for cache checking (content-based, not filename)
                        lastFileKey = btoa(resumeText.substring(0, 100)).substring(0, 50);
                        setScore(data.score);
                        appendLog("Analyze", `Matched score=${data.score.toFixed(1)}% idx=${data.index}`, "ok");
                        
                        // Get top 5 job matches for better variety
                        const jobsRes = await fetch('/api/match-jobs', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ text: resumeText })
                        });
                        const jobsText = await jobsRes.text();
                        let jobsData;
                        try {
                            jobsData = JSON.parse(jobsText);
                        } catch (_) {
                            appendLog("Jobs", "Server returned invalid response", "error");
                            jobsData = { matches: [] };
                        }
                        if (jobsData && jobsData.matches && jobsData.matches.length > 0) {
                            updateJobMatchesFromData(jobsData.matches);
                            appendLog("Jobs", `Found ${jobsData.matches.length} job matches`, "ok");
                        } else {
                            appendLog("Jobs", "No job matches found", "error");
                        }
                        setStatus("Analysis complete", true);
                        return;
                    } else {
                        appendLog("Analyze", "Server error: " + (data.error || "unknown"), "error");
                    }
                } catch (err) {
                    appendLog("Analyze", "Request failed: " + err, "error");
                }

                // If matching fails, show error
                setScore(NaN);
                appendLog("Analyze", "Failed to match resume with jobs", "error");
                setStatus("Analysis failed", false);
            });

            resetBtn.addEventListener("click", () => {
                resumeFile.value = "";
                fileHint.textContent = "No file selected yet. This demo keeps everything in the browser; backend parsing endpoints can be added later.";
                lastAction.textContent = "Dashboard reset";
                setStatus("Idle – click “Check API health”", true);
                scoreTags.innerHTML = "";
                ["Skills coverage", "JD similarity", "Experience match"].forEach((label) => {
                    const span = document.createElement("span");
                    span.className = "score-tag";
                    span.textContent = label;
                    scoreTags.appendChild(span);
                });
                setScore(NaN);
                lastMatch = null;
                lastFileKey = null;
                // Reset job matches
                const jobListEl = document.getElementById("jobMatchesList");
                if (jobListEl) {
                    jobListEl.innerHTML = '<div class="list-item"><div class="list-sub">Upload and analyze a resume to see job matches.</div></div>';
                }
                appendLog("System", "Dashboard state reset");
            });

            // Compare CV with Job Description
            compareBtn.addEventListener("click", async () => {
                const file = resumeFile.files[0];
                const jdText = jobDescriptionInput.value.trim();
                
                if (!jdText) {
                    appendLog("Compare", "Please enter a job description", "error");
                    return;
                }
                
                if (!file) {
                    appendLog("Compare", "Please upload a resume first", "error");
                    return;
                }
                
                compareBtn.disabled = true;
                compareBtn.textContent = "Comparing...";
                lastAction.textContent = "Comparing CV with JD";
                appendLog("Compare", "Extracting resume text...");
                
                // Extract resume text from PDF
                let resumeText = null;
                try {
                    const formData = new FormData();
                    formData.append('file', file);
                    const parseRes = await fetch('/api/parse-pdf', {
                        method: 'POST',
                        body: formData
                    });
                    const parseData = await parseRes.json();
                    if (parseData && parseData.text) {
                        resumeText = parseData.text;
                    }
                } catch (err) {
                    appendLog("Compare", "Failed to parse PDF: " + err, "error");
                    compareBtn.disabled = false;
                    compareBtn.textContent = "Compare with CV";
                    return;
                }
                
                if (!resumeText) {
                    appendLog("Compare", "Could not extract resume text", "error");
                    compareBtn.disabled = false;
                    compareBtn.textContent = "Compare with CV";
                    return;
                }
                
                // Compare with job description
                try {
                    const res = await fetch('/api/compare-cv-jd', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            resume_text: resumeText,
                            job_description: jdText
                        })
                    });
                    const data = await res.json();
                    
                    if (data && !data.error) {
                        compareResult.style.display = 'block';
                        setScore(data.score, compareScoreCircle, compareScoreValue, compareScoreHeadline);
                        
                        // Set match level badge
                        const levelColors = {
                            "Excellent": "#4ade80",
                            "Good": "#60a5fa",
                            "Fair": "#fbbf24",
                            "Poor": "#f97373"
                        };
                        compareMatchLevel.innerHTML = `<span class="score-tag" style="border-color: ${levelColors[data.match_level] || '#9ca3af'}; color: ${levelColors[data.match_level] || '#9ca3af'};">${data.match_level} Match</span>`;
                        
                        appendLog("Compare", `Match score: ${data.score}% (${data.match_level})`, "ok");
                        setStatus("Comparison complete", true);
                    } else {
                        appendLog("Compare", "Error: " + (data.error || "unknown"), "error");
                    }
                } catch (err) {
                    appendLog("Compare", "Request failed: " + err, "error");
                }
                
                compareBtn.disabled = false;
                compareBtn.textContent = "Compare with CV";
            });

            // Initialize score visuals
            setScore(NaN);
        </script>
    </body>
    </html>
    """

