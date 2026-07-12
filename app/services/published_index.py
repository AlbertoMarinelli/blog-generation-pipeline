import os
import numpy as np
import faiss
from sqlalchemy import select
from app.database.db import SessionLocal
from app.database.models import GeneratedPostModel

INDEX_PATH = "data/published_posts.index"

class PublishedPostsIndex:
    """Manages the FAISS vector index of published blog posts to support related post queries."""

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def build_index_from_db(self) -> int:
        """Extracts all published posts from the database, builds the FAISS index, and saves it to disk.

        Returns:
            int: The number of indexed posts.
        """
        with self.session_factory() as session:
            # Query published posts with non-null embeddings
            posts = session.scalars(
                select(GeneratedPostModel).where(
                    GeneratedPostModel.is_published == True,
                    GeneratedPostModel.embedding != None
                )
            ).all()

            if not posts:
                print("No published posts found in the database for indexing.")
                # If the index file exists, remove it for consistency
                if os.path.exists(INDEX_PATH):
                    try:
                        os.remove(INDEX_PATH)
                    except OSError:
                        pass
                return 0

            # Extract and inspect the first embedding to determine vector dimension dynamically
            first_emb = np.frombuffer(posts[0].embedding, dtype=np.float32)
            dimension = len(first_emb)

            # Create a FAISS IndexIDMap2 with IndexFlatIP (Inner Product cosine similarity on normalized vectors)
            flat_index = faiss.IndexFlatIP(dimension)
            index = faiss.IndexIDMap2(flat_index)

            embeddings_list = []
            ids_list = []

            for p in posts:
                emb = np.frombuffer(p.embedding, dtype=np.float32)
                # Normalize embeddings to ensure Inner Product calculates cosine similarity
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                embeddings_list.append(emb)
                ids_list.append(p.id)

            embeddings_np = np.stack(embeddings_list).astype(np.float32)
            ids_np = np.array(ids_list, dtype=np.int64)

            # Add vectors mapped to database primary IDs
            index.add_with_ids(embeddings_np, ids_np)

            # Save the index to disk
            os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
            faiss.write_index(index, INDEX_PATH)
            print(f"FAISS index built and exported successfully to '{INDEX_PATH}' ({len(posts)} posts indexed).")
            return len(posts)

    def search_similar_posts(self, query_embedding: np.ndarray, k: int = 2) -> list[int]:
        """Queries the vector index for the k most similar published posts.

        Args:
            query_embedding (np.ndarray): The query vector.
            k (int): Maximum number of recommendations to retrieve.

        Returns:
            list[int]: List of primary database IDs for matching posts.
        """
        if not os.path.exists(INDEX_PATH):
            return []

        try:
            # Load the index from disk
            index = faiss.read_index(INDEX_PATH)
        except Exception as e:
            print(f"Error loading FAISS index from disk: {e}")
            return []

        # Normalize query vector for cosine similarity
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return []
        q_vec = (query_embedding / query_norm).reshape(1, -1).astype(np.float32)

        # Search the index
        distances, indices = index.search(q_vec, k)

        # Return valid IDs, filtering out -1 (no match indicator)
        matched_ids = [int(idx) for idx in indices[0] if idx != -1]
        return matched_ids
