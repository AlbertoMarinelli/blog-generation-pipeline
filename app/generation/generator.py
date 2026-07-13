import datetime
import os
from jinja2 import Environment, FileSystemLoader
from config import GEMINI_MOCK_MODE, GEMINI_API_KEY
from app.database.models import ArticleModel


class BlogGenerator:
    """Generates SEO-compliant blog posts using either a local mock template or the Google Gemini LLM API."""

    def __init__(self):
        self.mock_mode = GEMINI_MOCK_MODE
        self.api_key = GEMINI_API_KEY
        
        # Initialize the Jinja2 environment for rendering prompt templates
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))

    def generate_post(self, topic_label: str, keywords: str, search_trends: str, rag_articles: list[ArticleModel], feedback: str = None) -> str:
        """Generates a blog post using Gemini or the fallback mock generator depending on configuration.

        Args:
            topic_label (str): Label of the selected trend topic.
            keywords (str): Associated keywords.
            search_trends (str): Related search queries from Google Trends.
            rag_articles (list[ArticleModel]): List of referenced source articles.
            feedback (str, optional): Corrective feedback for auto-correction loops.

        Returns:
            str: Generated post content in markdown format.
        """
        # [DIDACTIC_LIMITATION] Uses a rule-based mock post template if real LLM API keys are not supplied.
        if self.mock_mode:
            return self._generate_mock_post(topic_label, keywords, search_trends, rag_articles, feedback=feedback)
        else:
            return self._generate_gemini_post(topic_label, keywords, search_trends, rag_articles, feedback=feedback)

    def _generate_mock_post(self, topic_label: str, keywords: str, search_trends: str, rag_articles: list[ArticleModel], feedback: str = None) -> str:
        import re
        import random
        import datetime

        def slugify(text: str) -> str:
            text = text.lower()
            text = re.sub(r'[^\w\s-]', '', text)
            text = re.sub(r'[\s_-]+', '-', text)
            return text.strip('-')

        # Extract main keywords for header
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        main_kw = kw_list[0].capitalize() if kw_list else "Innovazione Fintech"
        sub_kw = kw_list[1] if len(kw_list) > 1 else "Digital Finance"
        
        date_str = datetime.date.today().strftime("%d %B %Y")
        
        # Determine Title, Slug, Meta Description, and Body based on RAG articles
        if rag_articles:
            # Take title and part of description from the first RAG article to make posts diverse
            ref_art = rag_articles[0]
            title = ref_art.title if ref_art.title else f"Dinamiche di Mercato su {topic_label}"
            title = title.replace('"', '\\"') # escape quotes for frontmatter
            
            # Create a unique slug from title
            slug = slugify(title)
            if not slug:
                slug = f"focus-{main_kw.lower().replace(' ', '-')}-futuro-fintech-{random.randint(100, 999)}"
            
            snippet = ref_art.summary if ref_art.summary else (ref_art.content[:150] + "..." if ref_art.content else "analisi dettagliata")
            meta_description = f"Scopri di più su: {title}. {snippet}"
            if len(meta_description) > 160:
                meta_description = meta_description[:157] + "..."
            meta_description = meta_description.replace('"', '\\"')
            
            # Build article summaries section
            articles_section = "### Articoli e Notizie analizzate:\n\n"
            for i, art in enumerate(rag_articles):
                art_snippet = art.summary if art.summary else (art.content[:300] + "..." if art.content else "Nessun contenuto disponibile.")
                articles_section += f"#### {i+1}. {art.title}\n"
                articles_section += f"*Fonte: {art.source}* | *Link: [{art.url}]({art.url})*\n\n"
                articles_section += f"{art_snippet}\n\n"
        else:
            # Standard fallback
            rand_id = random.randint(100, 999)
            title = f"L'impatto di {main_kw} nel Futuro del Fintech (Analisi {rand_id})"
            slug = f"impatto-{main_kw.lower().replace(' ', '-')}-futuro-fintech-{rand_id}"
            meta_description = f"Scopri come {main_kw.lower()} e {sub_kw.lower()} stanno ridefinendo i servizi finanziari digitali nel settore fintech."
            articles_section = (
                "*Attenzione: Nessuna fonte RAG diretta disponibile per questo post. "
                "Generato come articolo di analisi teorica e di scenario di mercato.*\n\n"
                "In assenza di notizie dell'ultima ora, l'analisi si concentra sulle dinamiche strutturali "
                "delle infrastrutture bancarie digitali e sulle tendenze di crescita a medio termine.\n\n"
            )

        # Mock post template with clean markdown structure and YAML Front Matter
        post_md = f"""---
title: "{title}"
meta_description: "{meta_description}"
slug: "{slug}"
---

# {title}
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

        # Load and render prompt configuration using Jinja2 templates
        template = self.jinja_env.get_template('post_generation.jinja')
        user_content = template.render(
            topic_label=topic_label,
            keywords=keywords,
            search_trends=search_trends,
            rag_articles=rag_articles,
            feedback=feedback
        )

        # Load system instruction profile from template
        system_instruction_tmpl = self.jinja_env.get_template('system_instruction.jinja')
        system_instruction = system_instruction_tmpl.render()

        # Generate content using gemini-1.5-flash
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=2048
            )
        )

        return response.text
