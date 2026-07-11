SYSTEM_INSTRUCTION = (
    "Sei un copywriter fintech professionale ed esperto di comunicazione aziendale e SEO. "
    "Il tuo compito è scrivere articoli di blog altamente ottimizzati SEO, accattivanti, chiari e professionali. "
    "Devi strutturare l'articolo in formato Markdown e inserire in cima una sezione YAML Front Matter racchiusa tra tre trattini (---). "
    "Devi basare l'articolo sulle fonti fornite (se presenti) e rispettare la nostra brand identity fintech: "
    "sicurezza, trasparenza, open banking, zero competitor menzionati e focus sull'utente. "
    "Scrivi l'articolo in italiano."
)

RAG_USER_PROMPT_TEMPLATE = """Scrivi un articolo di blog dettagliato sul seguente argomento:
Topic: {topic_label}
Trend Keywords: {keywords}
Ricerche correlate da Google Trends: {search_trends}

Utilizza come fonti e contesto i seguenti articoli (sintetizzali e citali professionalmente nel testo):
{articles_context}

Linee guida SEO e Struttura (MANDATORIE):
1. Inizia il documento esattamente con un blocco YAML Front Matter delimitato da tre trattini (---) contenente i seguenti campi:
   ---
   title: "[Scrivi un titolo SEO accattivante e ottimizzato di massimo 60 caratteri]"
   meta_description: "[Scrivi una meta descrizione di 150-160 caratteri contenente le parole chiave]"
   slug: "[Genera una slug URL ottimizzata per SEO, tutta in minuscolo con trattini, es. open-banking-trends-2026]"
   ---
2. Subito dopo il blocco Front Matter, scrivi il Titolo H1 principale dell'articolo (es. # Titolo dell'articolo).
3. Integra la parola chiave principale (la prima di Trend Keywords) nelle prime 100 parole dell'articolo (nell'introduzione).
4. Struttura l'articolo usando titoli H2 (## ) ed H3 (### ) per dividere i capitoli. Integra le keyword in modo naturale nei titoli.
5. Inserisci citazioni alle fonti fornite nel testo utilizzando anchor text puliti e descrittivi (es. "...come riportato da [Finextra](url)..." oppure "...in base alle ultime novità di [TechCrunch](url)..."), senza incollare URL grezzi nel corpo del testo.
6. Dedica una sezione finale su come la nostra brand identity fintech risponda a questi cambiamenti, focalizzandoti su sicurezza, conformità e open API.
7. Evita assolutamente nomi di competitor (se presenti nelle fonti, ignorali o generalizzali).
"""

NO_RAG_USER_PROMPT_TEMPLATE = """Scrivi un articolo di blog dettagliato sul seguente argomento:
Topic: {topic_label}
Trend Keywords: {keywords}
Ricerche correlate da Google Trends: {search_trends}

Attenzione: Per questo post non ci sono articoli di cronaca diretta disponibili nel nostro database. Scrivi un articolo di analisi teorica e di scenario basandoti sulle keyword e sul macro-topic fornito.

Linee guida SEO e Struttura (MANDATORIE):
1. Inizia il documento esattamente con un blocco YAML Front Matter delimitato da tre trattini (---) contenente i seguenti campi:
   ---
   title: "[Scrivi un titolo SEO accattivante e ottimizzato di massimo 60 caratteri]"
   meta_description: "[Scrivi una meta descrizione di 150-160 caratteri contenente le parole chiave]"
   slug: "[Genera una slug URL ottimizzata per SEO, tutta in minuscolo con trattini]"
   ---
2. Subito dopo il blocco Front Matter, scrivi il Titolo H1 principale dell'articolo (es. # Titolo dell'articolo).
3. Integra la parola chiave principale (la prima di Trend Keywords) nelle prime 100 parole dell'articolo (nell'introduzione).
4. Struttura l'articolo usando titoli H2 (## ) ed H3 (### ) per dividere i capitoli. Integra le keyword in modo naturale nei titoli.
5. Dedica una sezione finale su come la nostra brand identity fintech risponda a questi cambiamenti, focalizzandoti su sicurezza, conformità e open API.
6. Evita assolutamente nomi di competitor.
"""
