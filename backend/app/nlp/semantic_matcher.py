"""
Semantic similarity with Sentence Transformers (all-MiniLM-L6-v2).

What it does
------------
1. Turns each text into an *embedding*: a list of 384 numbers that captures its
   meaning, so "built REST services in Flask" and "backend API development with
   Python" end up close together even though they share few exact words.
2. Compares the JD embedding with each resume embedding using cosine similarity:

        cosine(A, B) = (A · B) / (||A|| × ||B||)        (range -1 … 1)

3. Converts the cosine into a 0-100 score (see `cosine_to_score`).

Practical details
-----------------
- The model is loaded ONCE (at API startup) and reused for every request.
- MiniLM reads at most 256 word-pieces (~180 words) and silently ignores the
  rest. Long texts are therefore split into overlapping chunks of ~150 words;
  the chunk embeddings are averaged into one document embedding, so the whole
  resume counts, not just its first paragraph.
- All chunks of all resumes are encoded in one batched call (fast for 10+ resumes).
- If the model cannot be loaded, `available` is False and the semantic score
  is reported as unavailable instead of crashing the analysis.
"""
import logging
import threading

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings

logger = logging.getLogger(__name__)

CHUNK_WORDS = 150
CHUNK_OVERLAP = 30


def chunk_text(text: str, chunk_words: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word windows so no part exceeds the model's input limit."""
    words = (text or "").split()
    if not words:
        return []
    if len(words) <= chunk_words:
        return [" ".join(words)]
    step = chunk_words - overlap
    return [" ".join(words[i:i + chunk_words]) for i in range(0, len(words) - overlap, step)]


def cosine_to_score(cosine: float, floor: float | None = None, ceil: float | None = None) -> float:
    """
    Linear calibration of a cosine similarity to 0-100.

    all-MiniLM-L6-v2 rarely gives cosines below ~0.1 (unrelated texts) or above
    ~0.7 (near-identical topics) for JD/resume pairs, so the raw value would
    use only a small part of the 0-100 range. Values <= FLOOR map to 0,
    >= CEIL map to 100, linear in between. Both bounds are configurable.
    """
    floor = settings.SEMANTIC_COSINE_FLOOR if floor is None else floor
    ceil = settings.SEMANTIC_COSINE_CEIL if ceil is None else ceil
    score = (cosine - floor) / (ceil - floor) * 100
    return float(min(max(score, 0.0), 100.0))


class SemanticMatcher:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.MODEL_NAME
        self._model = None
        self._error: str | None = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def error(self) -> str | None:
        return self._error

    def load(self) -> bool:
        """Load the model once (thread-safe). Returns True on success."""
        if self._model is not None:
            return True
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name, device="cpu")
                    self._error = None
                    logger.info("Sentence Transformer '%s' loaded.", self.model_name)
                except Exception as exc:  # no internet on first run, corrupted cache, blocked DLL ...
                    self._error = f"Could not load model '{self.model_name}': {exc}".splitlines()[0]
                    logger.error(self._error)
        return self._model is not None

    def embed_documents(self, texts: list[str]) -> list[np.ndarray | None]:
        """One normalised embedding per text (None for empty text), via chunk averaging."""
        if not self.load():
            raise RuntimeError(self._error or "Semantic model unavailable.")
        chunks, owners = [], []
        for index, text in enumerate(texts):
            for chunk in chunk_text(text):
                chunks.append(chunk)
                owners.append(index)
        vectors: list[list[np.ndarray]] = [[] for _ in texts]
        if chunks:
            encoded = self._model.encode(chunks, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
            for owner, vector in zip(owners, encoded):
                vectors[owner].append(vector)
        result: list[np.ndarray | None] = []
        for parts in vectors:
            if not parts:
                result.append(None)
                continue
            mean = np.mean(parts, axis=0)
            norm = np.linalg.norm(mean)
            result.append(mean / norm if norm else None)
        return result

    def similarities(self, jd_text: str, resume_texts: list[str]) -> list[float | None]:
        """Raw cosine similarity between the JD and each resume (None if a text is empty)."""
        embeddings = self.embed_documents([jd_text, *resume_texts])
        jd_vector, resume_vectors = embeddings[0], embeddings[1:]
        if jd_vector is None:
            return [None] * len(resume_texts)
        return [
            None if vector is None else float(cosine_similarity(jd_vector.reshape(1, -1), vector.reshape(1, -1))[0, 0])
            for vector in resume_vectors
        ]


# The single shared instance used by the whole application.
semantic_matcher = SemanticMatcher()
