import os
import numpy as np
import faiss
from sqlalchemy import select
from app.database.db import SessionLocal
from app.database.models import GeneratedPostModel

INDEX_PATH = "data/published_posts.index"

class PublishedPostsIndex:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def build_index_from_db(self) -> int:
        """
        Estrarre tutti i post con is_published = 1 dal database, genera l'indice FAISS
        e lo scrive su disco. Ritorna il numero di post indicizzati.
        """
        with self.session_factory() as session:
            # Query post pubblicati con embedding non nullo
            posts = session.scalars(
                select(GeneratedPostModel).where(
                    GeneratedPostModel.is_published == True,
                    GeneratedPostModel.embedding != None
                )
            ).all()

            if not posts:
                print("Nessun post pubblicato trovato nel database per l'indicizzazione.")
                # Se l'indice esiste, rimuovilo per consistenza
                if os.path.exists(INDEX_PATH):
                    try:
                        os.remove(INDEX_PATH)
                    except OSError:
                        pass
                return 0

            # Estrai ed analizza il primo embedding per determinare la dimensione dinamicamente
            first_emb = np.frombuffer(posts[0].embedding, dtype=np.float32)
            dimension = len(first_emb)

            # Crea un indice FAISS IndexIDMap2 con IndexFlatIP (Inner Product per cosine similarity su vettori normalizzati)
            flat_index = faiss.IndexFlatIP(dimension)
            index = faiss.IndexIDMap2(flat_index)

            embeddings_list = []
            ids_list = []

            for p in posts:
                emb = np.frombuffer(p.embedding, dtype=np.float32)
                # Normalizzazione per garantire che l'Inner Product calcoli la cosine similarity
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                embeddings_list.append(emb)
                ids_list.append(p.id)

            embeddings_np = np.stack(embeddings_list).astype(np.float32)
            ids_np = np.array(ids_list, dtype=np.int64)

            # Aggiunge i vettori associandoli agli ID del DB
            index.add_with_ids(embeddings_np, ids_np)

            # Salva l'indice su disco
            os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
            faiss.write_index(index, INDEX_PATH)
            print(f"Indice FAISS costruito ed esportato con successo in '{INDEX_PATH}' ({len(posts)} post indicizzati).")
            return len(posts)

    def search_similar_posts(self, query_embedding: np.ndarray, k: int = 2) -> list[int]:
        """
        Cerca nell'indice i k post più simili al vettore fornito.
        Ritorna una lista di ID primari del database dei post correlati.
        """
        if not os.path.exists(INDEX_PATH):
            return []

        try:
            # Carica l'indice da disco
            index = faiss.read_index(INDEX_PATH)
        except Exception as e:
            print(f"Errore nel caricamento dell'indice FAISS da disco: {e}")
            return []

        # Normalizza il vettore di query per cosine similarity
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return []
        q_vec = (query_embedding / query_norm).reshape(1, -1).astype(np.float32)

        # Cerca nell'indice
        distances, indices = index.search(q_vec, k)

        # Ritorna gli ID validi (esclude -1 che rappresenta nessun match)
        matched_ids = [int(idx) for idx in indices[0] if idx != -1]
        return matched_ids
