from typing import List, Dict, Any, Set
import hashlib
import re

from .config import get_settings

settings = get_settings()

# Max chars to encode for speed (model has 256 token limit; ~4 chars/token safe)
_MAX_ENCODE_CHARS = 4000

# Common tech skills for extraction
COMMON_SKILLS = {
    'python', 'java', 'javascript', 'typescript', 'react', 'angular', 'vue', 'node', 'nodejs',
    'django', 'flask', 'fastapi', 'spring', 'express', 'mongodb', 'mysql', 'postgresql', 'sql',
    'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'jenkins', 'git', 'gitlab', 'ci/cd',
    'html', 'css', 'bootstrap', 'tailwind', 'redux', 'graphql', 'rest', 'api',
    'machine learning', 'ml', 'ai', 'deep learning', 'tensorflow', 'pytorch', 'pandas', 'numpy',
    'agile', 'scrum', 'devops', 'microservices', 'cloud', 'linux', 'unix'
}

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from numpy.linalg import norm
except Exception as e:  # pragma: no cover - runtime dependency
    raise ImportError("sentence-transformers and numpy are required for matcher") from e


def _truncate_for_encode(text: str, max_chars: int = _MAX_ENCODE_CHARS) -> str:
    """Truncate text for faster encoding while keeping meaning."""
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars].rsplit(" ", 1)[0] or text[:max_chars]


def _extract_skills(text: str) -> Set[str]:
    """Extract skills from text by looking for common tech terms."""
    if not text:
        return set()
    text_lower = text.lower()
    found_skills = set()
    
    # Check for common skills
    for skill in COMMON_SKILLS:
        if skill in text_lower:
            found_skills.add(skill)
    
    # Also extract comma-separated skills (common format)
    if ',' in text:
        parts = [p.strip().lower() for p in text.split(',')]
        found_skills.update([p for p in parts if len(p) > 2 and len(p) < 30])
    
    return found_skills


def _calculate_skill_overlap(resume_skills: Set[str], job_skills: Set[str]) -> float:
    """Calculate skill overlap score between resume and job (0-1)."""
    if not job_skills:
        return 0.5  # Neutral if job has no skills listed
    if not resume_skills:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = resume_skills & job_skills
    union = resume_skills | job_skills
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)


def _rows_hash(rows: List[Dict[str, Any]]) -> str:
    """Quick hash to detect if job data changed (skip re-encoding)."""
    if not rows:
        return "0"
    first = rows[0]
    # Support both old (job_description) and new (skills_required) formats
    desc = first.get("job_description", "") or first.get("skills_required", "")
    key = (
        str(len(rows))
        + str(desc[:200])
        + str(first.get("job_title", ""))
    )
    return hashlib.md5(key.encode("utf-8", errors="ignore")).hexdigest()


