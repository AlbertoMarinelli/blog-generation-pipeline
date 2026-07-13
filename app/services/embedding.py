import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
_model = None

def get_embedding_model() -> SentenceTransformer:
    """Returns the shared SentenceTransformer singleton instance to prevent multiple model copies in memory.

    Returns:
        SentenceTransformer: Shared encoder model.
    """
    global _model
    if _model is None:
        logger.info("Loading shared SentenceTransformer model ('all-MiniLM-L6-v2')...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("SentenceTransformer model loaded successfully.")
    return _model
