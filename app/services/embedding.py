import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
_model = None

def get_embedding_model() -> SentenceTransformer:
    """
    Ritorna l'istanza condivisa di SentenceTransformer (Singleton)
    per evitare molteplici caricamenti del modello in memoria.
    """
    global _model
    if _model is None:
        logger.info("Caricamento del modello SentenceTransformer ('all-MiniLM-L6-v2') condiviso...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Modello SentenceTransformer caricato con successo.")
    return _model
