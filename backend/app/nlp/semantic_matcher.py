"""
Semantic similarity with the Sentence Transformers model all-MiniLM-L6-v2, run on ONNX Runtime.

What it does
------------
1. Turns each text into an *embedding*: a list of 384 numbers that captures its
   meaning, so "built REST services in Flask" and "backend API development with
   Python" end up close together even though they share few exact words.
2. Compares the JD embedding with each resume embedding using cosine similarity:

        cosine(A, B) = (A · B) / (||A|| × ||B||)        (range -1 … 1)

   The embeddings are normalised to length 1, so this is simply the dot product A · B.
3. Converts the cosine into a 0-100 score (see `cosine_to_score`).

How the model runs
------------------
The model is the official ONNX export of sentence-transformers/all-MiniLM-L6-v2,
executed with ONNX Runtime. This reproduces the sentence-transformers pipeline
exactly (tokenise -> transformer -> mean pooling -> L2 normalisation) without
installing PyTorch (~1 GB), which keeps the app small enough for serverless hosting.
A test checks the embeddings against the sentence-transformers library itself.

Practical details
-----------------
- Model files (~90 MB) are downloaded once from Hugging Face into MODEL_CACHE_DIR
  and loaded ONCE per server process, then reused for every request.
- The model reads at most 256 word-pieces (~180 words). Long texts are split into
  overlapping chunks of ~150 words; the chunk embeddings are averaged into one
  document embedding, so the whole resume counts, not just its first paragraph.
- All chunks of all resumes are encoded in batches (fast for 10+ resumes).
- If the model cannot be loaded, `available` is False and the semantic score is
  reported as unavailable instead of crashing the analysis.
"""
import logging
import os
import threading
import urllib.request
from pathlib import Path

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

CHUNK_WORDS = 150
CHUNK_OVERLAP = 30
MAX_TOKENS = 256  # all-MiniLM-L6-v2's max_seq_length
BATCH_SIZE = 32
MODEL_FILES = ("onnx/model.onnx", "tokenizer.json")


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


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """cos(A, B) = (A · B) / (||A|| × ||B||)."""
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator else 0.0


def _download(repo: str, filename: str, target: Path) -> None:
    """Download one file from the Hugging Face Hub (atomic: write to .part, then rename)."""
    url = f"https://huggingface.co/{repo}/resolve/{settings.MODEL_REVISION}/{filename}"
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, open(partial, "wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    os.replace(partial, target)


class SemanticMatcher:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.MODEL_NAME
        self.repo = self.model_name if "/" in self.model_name else f"sentence-transformers/{self.model_name}"
        self._session = None
        self._tokenizer = None
        self._error: str | None = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self._session is not None

    @property
    def error(self) -> str | None:
        return self._error

    def model_path(self, filename: str) -> Path:
        return Path(settings.MODEL_CACHE_DIR) / self.repo.replace("/", "--") / filename

    def load(self) -> bool:
        """Download (first time only) and load the model once, thread-safely. Returns True on success."""
        if self._session is not None:
            return True
        with self._lock:
            if self._session is None:
                try:
                    import onnxruntime
                    from tokenizers import Tokenizer

                    for filename in MODEL_FILES:
                        if not self.model_path(filename).exists():
                            logger.info("Downloading %s/%s ...", self.repo, filename)
                            _download(self.repo, filename, self.model_path(filename))
                    tokenizer = Tokenizer.from_file(str(self.model_path("tokenizer.json")))
                    tokenizer.enable_truncation(max_length=MAX_TOKENS)
                    tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
                    options = onnxruntime.SessionOptions()
                    options.log_severity_level = 3  # errors only
                    self._session = onnxruntime.InferenceSession(
                        str(self.model_path("onnx/model.onnx")), sess_options=options, providers=["CPUExecutionProvider"]
                    )
                    self._input_names = {i.name for i in self._session.get_inputs()}
                    self._tokenizer = tokenizer
                    self._error = None
                    logger.info("Semantic model '%s' loaded (ONNX Runtime).", self.model_name)
                except Exception as exc:  # no internet on first run, corrupted download, blocked DLL ...
                    self._session = None
                    self._error = f"Could not load model '{self.model_name}': {exc}".splitlines()[0]
                    logger.error(self._error)
        return self._session is not None

    def _encode(self, texts: list[str]) -> np.ndarray:
        """Normalised sentence embeddings: transformer -> mean pooling over real tokens -> L2 normalisation."""
        vectors = []
        for start in range(0, len(texts), BATCH_SIZE):
            encodings = self._tokenizer.encode_batch(texts[start:start + BATCH_SIZE])
            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
            feeds = {"input_ids": input_ids, "attention_mask": attention_mask}
            if "token_type_ids" in self._input_names:
                feeds["token_type_ids"] = np.array([e.type_ids for e in encodings], dtype=np.int64)
            hidden = self._session.run(None, feeds)[0]  # (batch, tokens, 384)
            mask = attention_mask[..., None].astype(np.float32)
            pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
            vectors.append(pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None))
        return np.vstack(vectors) if vectors else np.zeros((0, 384), dtype=np.float32)

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
            for owner, vector in zip(owners, self._encode(chunks)):
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
        return [None if vector is None else cosine_similarity(jd_vector, vector) for vector in resume_vectors]


# The single shared instance used by the whole application.
semantic_matcher = SemanticMatcher()
