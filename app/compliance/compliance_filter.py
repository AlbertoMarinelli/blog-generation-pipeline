import re
import numpy as np

from config import COMPETITOR_BLACKLIST_PATH, BRAND_IDENTITY_PATH, COMPLIANCE_SIMILARITY_THRESHOLD
from app.database.models import ArticleModel
from app.services.embedding import get_embedding_model


class ComplianceFilter:
    """Evaluates whether crawled articles align with brand identity guidelines and avoid competitors."""

    def __init__(self):
        self._brand_embedding = None

    def _get_encoder(self):
        """Helper to retrieve the shared embedding model."""
        return get_embedding_model()

    def _get_brand_embedding(self) -> np.ndarray:
        """Retrieves or computes the brand identity embedding vector.

        Returns:
            np.ndarray: The embedding vector representing the brand identity guidelines.
        """
        if self._brand_embedding is None:
            # Read Brand Identity text
            try:
                with open(BRAND_IDENTITY_PATH, "r", encoding="utf-8") as f:
                    text = f.read().strip()
            except Exception as e:
                print(f"Warning: could not read brand_identity.txt from {BRAND_IDENTITY_PATH}: {e}. Using fallback.")
                # [DIDACTIC_LIMITATION] Fallback brand description used to ensure compliance filter runs without dependency on external txt configuration.
                text = "Open banking, financial APIs, digital payments, B2B fintech SaaS."

            if not text:
                text = "Open banking, financial APIs, digital payments, B2B fintech SaaS."

            encoder = self._get_encoder()
            self._brand_embedding = encoder.encode(text, convert_to_numpy=True)
            print(f"Loaded brand identity manifesto for semantic similarity checking.")
        return self._brand_embedding

    def evaluate_articles(self, articles: list[ArticleModel], repository) -> list[dict]:
        """Evaluates compliance for a batch of articles against blacklists and brand guidelines.

        Updates the database with compliance status and computed article embeddings.

        Args:
            articles (list[ArticleModel]): The database article models to check.
            repository (ArticleRepository): Repository class to persist results.

        Returns:
            list[dict]: List of update dictionaries with compliance status.
        """
        if not articles:
            return []

        print(f"Evaluating brand compliance for {len(articles)} articles...")
        brand_emb = self._get_brand_embedding()
        updates = []

        # Read blacklist words from file
        try:
            with open(COMPETITOR_BLACKLIST_PATH, "r", encoding="utf-8") as f:
                blacklist_words = [line.strip().lower() for line in f if line.strip()]
        except Exception as e:
            print(f"Warning: could not read competitor blacklist from {COMPETITOR_BLACKLIST_PATH}: {e}. Blacklist check skipped.")
            blacklist_words = []

        # Pre-compile regex for blacklist words with word boundaries
        blacklist_regexes = [
            re.compile(rf"\b{re.escape(comp)}\b") 
            for comp in blacklist_words
        ]

        for a in articles:
            # Combine title, summary, and content for analysis
            title = a.title or ""
            summary = a.summary or ""
            content = a.content or ""
            
            combined_text = f"{title}\n{summary}\n{content}".strip()
            combined_text_lower = combined_text.lower()

            # 1. Blacklist Check
            is_blacklisted = False
            for r in blacklist_regexes:
                if r.search(combined_text_lower):
                    is_blacklisted = True
                    break

            if is_blacklisted:
                updates.append({
                    "id": a.id,
                    "is_compliant": False,
                    "compliance_reason": "blacklist"
                })
                continue

            # 2. Semantic Similarity Check
            # Reuse cached embedding if already computed
            if a.embedding is not None:
                emb = np.frombuffer(a.embedding, dtype=np.float32)
                emb_bytes = a.embedding
            else:
                # Compute embedding on-the-fly
                text_to_encode = combined_text if combined_text else "Empty article"
                encoder = self._get_encoder()
                emb = encoder.encode(text_to_encode, convert_to_numpy=True)
                emb_bytes = emb.astype(np.float32).tobytes()

            # Compute cosine similarity
            dot_product = np.dot(emb, brand_emb)
            norm_emb = np.linalg.norm(emb)
            norm_brand = np.linalg.norm(brand_emb)
            similarity = float(dot_product / (norm_emb * norm_brand)) if norm_emb > 0 and norm_brand > 0 else 0.0

            # Determine compliance status based on threshold limit
            if similarity >= COMPLIANCE_SIMILARITY_THRESHOLD:
                updates.append({
                    "id": a.id,
                    "is_compliant": True,
                    "compliance_reason": "compliant",
                    "embedding": emb_bytes
                })
            else:
                updates.append({
                    "id": a.id,
                    "is_compliant": False,
                    "compliance_reason": "low_similarity",
                    "embedding": emb_bytes
                })

        if updates:
            # Persist results in batch database transaction
            repository.update_article_compliance(updates)
            
            reasons = [u["compliance_reason"] for u in updates]
            print(f"Compliance evaluation finished. "
                  f"Compliant: {reasons.count('compliant')}, "
                  f"Blocked (Blacklist): {reasons.count('blacklist')}, "
                  f"Blocked (Low Similarity): {reasons.count('low_similarity')}")

        return updates
