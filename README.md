# AI Resume Analyzer & Job Matcher

A full-stack web application that analyzes resumes, computes ATS-style scores, and recommends matching jobs using NLP and semantic similarity.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Features

- **PDF Resume Parsing** – Extract text from PDF resumes
- **ATS Score** – Compute an ATS-style match score (0–100%)
- **Job Matching** – Semantic matching with 12,000+ jobs using sentence-transformers
- **CV vs JD Comparison** – Compare your resume against a custom job description
- **Interactive Dashboard** – Upload, analyze, and view results in one place

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (Python 3.11) |
| NLP | spaCy, sentence-transformers (Hugging Face) |
| PDF | pdfminer.six |
| Data | Pandas, CSV |
| Auth | JWT, passlib, python-jose (ready) |
| Database | PostgreSQL + SQLAlchemy (ready) |
| Deployment | Docker, docker-compose |

---

## Project Structure

```
ai-resume-analyzer/
├── app/
│   ├── main.py          # FastAPI app, routes, dashboard
│   ├── config.py        # Settings & env config
│   ├── data_loader.py   # Load training/resume CSVs
│   └── matcher.py       # Semantic matching (sentence-transformers)
├── job_dataset.csv      # Job postings (12,000+ jobs)
├── Resume.csv           # Sample resumes (optional fallback)
├── training_data.csv    # Legacy dataset
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── DEPLOYMENT.md        # Docker & production notes
├── AWS_DEPLOYMENT.md    # AWS deploy (App Runner, ECS, EC2)
└── DATASET_USAGE.md     # Dataset details
```

---

## Prerequisites

- Python 3.11+
- ~2 GB RAM (for sentence-transformers model)

---

## Local Setup

### 1. Clone and enter the project

```bash
git clone <your-repo-url>
cd ai-resume-analyzer
```

### 2. Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Download spaCy model (if not auto-installed)

```bash
python -m spacy download en_core_web_sm
```

### 5. Run the API

```bash
uvicorn app.main:app --reload
```

The API runs at **http://localhost:8000**

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| GET | `/dashboard` | Interactive web dashboard |
| GET | `/docs` | Swagger API documentation |
| POST | `/api/parse-pdf` | Extract text from PDF file |
| POST | `/api/match-jobs` | Get top 5 job matches (body: `{ "text": "resume text" }`) |
| POST | `/api/compare-cv-jd` | Compare resume with job description |
| POST | `/debug/match` | Debug: match resume text, returns ATS score |
| GET | `/debug/datasets` | Debug: inspect loaded datasets |

---

## Docker Deployment

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) (optional, for `docker-compose`)
- ~4 GB free disk space (first build downloads PyTorch & models)

---

### Step 1: Build the image

From the project root:

```bash
docker build -t ai-resume-analyzer .
```

**Note:** First build takes 10–15 minutes (downloads Python deps, PyTorch, sentence-transformers model). Later builds use cache and are faster.

---

### Step 2: Run the container

```bash
docker run -p 8000:8000 ai-resume-analyzer
```

- App: **http://localhost:8000**
- Dashboard: **http://localhost:8000/dashboard**
- API docs: **http://localhost:8000/docs**

---

### Step 3 (optional): Run in background (detached)

```bash
docker run -d -p 8000:8000 --name resume-analyzer ai-resume-analyzer
```

- View logs: `docker logs -f resume-analyzer`
- Stop: `docker stop resume-analyzer`
- Remove: `docker rm resume-analyzer`

---

### Using docker-compose

```bash
docker-compose up --build
```

Runs the app and creates a volume for uploads. Add `-d` to run in background.

---

### Push to Docker Hub

1. **Log in** (enter your password when prompted):
   ```bash
   docker login
   ```

2. **Tag** with your Docker Hub username:
   ```bash
   docker build -t mohitbhalothia007/ai-resume-analyzer:latest .
   ```

3. **Push** to Docker Hub:
   ```bash
   docker push mohitbhalothia007/ai-resume-analyzer:latest
   ```

Image URL: **https://hub.docker.com/r/mohitbhalothia007/ai-resume-analyzer**

---

### Run pre-built image from Docker Hub

```bash
docker run -p 8000:8000 mohitbhalothia007/ai-resume-analyzer
```

---

### Custom port and environment variables

```bash
# Use port 8080 instead of 8000
docker run -p 8080:8000 ai-resume-analyzer

# Pass environment variables
docker run -p 8000:8000 -e ENVIRONMENT=production -e JWT_SECRET_KEY=your-secret ai-resume-analyzer
```

---

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Build fails / out of memory | Allocate more memory to Docker (Settings → Resources) |
| Port 8000 already in use | Use a different port: `-p 8080:8000` |
| Slow first request | Model loads on startup; wait a few seconds |

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for more details.

---

## AWS Deployment

Deploy to AWS using your Docker image:

| Option | Use case |
|--------|----------|
| **App Runner** | Easiest – fully managed, auto-scaling |
| **ECS Fargate** | Production workloads, scalable |
| **EC2** | Full control, run Docker on a VM |

**Quick EC2 deploy:**
```bash
# On an EC2 instance (t3.medium or larger)
docker run -d -p 8000:8000 --restart unless-stopped mohitbhalothia007/ai-resume-analyzer:latest
```

See **[AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md)** for step-by-step instructions.

---

## Environment Variables

Create a `.env` file (optional):

```env
ENVIRONMENT=development
JWT_SECRET_KEY=your-secret-key-in-production
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/ai_resume_analyzer
TRAINING_CSV_PATH=job_dataset.csv
RESUMES_CSV_PATH=Resume.csv
SENTENCE_TRANSFORMER_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

---

## Datasets

| File | Purpose |
|------|---------|
| `job_dataset.csv` | 12,000+ job postings used for matching |
| `Resume.csv` | Sample resumes (optional, for key-based lookup) |

Configure paths in `app/config.py` or via env vars. See **[DATASET_USAGE.md](DATASET_USAGE.md)** for details.

---

## Usage Example

```bash
# Parse a PDF
curl -X POST -F "file=@resume.pdf" http://localhost:8000/api/parse-pdf

# Match jobs (with resume text)
curl -X POST http://localhost:8000/api/match-jobs \
  -H "Content-Type: application/json" \
  -d '{"text": "Experienced Python developer with 5 years..."}'
```

---

## License

MIT
