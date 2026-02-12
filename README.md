# AI Resume Analyzer & Job Matcher

This project is a full-stack web application that:

- Parses resumes (PDF → text)
- Extracts skills using NLP (spaCy + transformers)
- Computes an ATS-style score
- Recommends matching jobs
- Provides an admin dashboard for managing job postings

## Tech stack

- Backend: FastAPI (Python)
- NLP: spaCy, sentence-transformers (Hugging Face)
- Database: PostgreSQL (via SQLAlchemy)
- Auth: JWT (access tokens) with role-based access (user/admin)
- Containerization: Docker + docker-compose
- Deployment target: AWS (EC2 or ECS + RDS + S3)

## Local setup (high level)

1. Create and activate a virtual environment (on your machine):
   - Windows (PowerShell):
     - `python -m venv .venv`
     - `.venv\Scripts\Activate.ps1`
   - macOS / Linux:
     - `python -m venv .venv`
     - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Create a `.env` file (see `.env.example` once it exists).
4. Run the API:
   - `uvicorn app.main:app --reload`

Docker and AWS deployment steps will be documented once the core API is complete.