class SemanticMatcher:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.sentence_transformer_model
        self.model = SentenceTransformer(self.model_name)
        self._job_texts = []
        self._job_embeddings = None
        self._job_embeddings_norm = None  # Pre-normalized for fast dot product
        self._job_rows = None
        self._fitted_hash: str = ""

    def fit(self, rows: List[Dict[str, Any]]):
        """Provide training/job rows. Re-encodes only when data actually changes."""
        data_hash = _rows_hash(rows)
        if self._fitted_hash == data_hash and self._job_embeddings_norm is not None:
            return  # Already fitted with same data
        self._fitted_hash = data_hash

        texts = []
        for r in rows:
            # Support both old format (job_description) and new format (skills_required)
            txt = (r.get("job_description") or r.get("description") or r.get("job_desc") or "")
            job_title = r.get("job_title") or r.get("position_title") or r.get("title") or ""
            # New dataset uses skills_required (comma-separated)
            job_skills = (r.get("skills_required") or 
                         r.get("job_skill_set") or 
                         r.get("skills") or 
                         r.get("required_skills") or "")
            # Also include other relevant fields from new dataset
            company = r.get("company", "")
            location = r.get("location", "")
            experience = r.get("experience", "")
            category = r.get("category", "")
            
            # Combine all relevant information for better matching
            # Format: "Title Category Location Experience Skills Description"
            parts = [job_title, category, location, experience, job_skills, txt]
            combined_text = " ".join([p for p in parts if p]).strip()
            
            if combined_text:
                texts.append(_truncate_for_encode(combined_text))
            elif txt:
                texts.append(_truncate_for_encode(txt))
            elif job_title:
                texts.append(_truncate_for_encode(job_title))
        self._job_texts = texts
        if len(texts) == 0:
            dim = self.model.get_sentence_embedding_dimension()
            self._job_embeddings = np.zeros((0, dim))
            self._job_embeddings_norm = np.zeros((0, dim))
        else:
            self._job_embeddings = np.array(
                self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            )
            # Pre-normalize once for fast cosine similarity in match_text
            self._job_embeddings_norm = self._job_embeddings / (
                norm(self._job_embeddings, axis=1, keepdims=True) + 1e-9
            )
        self._job_rows = rows

    def match_text(self, text: str, top_k: int = 3):
        if not text:
            return []
        text = _truncate_for_encode(text)
        
        # Extract skills from resume for better matching
        resume_skills = _extract_skills(text)
        
        emb = np.array(
            self.model.encode([text], convert_to_numpy=True, show_progress_bar=False)
        )[0]
        if self._job_embeddings_norm is None or self._job_embeddings_norm.shape[0] == 0:
            return []
        # Use pre-normalized job embeddings; only normalize resume embedding
        emb_norm = emb / (norm(emb) + 1e-9)
        sims = np.dot(self._job_embeddings_norm, emb_norm)
        
        # Improve accuracy by combining semantic similarity with skill overlap
        enhanced_scores = []
        for idx, semantic_sim in enumerate(sims):
            row = self._job_rows[int(idx)] if self._job_rows is not None else {}
            # Extract job skills
            job_skills_str = (row.get("skills_required") or 
                            row.get("job_skill_set") or 
                            row.get("skills") or "")
            job_skills = _extract_skills(job_skills_str)
            
            # Calculate skill overlap
            skill_overlap = _calculate_skill_overlap(resume_skills, job_skills)
            
            # Combine semantic similarity (70%) with skill overlap (30%)
            # This gives more accurate ATS scores
            combined_score = (semantic_sim * 0.7) + (skill_overlap * 0.3)
            enhanced_scores.append(combined_score)
        
        enhanced_scores = np.array(enhanced_scores)
        
        # Normalize enhanced scores to 0-100 range
        min_sim = 0.3
        max_sim = 0.95
        normalized_sims = np.clip((enhanced_scores - min_sim) / (max_sim - min_sim), 0, 1) * 100
        
        # Ensure top matches get appropriate scores
        if len(enhanced_scores) > 0:
            top_sim = np.max(enhanced_scores)
            if top_sim < 0.3:
                normalized_sims = (enhanced_scores / 0.3) * 30
            elif top_sim < 0.5:
                normalized_sims = 30 + ((enhanced_scores - 0.3) / 0.2) * 40
            # Otherwise use standard scaling
        
        # Sort by enhanced scores
        idxs = np.argsort(-enhanced_scores)[:top_k]
        results = []
        for i in idxs:
            row = self._job_rows[int(i)] if self._job_rows is not None else {}
            actual_sim = float(enhanced_scores[int(i)])
            final_score = max(0, min(100, float(normalized_sims[int(i)])))
            
            # Support multiple column name variations (old and new formats)
            company_name = (row.get("company_name") or 
                          row.get("company") or 
                          row.get("employer") or "")
            position_title = (row.get("position_title") or 
                            row.get("job_title") or 
                            row.get("title") or "")
            # New dataset doesn't have job_description, use skills_required + other fields
            job_description = (row.get("job_description") or 
                             row.get("description") or 
                             row.get("job_desc") or "")
            if not job_description:
                # Build description from available fields
                parts = []
                if row.get("location"):
                    parts.append(f"Location: {row.get('location')}")
                if row.get("experience"):
                    parts.append(f"Experience: {row.get('experience')}")
                if row.get("skills_required"):
                    parts.append(f"Skills: {row.get('skills_required')}")
                if row.get("category"):
                    parts.append(f"Category: {row.get('category')}")
                job_description = " | ".join(parts)
            
            results.append({
                "index": int(i),
                "score": round(final_score, 1),
                "similarity": round(actual_sim, 4),
                "company_name": company_name,
                "position_title": position_title,
                "job_description": job_description[:800],
            })
        return results
    
    def compare_with_jd(self, resume_text: str, job_description: str) -> dict:
        """Compare a resume with a specific job description and return match score."""
        if not resume_text or not job_description:
            return {"error": "Both resume text and job description are required", "score": 0}
        # Truncate for faster encoding
        resume_text = _truncate_for_encode(resume_text)
        job_description = _truncate_for_encode(job_description)
        # Encode both in one batch for speed
        texts = [resume_text, job_description]
        embs = np.array(
            self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        )
        resume_emb = embs[0]
        jd_emb = embs[1]
        
        # Calculate cosine similarity with proper normalization
        resume_norm = resume_emb / (norm(resume_emb) + 1e-9)
        jd_norm = jd_emb / (norm(jd_emb) + 1e-9)
        similarity = float(np.dot(resume_norm, jd_norm))
        
        # More accurate scaling based on real-world sentence transformer similarity ranges
        # Sentence transformers typically give similarities between 0.2-0.95 for related text
        # Use realistic thresholds for better accuracy
        if similarity >= 0.75:
            # Excellent match: 0.75-0.95 -> 85-100%
            normalized_score = 85 + ((similarity - 0.75) / 0.20) * 15
        elif similarity >= 0.60:
            # Good match: 0.60-0.75 -> 70-85%
            normalized_score = 70 + ((similarity - 0.60) / 0.15) * 15
        elif similarity >= 0.45:
            # Fair match: 0.45-0.60 -> 50-70%
            normalized_score = 50 + ((similarity - 0.45) / 0.15) * 20
        elif similarity >= 0.30:
            # Poor match: 0.30-0.45 -> 30-50%
            normalized_score = 30 + ((similarity - 0.30) / 0.15) * 20
        else:
            # Very poor match: 0-0.30 -> 0-30%
            normalized_score = (similarity / 0.30) * 30
        
        normalized_score = max(0, min(100, normalized_score))
        
        # Determine match level based on normalized score
        if normalized_score >= 80:
            match_level = "Excellent"
        elif normalized_score >= 65:
            match_level = "Good"
        elif normalized_score >= 50:
            match_level = "Fair"
        elif normalized_score >= 35:
            match_level = "Poor"
        else:
            match_level = "Very Poor"
        
        return {
            "score": round(normalized_score, 1),
            "similarity": round(similarity, 4),
            "match_level": match_level
        }


_GLOBAL_MATCHER = None


def get_global_matcher():
    global _GLOBAL_MATCHER
    if _GLOBAL_MATCHER is None:
        _GLOBAL_MATCHER = SemanticMatcher()
    return _GLOBAL_MATCHER


__all__ = ["SemanticMatcher", "get_global_matcher"]
