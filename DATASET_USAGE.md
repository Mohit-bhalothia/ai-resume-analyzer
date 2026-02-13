# Dataset Usage in AI Resume Analyzer

This document shows exactly where each of the 3 datasets is used in the codebase.

## 📊 Dataset Configuration

**Location:** `app/config.py` (lines 21-22)

```python
training_csv_path: str = "all_job_post.csv"  # Job postings dataset
resumes_csv_path: str = "Resume.csv"         # Resumes dataset
```

---

## 1️⃣ **all_job_post.csv** (Job Postings Dataset)

**Purpose:** Contains job postings used for matching resumes to jobs

**Columns:** `job_id`, `category`, `job_title`, `job_description`, `job_skill_set`

### Usage Locations:

#### ✅ **Startup Pre-load** (`app/main.py` line 27)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    td = load_training_data()  # Loads all_job_post.csv
    matcher.fit(rows)  # Pre-encodes all job descriptions
```
**Purpose:** Pre-loads and encodes all jobs at server startup for faster responses

---

#### ✅ **Debug Endpoint** (`app/main.py` line 77)
```python
@app.get("/debug/datasets")
def debug_datasets():
    td = load_training_data()  # Shows dataset summary
```
**Purpose:** Debug endpoint to inspect dataset contents

---

#### ✅ **Main Matching Endpoint** (`app/main.py` line 127)
```python
@app.post("/debug/match")
def debug_match(req: MatchRequest):
    td = load_training_data()  # Loads all_job_post.csv
    matcher.fit(rows)  # Fits matcher with job data
    matches = matcher.match_text(req.text, top_k=1)  # Matches resume to jobs
```
**Purpose:** Main endpoint for matching resume to best job (returns ATS score)

---

#### ✅ **Job Matches Endpoint** (`app/main.py` line 250)
```python
@app.post("/api/match-jobs")
def match_jobs(req: MatchRequest):
    td = load_training_data()  # Loads all_job_post.csv
    matcher.fit(rows)  # Fits matcher with job data
    matches = matcher.match_text(resume_text, top_k=5)  # Returns top 5 matches
```
**Purpose:** Returns top 5 job matches for a resume (used by dashboard)

---

## 2️⃣ **Resume.csv** (Resumes Dataset)

**Purpose:** Contains resume data for lookup when matching by filename/key

**Columns:** `ID`, `Resume_str`, `Resume_html`, `Category`

### Usage Locations:

#### ✅ **Debug Endpoint** (`app/main.py` line 82)
```python
@app.get("/debug/datasets")
def debug_datasets():
    rd = load_resumes()  # Shows dataset summary
```
**Purpose:** Debug endpoint to inspect resume dataset

---

#### ✅ **Fallback Resume Lookup** (`app/main.py` line 157)
```python
@app.post("/debug/match")
def debug_match(req: MatchRequest):
    resumes = load_resumes()  # Loads Resume.csv
    # Searches for resume by filename/key in CSV
    # Extracts Resume_str column for matching
```
**Purpose:** Fallback when PDF parsing fails - looks up resume text from CSV

---

#### ✅ **Job Matches with Key** (`app/main.py` line 266)
```python
@app.post("/api/match-jobs")
def match_jobs(req: MatchRequest):
    resumes = load_resumes()  # Loads Resume.csv
    # Looks up resume by key/filename
    # Extracts Resume_str for matching
```
**Purpose:** Alternative way to get resume text when key is provided instead of text

---

## 3️⃣ **training_data.csv** (NOT USED - Replaced)

**Status:** ❌ **This file is NO LONGER USED**

**Replaced by:** `all_job_post.csv`

**Old Usage:** Previously used for job postings, but has been replaced in `app/config.py`

---

## 🔄 Data Flow Summary

```
┌─────────────────────────────────────────────────────────┐
│                    USER UPLOADS PDF                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Extract text from PDF │
         └───────────┬─────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Encode resume text   │
         │  (sentence transformer)│
         └───────────┬─────────────┘
                     │
                     ▼
    ┌────────────────────────────────────┐
    │  Compare with all_job_post.csv     │
    │  (1,167 job embeddings)            │
    │  - job_title                       │
    │  - job_description                 │
    │  - job_skill_set                  │
    └────────────┬───────────────────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │  Return top 5 matches       │
    │  with similarity scores    │
    └────────────────────────────┘
```

---

## 📝 Key Points

1. **all_job_post.csv** is the PRIMARY dataset used for job matching
   - Loaded at startup (cached)
   - Used in all matching endpoints
   - Contains 1,167 job postings

2. **Resume.csv** is used as a FALLBACK
   - Only used when PDF parsing fails
   - Used when matching by filename/key instead of direct text
   - Contains resume text in `Resume_str` column

3. **training_data.csv** is NOT USED
   - Replaced by `all_job_post.csv`
   - Can be safely ignored or removed

---

## 🔍 How to Verify Dataset Usage

1. **Check config:** `app/config.py` lines 21-22
2. **Check data loader:** `app/data_loader.py` lines 35-42
3. **Check actual usage:** Search for `load_training_data()` and `load_resumes()` in `app/main.py`
