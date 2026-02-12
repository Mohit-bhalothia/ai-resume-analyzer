from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import get_settings


settings = get_settings()

app = FastAPI(title=settings.app_name)

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
                                <div class="aside-title">Admin & matching preview</div>
                                <span class="chip">Read‑only mock</span>
                            </div>
                            <div class="subtitle" style="margin-bottom: 10px;">
                                This panel mimics what an admin view could look like once job and scoring endpoints are wired in.
                            </div>
                            <div class="list">
                                <div class="list-item">
                                    <div class="list-title">Senior Backend Engineer · Remote (EU)</div>
                                    <div class="list-sub">Focus on FastAPI, microservices, and distributed systems.</div>
                                    <div class="list-meta">
                                        <div class="list-tag-row">
                                            <span class="list-tag">FastAPI</span>
                                            <span class="list-tag">PostgreSQL</span>
                                            <span class="list-tag">Docker</span>
                                        </div>
                                        <div>Match: <strong>82%</strong></div>
                                    </div>
                                </div>
                                <div class="list-item">
                                    <div class="list-title">Machine Learning Engineer · ATS Optimization</div>
                                    <div class="list-sub">NLP-heavy role working on resume ranking and job search relevance.</div>
                                    <div class="list-meta">
                                        <div class="list-tag-row">
                                            <span class="list-tag">Transformers</span>
                                            <span class="list-tag">spaCy</span>
                                            <span class="list-tag">PyTorch</span>
                                        </div>
                                        <div>Match: <strong>76%</strong></div>
                                    </div>
                                </div>
                                <div class="list-item">
                                    <div class="list-title">Full‑stack Developer · Talent Platform</div>
                                    <div class="list-sub">Blend of API work and front‑end dashboards for recruiters.</div>
                                    <div class="list-meta">
                                        <div class="list-tag-row">
                                            <span class="list-tag">React</span>
                                            <span class="list-tag">FastAPI</span>
                                            <span class="list-tag">Auth/JWT</span>
                                        </div>
                                        <div>Match: <strong>69%</strong></div>
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

            const setScore = (score) => {
                if (isNaN(score)) {
                    scoreValue.textContent = "–";
                    scoreCircle.style.setProperty("--score-deg", "40deg");
                    scoreHeadline.textContent = "Upload a resume to simulate scoring.";
                    return;
                }
                const clamped = Math.max(0, Math.min(100, score));
                const deg = (clamped / 100) * 320 + 40;
                scoreCircle.style.setProperty("--score-deg", deg + "deg");
                scoreValue.textContent = clamped.toString();
                if (clamped >= 80) {
                    scoreHeadline.textContent = "Great match! This profile should stand out for most job filters.";
                } else if (clamped >= 60) {
                    scoreHeadline.textContent = "Solid fit. A few targeted tweaks could push this into the top tier.";
                } else if (clamped >= 40) {
                    scoreHeadline.textContent = "Moderate match. Consider sharpening skills & keywords for the target role.";
                } else {
                    scoreHeadline.textContent = "Low match. Use this as a baseline and expand relevant experience/skills.";
                }
            };

            const simulateScoreFromFile = (file) => {
                if (!file) return 0;
                const base = 55;
                const lenFactor = Math.min(35, Math.floor(file.size / (1024 * 20)));
                const nameFactor = file.name.toLowerCase().includes("senior") ? 8 :
                    file.name.toLowerCase().includes("lead") ? 6 : 0;
                const random = Math.floor(Math.random() * 15);
                return base + lenFactor + nameFactor + random;
            };

            resumeFile.addEventListener("change", () => {
                const file = resumeFile.files[0];
                if (!file) {
                    fileHint.textContent = "No file selected yet. This demo keeps everything in the browser.";
                    return;
                }
                fileHint.textContent = "Selected: " + file.name + " (" + (file.size / 1024).toFixed(1) + " KB)";
                lastAction.textContent = "Selected resume file";
                appendLog("File", "Selected " + file.name);
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

            analyzeBtn.addEventListener("click", () => {
                const file = resumeFile.files[0];
                if (!file) {
                    appendLog("Analyze", "No file selected – using demo score", "error");
                    lastAction.textContent = "Tried to analyze without file";
                    setScore(Math.floor(40 + Math.random() * 30));
                    return;
                }
                lastAction.textContent = "Generated local demo score";
                const score = simulateScoreFromFile(file);
                setScore(score);
                appendLog("Analyze", "Simulated ATS score=" + score + " for " + file.name, "ok");
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
                appendLog("System", "Dashboard state reset");
            });

            // Initialize score visuals
            setScore(NaN);
        </script>
    </body>
    </html>
    """

