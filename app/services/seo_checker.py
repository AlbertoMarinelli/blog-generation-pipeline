import re
import numpy as np

class SEOQualityChecker:

    def check_seo(self, text: str, keywords: str) -> dict:
        """
        Valuta la qualità SEO di un articolo e restituisce un dizionario con i dettagli.
        Punteggio massimo: 100.
        """
        if not text:
            return {"score": 0, "details": "Articolo vuoto.", "warnings": ["Contenuto assente"]}

        # 1. Word Count Check (Peso: 30%)
        words = text.split()
        word_count = len(words)
        if word_count >= 500:
            word_score = 100.0
        else:
            word_score = (word_count / 500.0) * 100.0

        warnings = []
        if word_count < 500:
            warnings.append(f"Articolo troppo corto: {word_count} parole (minimo consigliato: 500).")

        # 2. Heading Structure Check (Peso: 20%)
        # Conteggio dei titoli H1 (es. righe che iniziano con # )
        h1_matches = re.findall(r"^#\s+.+", text, re.MULTILINE)
        h1_count = len(h1_matches)
        
        # Conteggio H2/H3
        h2_count = len(re.findall(r"^##\s+.+", text, re.MULTILINE))
        h3_count = len(re.findall(r"^###\s+.+", text, re.MULTILINE))

        heading_score = 100.0
        if h1_count != 1:
            heading_score -= 50.0  # Penalità severa per mancanza o molteplicità di H1
            warnings.append(f"Trovati {h1_count} titoli H1 (deve essercene esattamente uno).")
        if h2_count == 0:
            heading_score -= 30.0  # Penalità per mancanza di sezioni H2
            warnings.append("Mancanza di titoli H2 per strutturare il testo.")
        
        heading_score = max(0.0, heading_score)

        # 3. Keyword Presence Check (Peso: 30%)
        kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        present_kws = 0
        text_lower = text.lower()

        for kw in kw_list:
            if kw in text_lower:
                present_kws += 1
            else:
                warnings.append(f"Parola chiave '{kw}' non trovata nel testo.")

        if kw_list:
            kw_presence_score = (present_kws / len(kw_list)) * 100.0
        else:
            kw_presence_score = 100.0

        # 4. Keyword Density Check (Peso: 20%)
        # Calcoliamo la densità della parola chiave principale (la prima della lista)
        density_score = 100.0
        primary_kw = kw_list[0] if kw_list else None
        
        if primary_kw and word_count > 0:
            kw_occurrences = text_lower.count(primary_kw)
            primary_kw_words_count = len(primary_kw.split())
            density = (kw_occurrences * primary_kw_words_count) / word_count
            
            # Densità ottimale tra 0.8% e 3.0%
            if density < 0.008:
                density_score = (density / 0.008) * 100.0
                warnings.append(f"Bassa densità della keyword principale '{primary_kw}': {density:.2%} (ottimale: 0.8% - 3.0%).")
            elif density > 0.03:
                # Penalizza il keyword stuffing
                density_score = max(0.0, 100.0 - (density - 0.03) * 1000.0)
                warnings.append(f"Keyword stuffing rilevato per '{primary_kw}': {density:.2%} (superiore al 3.0%).")
        else:
            density_score = 100.0

        # Calcolo Punteggio Finale Pesato
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
        """
        Calcola la massima somiglianza coseno tra il nuovo embedding e quelli precedentemente generati.
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
