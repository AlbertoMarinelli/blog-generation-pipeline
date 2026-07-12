import numpy as np
import faiss
from app.database.models import ArticleModel


class RAGRetriever:
    """Handles in-memory FAISS indexing and vector retrieval of articles for RAG-augmented generation."""

    def __init__(self):
        self.index = None
        self.article_mapping = []

    def build_index(self, articles: list[ArticleModel]) -> bool:
        """Constructs an in-memory FAISS L2 Inner Product index for the provided articles.

        Args:
            articles (list[ArticleModel]): List of articles to index.

        Returns:
            bool: True if index was successfully built, False otherwise.
        """
        if not articles:
            self.index = None
            self.article_mapping = []
            return False

        # Load embedding float32 arrays from database binary buffers
        embeddings_list = []
        valid_articles = []

        for a in articles:
            if a.embedding is not None:
                emb = np.frombuffer(a.embedding, dtype=np.float32)
                # Ensure the embedding size is correct (384 dimensions)
                if emb.shape[0] == 384:
                    embeddings_list.append(emb)
                    valid_articles.append(a)

        if not embeddings_list:
            self.index = None
            self.article_mapping = []
            return False

        # Stack into matrix (Shape: M x 384)
        np_embs = np.stack(embeddings_list).astype(np.float32)

        # L2 Normalize the vectors so Inner Product (IndexFlatIP) behaves as Cosine Similarity
        norms = np.linalg.norm(np_embs, axis=1, keepdims=True)
        # Avoid division by zero
        norms[norms == 0] = 1.0
        normalized_embs = np_embs / norms

        # Create IndexFlatIP index
        self.index = faiss.IndexFlatIP(384)
        self.index.add(normalized_embs)
        
        # Keep track of mapping index -> ArticleModel
        self.article_mapping = valid_articles
        return True

    def retrieve(self, query_vector: np.ndarray, k: int = 3) -> list[ArticleModel]:
        """Retrieves the top k most relevant articles matching the query vector.

        Args:
            query_vector (np.ndarray): The query embedding.
            k (int): Number of articles to retrieve.

        Returns:
            list[ArticleModel]: List of top relevant articles.
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # Ensure query is float32 and shape is (1, 384)
        query = np.array(query_vector, dtype=np.float32).reshape(1, -1)

        # Normalize query vector
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        # Query FAISS
        # index.search returns (distances, indices)
        k_actual = min(k, self.index.ntotal)
        distances, indices = self.index.search(query, k_actual)

        retrieved_articles = []
        for idx in indices[0]:
            if idx != -1 and idx < len(self.article_mapping):
                retrieved_articles.append(self.article_mapping[idx])

        return retrieved_articles
