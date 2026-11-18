"""Tests for Sentence Transformer embeddings and cosine similarity (uses the real all-MiniLM-L6-v2 model)."""
import numpy as np
import pytest

from app.nlp import semantic_matcher as semantic_module
from app.nlp.semantic_matcher import SemanticMatcher, chunk_text, cosine_to_score, semantic_matcher

BACKEND_JD = "Python backend developer building REST APIs with FastAPI, SQL databases and Docker."


@pytest.fixture(scope="module")
def matcher():
    assert semantic_matcher.load(), semantic_matcher.error
    return semantic_matcher


# --- Pure functions ---------------------------------------------------------------------------------------
def test_chunking_keeps_short_text_whole_and_splits_long_text():
    assert chunk_text("one two three") == ["one two three"]
    assert chunk_text("") == [] and chunk_text(None) == []
    words = [f"w{i}" for i in range(400)]
    chunks = chunk_text(" ".join(words), chunk_words=150, overlap=30)
    assert all(len(c.split()) <= 150 for c in chunks)
    covered = {w for c in chunks for w in c.split()}
    assert covered == set(words)  # nothing is dropped
    assert chunks[1].split()[0] == "w120"  # 30-word overlap


@pytest.mark.parametrize(
    "cosine, expected", [(-0.5, 0.0), (0.15, 0.0), (0.45, 50.0), (0.75, 100.0), (0.95, 100.0)]
)
def test_cosine_calibration(cosine, expected):
    assert cosine_to_score(cosine, floor=0.15, ceil=0.75) == pytest.approx(expected)


# --- Real model -----------------------------------------------------------------------------------------------
def test_model_is_loaded_once_and_reused(matcher):
    session = matcher._session
    assert matcher.load() and matcher._session is session  # second load() does not reload
    assert matcher.embed_documents(["hello world"])[0].shape == (384,)


def test_embeddings_are_normalised(matcher):
    vector = matcher.embed_documents([BACKEND_JD])[0]
    assert np.linalg.norm(vector) == pytest.approx(1.0, abs=1e-5)


def test_cosine_matches_formula(matcher):
    a, b = matcher.embed_documents([BACKEND_JD, "Java Spring Boot microservices engineer"])
    manual = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    assert matcher.similarities(BACKEND_JD, ["Java Spring Boot microservices engineer"])[0] == pytest.approx(manual, abs=1e-5)


def test_related_text_scores_higher_than_unrelated(matcher):
    related, unrelated = matcher.similarities(
        BACKEND_JD,
        ["Developed Flask and FastAPI services in Python with PostgreSQL, deployed in Docker containers.",
         "Pastry chef specialising in French desserts and wedding cakes."],
    )
    assert related > 0.5 > unrelated
    assert cosine_to_score(related) > 50 > cosine_to_score(unrelated)


def test_empty_resume_text_gives_none(matcher):
    assert matcher.similarities(BACKEND_JD, ["", "   ", "Python developer"])[:2] == [None, None]


def test_batch_and_single_results_are_identical(matcher):
    texts = ["Python developer with FastAPI", "Data scientist using pandas", "Embedded C firmware engineer"]
    batch = matcher.similarities(BACKEND_JD, texts)
    singles = [matcher.similarities(BACKEND_JD, [t])[0] for t in texts]
    assert batch == pytest.approx(singles, abs=1e-5)


def test_long_resume_is_not_truncated(matcher):
    """Relevant content after 300 filler words must still influence the score."""
    filler = "lorem ipsum dolor sit amet " * 60  # 300 words
    without = matcher.similarities(BACKEND_JD, [filler])[0]
    with_tail = matcher.similarities(BACKEND_JD, [filler + " " + BACKEND_JD * 3])[0]
    assert with_tail > without + 0.1


def test_model_load_failure_is_reported_not_raised(monkeypatch):
    import onnxruntime

    def broken(*args, **kwargs):
        raise OSError("model files not found")

    monkeypatch.setattr(onnxruntime, "InferenceSession", broken)
    broken_matcher = SemanticMatcher()  # same files (already downloaded), but loading them fails
    assert broken_matcher.load() is False and broken_matcher.available is False
    assert "model files not found" in broken_matcher.error
    with pytest.raises(RuntimeError, match="Could not load model"):
        broken_matcher.similarities("jd", ["resume"])


def test_onnx_embeddings_identical_to_sentence_transformers(matcher):
    """The ONNX pipeline must reproduce the original sentence-transformers model exactly."""
    sentence_transformers = pytest.importorskip("sentence_transformers")
    reference = sentence_transformers.SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    texts = [BACKEND_JD, "Pastry chef specialising in French desserts.", "Java Spring Boot microservices " * 20]
    ours = matcher._encode(texts)
    theirs = reference.encode(texts, normalize_embeddings=True)
    assert np.abs(ours - theirs).max() < 1e-5


def test_shared_instance_is_module_level_singleton():
    assert semantic_module.semantic_matcher is semantic_matcher
