import re
import numpy as np

class SEOQualityChecker:
    """Evaluates the SEO quality of generated articles and analyzes semantic similarity with past posts."""

    def check_seo(self, text: str, keywords: str) -> dict:
        """Evaluates the SEO quality of an article based on length, heading structure, and keyword density.

        Maximum score is 100.0.

        Args:
            text (str): The markdown text content of the article.
            keywords (str): A comma-separated list of keywords.

        Returns:
            dict: Analysis results containing the score and detailed warnings if any.
        """
        if not text:
            return {"score": 0, "details": "Empty article.", "warnings": ["Content missing"]}

        # 1. Word Count Check (Weight: 30%)
        words = text.split()
        word_count = len(words)
        if word_count >= 500:
            word_score = 100.0
        else:
            word_score = (word_count / 500.0) * 100.0

        warnings = []
        if word_count < 500:
            warnings.append(f"Article too short: {word_count} words (minimum recommended: 500).")

        # 2. Heading Structure Check (Weight: 20%)
        # Count H1 headings (e.g. lines starting with '# ')
        h1_matches = re.findall(r"^#\s+.+", text, re.MULTILINE)
        h1_count = len(h1_matches)
        
        # Count H2 and H3 headings
        h2_count = len(re.findall(r"^##\s+.+", text, re.MULTILINE))
        h3_count = len(re.findall(r"^###\s+.+", text, re.MULTILINE))

        heading_score = 100.0
        if h1_count != 1:
            heading_score -= 50.0  # Severe penalty for missing or multiple H1 tags
            warnings.append(f"Found {h1_count} H1 headings (exactly one is required).")
        if h2_count == 0:
            heading_score -= 30.0  # Penalty for missing H2 sections
            warnings.append("Missing H2 headings to structure the content.")
        
        heading_score = max(0.0, heading_score)

        # 3. Keyword Presence Check (Weight: 30%)
        kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        present_kws = 0
        text_lower = text.lower()

        for kw in kw_list:
            if kw in text_lower:
                present_kws += 1
            else:
                warnings.append(f"Keyword '{kw}' not found in content.")

        if kw_list:
            kw_presence_score = (present_kws / len(kw_list)) * 100.0
        else:
            kw_presence_score = 100.0

        # 4. Keyword Density Check (Weight: 20%)
        # Analyze density of the primary keyword (first in the list)
        density_score = 100.0
        primary_kw = kw_list[0] if kw_list else None
        
        if primary_kw and word_count > 0:
            kw_occurrences = text_lower.count(primary_kw)
            primary_kw_words_count = len(primary_kw.split())
            density = (kw_occurrences * primary_kw_words_count) / word_count
            
            # Optimal density is between 0.8% and 3.0%
            if density < 0.008:
                density_score = (density / 0.008) * 100.0
                warnings.append(f"Low density of primary keyword '{primary_kw}': {density:.2%} (optimal: 0.8% - 3.0%).")
            elif density > 0.03:
                # Penalize keyword stuffing
                density_score = max(0.0, 100.0 - (density - 0.03) * 1000.0)
                warnings.append(f"Keyword stuffing detected for '{primary_kw}': {density:.2%} (higher than 3.0%).")
        else:
            density_score = 100.0

        # Calculate weighted final SEO score
        total_score = (
            (word_score * 0.3) +
            (heading_score * 0.2) +
            (kw_presence_score * 0.3) +
            (density_score * 0.2)
        )

        return {
            "score": round(total_score, 1),
            "word_count": word_count,
            "h1_count": h1_count,
            "h2_count": h2_count,
            "h3_count": h3_count,
            "warnings": warnings
        }

    def check_similarity(self, new_emb: np.ndarray, past_embs: list[np.ndarray]) -> float:
        """Calculates maximum cosine similarity between a new post embedding and historical post embeddings.

        Args:
            new_emb (np.ndarray): Embedding vector of the new article.
            past_embs (list[np.ndarray]): List of embedding vectors of historical articles.

        Returns:
            float: Maximum similarity score (0.0 to 1.0).
        """
        if not past_embs:
            return 0.0

        new_norm = np.linalg.norm(new_emb)
        if new_norm == 0:
            return 0.0

        similarities = []
        for emb in past_embs:
            norm = np.linalg.norm(emb)
            if norm == 0:
                continue
            cos = np.dot(new_emb, emb) / (new_norm * norm)
            similarities.append(float(cos))

        return max(similarities) if similarities else 0.0
