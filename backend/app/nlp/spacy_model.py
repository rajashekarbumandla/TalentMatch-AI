"""
Loads the spaCy English model (en_core_web_sm) once and shares it.

Components kept:
- tagger  part-of-speech tags (e.g. a JD sentence starting with a verb, "Build APIs...",
          is usually a responsibility)
- senter  fast sentence splitting (used instead of the slower dependency parser)
- ner     named entities (PERSON names in resumes)

If the model cannot be loaded, callers get None and fall back to simpler rules;
parsing still works and nothing crashes.
"""
import logging
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_spacy_model():
    try:
        import spacy

        nlp = spacy.load(settings.SPACY_MODEL, exclude=["lemmatizer"])
        if "parser" in nlp.pipe_names:
            nlp.disable_pipe("parser")  # slow and not needed...
        if "senter" in nlp.disabled:
            nlp.enable_pipe("senter")  # ...because this lighter component splits sentences
        return nlp
    except Exception as exc:  # model not installed, blocked DLL, etc.
        logger.warning("spaCy model '%s' unavailable (%s); NLP fallbacks in use.", settings.SPACY_MODEL, exc)
        return None
