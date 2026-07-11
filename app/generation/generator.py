import datetime
from config import GEMINI_MOCK_MODE, GEMINI_API_KEY
from app.database.models import ArticleModel
from app.generation.prompts import (
    SYSTEM_INSTRUCTION,
    RAG_USER_PROMPT_TEMPLATE,
    NO_RAG_USER_PROMPT_TEMPLATE
)


class BlogGenerator:

    def __init__(self):
        self.mock_mode = GEMINI_MOCK_MODE
        self.api_key = GEMINI_API_KEY

    def generate_post(self, topic_label: str, keywords: str, search_trends: str, rag_articles: list[ArticleModel], feedback: str = None) -> str:
        if self.mock_mode:
            return self._generate_mock_post(topic_label, keywords, search_trends, rag_articles, feedback=feedback)
        else:
            return self._generate_gemini_post(topic_label, keywords, search_trends, rag_articles, feedback=feedback)

    def _generate_mock_post(self, topic_label: str, keywords: str, search_trends: str, rag_articles: list[ArticleModel], feedback: str = None) -> str:
        # Extract main keywords for header
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        main_kw = kw_list[0].capitalize() if kw_list else "Innovazione Fintech"
        sub_kw = kw_list[1] if len(kw_list) > 1 else "Digital Finance"
        
        date_str = datetime.date.today().strftime("%d %B %Y")
        
        # Build article summaries section
        if rag_articles:
            articles_section = ""
            for i, art in enumerate(rag_articles):
                snippet = art.summary if art.summary else (art.content[:200] + "..." if art.content else "Nessun contenuto disponibile.")
                articles_section += f"### {i+1}. {art.title}\n"
                articles_section += f"*Fonte: {art.source}* | *Link: [{art.url}]({art.url})*\n\n"
                articles_section += f"{snippet}\n\n"
        else:
            articles_section = (
                "*Attenzione: Nessuna fonte RAG diretta disponibile per questo post. "
                "Generato come articolo di analisi teorica e di scenario di mercato.*\n\n"
                "In assenza di notizie dell'ultima ora, l'analisi si concentra sulle dinamiche strutturali "
                "delle infrastrutture bancarie digitali e sulle tendenze di crescita a medio termine.\n\n"
            )

        slug = f"impatto-{main_kw.lower().replace(' ', '-')}-futuro-fintech"
        
        # Mock post template with clean markdown structure and YAML Front Matter
        post_md = f"""---
title: "L'impatto di {main_kw} nel Futuro del Fintech"
meta_description: "Scopri come {main_kw.lower()} e {sub_kw.lower()} stanno ridefinendo i servizi finanziari digitali nel settore fintech."
slug: "{slug}"
---

# L'impatto di {main_kw} nel Futuro del Fintech
*Data di pubblicazione: {date_str}*  
*Trend Keywords: {keywords}*  
*Google Trends Correlati: {search_trends if search_trends else "Nessuno"}*

---

## Introduzione
La rapida evoluzione tecnologica sta spingendo il settore finanziario verso una digitalizzazione senza precedenti. In questo contesto, tematiche calde come **{main_kw.lower()}** e **{sub_kw}** stanno ridefinendo il modo in cui aziende e consumatori interagiscono con il denaro. Questa analisi esplora le ultime novità del mercato basandosi su fonti autorevoli.

## Analisi del Mercato e Notizie Rilevanti
Le recenti notizie evidenziano sviluppi cruciali in ambito **{topic_label.replace("Topic ", "Argomento ")}**:

{articles_section}

## Il Nostro Posizionamento (Fintech Identity)
In linea con le nostre linee guida di posizionamento sul mercato, promuoviamo soluzioni che mettono al centro l'utente, garantendo:
* **Trasparenza e Sicurezza**: Zero compromessi sulla protezione dei dati, in linea con le normative vigenti.
* **Integrazione Open Finance**: Crediamo in ecosistemi aperti e API sicure per abilitare la collaborazione finanziaria.
* **Inclusione e Scalabilità**: Rendiamo i servizi fintech accessibili a tutti, semplificando la complessità operativa.

---
*Vuoi saperne di più? Registrati alla nostra newsletter o contatta il nostro team di esperti.*
"""
        return post_md

    def _generate_gemini_post(self, topic_label: str, keywords: str, search_trends: str, rag_articles: list[ArticleModel], feedback: str = None) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError("Package 'google-genai' is required for Gemini generation. Please run 'pip install google-genai'.")

        if not self.api_key or self.api_key == "MOCK":
            raise ValueError("GEMINI_API_KEY is not configured. Please set a valid API key in config.py.")

        # Initialize the official Gemini SDK client
        client = genai.Client(api_key=self.api_key)

        # Build prompt RAG context or select prompt template
        if rag_articles:
            articles_context = ""
            for i, art in enumerate(rag_articles):
                articles_context += f"--- SOURCE ARTICLE {i+1} ---\n"
                articles_context += f"Title: {art.title}\n"
                articles_context += f"Source: {art.source}\n"
                articles_context += f"URL: {art.url}\n"
                articles_context += f"Summary/Content: {art.content if art.content else art.summary}\n\n"
            
            user_content = RAG_USER_PROMPT_TEMPLATE.format(
                topic_label=topic_label,
                keywords=keywords,
                search_trends=search_trends,
                articles_context=articles_context
            )
        else:
            user_content = NO_RAG_USER_PROMPT_TEMPLATE.format(
                topic_label=topic_label,
                keywords=keywords,
                search_trends=search_trends
            )

        # Se è presente un feedback correttivo, lo appendiamo in fondo per forzare le correzioni SEO
        if feedback:
            user_content += f"\n\n--- FEEDBACK CORRETTIVO DI COPIATURA (Risolvi obbligatoriamente i seguenti problemi) ---\n{feedback}\n"

        # Generate content using gemini-1.5-flash
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=2048
            )
        )

        return response.text
