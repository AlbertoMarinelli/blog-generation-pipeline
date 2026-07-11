SYSTEM_INSTRUCTION = (
    "Sei un copywriter fintech professionale ed esperto di comunicazione aziendale. "
    "Il tuo compito è scrivere articoli di blog ottimizzati SEO, accattivanti, trasparenti e informati. "
    "Devi basare l'articolo sulle fonti fornite (se presenti) e rispettare la nostra brand identity fintech: "
    "sicurezza, trasparenza, open banking, zero competitor menzionati e focus sull'utente. "
    "Scrivi l'articolo in italiano e restituiscilo in formato Markdown puro."
)

RAG_USER_PROMPT_TEMPLATE = """Scrivi un articolo di blog dettagliato sul seguente argomento:
Topic: {topic_label}
Trend Keywords: {keywords}
Ricerche correlate da Google Trends: {search_trends}

Utilizza come fonti e contesto i seguenti articoli (sintetizzali e citali professionalmente nel testo):
{articles_context}

Linee guida di scrittura:
1. Usa un titolo accattivante in H1.
2. Includi un'introduzione che contestualizzi le keyword e le ricerche correlate.
3. Dedica una sezione all'analisi delle notizie fornite (citando le fonti).
4. Dedica una sezione finale su come la nostra brand identity fintech risponda a questi cambiamenti, focalizzandoti su sicurezza, conformità e open API.
5. Evita assolutamente nomi di competitor (se presenti nelle fonti, ignorali o generalizzali).
"""

NO_RAG_USER_PROMPT_TEMPLATE = """Scrivi un articolo di blog dettagliato sul seguente argomento:
Topic: {topic_label}
Trend Keywords: {keywords}
Ricerche correlate da Google Trends: {search_trends}

Attenzione: Per questo post non ci sono articoli di cronaca diretta disponibili nel nostro database. Scrivi un articolo di analisi teorica e di scenario basandoti sulle keyword e sul macro-topic fornito.

Linee guida di scrittura:
1. Usa un titolo accattivante in H1.
2. Includi un'introduzione che contestualizzi le keyword e le ricerche correlate.
3. Dedica una sezione all'analisi del trend di mercato in generale basandoti sulle tue conoscenze del settore fintech.
4. Dedica una sezione finale su come la nostra brand identity fintech risponda a questi cambiamenti, focalizzandoti su sicurezza, conformità e open API.
5. Evita assolutamente nomi di competitor.
"""
