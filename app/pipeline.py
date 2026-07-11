import logging
import re
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from config import RSS_FEEDS, DAILY_POST_BUDGET
from app.database.db import init_db
from app.database.repositories import (
    ArticleRepository,
    TopicTrendRepository,
    GenerationPlanRepository,
    TopicRepository,
    GeneratedPostRepository,
)
from app.services.seo_checker import SEOQualityChecker
from app.collectors.rss import RSSCollector
from app.preprocessing.text_cleaner import TextCleaner
from app.preprocessing.deduplicator import Deduplicator
from app.downloaders.article_downloader import ArticleDownloader
from app.compliance.compliance_filter import ComplianceFilter
from app.topic_modeling.bertopic_model import FintechTopicModeler
from app.trend_analysis.scorer import TrendScorer
from app.generation.planner import PostPlanner
from app.generation.rag import RAGRetriever
from app.generation.generator import BlogGenerator
from app.services.embedding import get_embedding_model
from googlenewsdecoder import new_decoderv1

logger = logging.getLogger(__name__)


def init_database():
    """Inizializza lo schema del database ed effettua eventuali migrazioni."""
    logger.info("Inizializzazione database in corso...")
    init_db()
    logger.info("Database inizializzato con successo.")


def run_ingest():
    """Esegue la fase di raccolta, scaricamento e pulizia degli articoli."""
    init_database()
    logger.info("Inizio fase di Ingest degli articoli da feed RSS...")

    collector = RSSCollector(RSS_FEEDS)
    articles = collector.collect()
    logger.info(f"Raccolti {len(articles)} articoli dai feed RSS.")

    if not articles:
        logger.warning("Nessun articolo trovato nei feed RSS.")
        return

    # Prioritizziamo i primi 150 articoli per freschezza
    articles = articles[:150]
    logger.info("Decodifica dei link Google News in corso...")

    def decode_single(article):
        if "news.google.com" in article.url:
            try:
                decoded = new_decoderv1(article.url)
                if decoded.get("status"):
                    article.url = decoded["decoded_url"]
            except Exception as e:
                logger.debug(f"Errore durante la decodifica URL {article.url}: {e}")
        return article

    with ThreadPoolExecutor(max_workers=5) as executor:
        articles = list(executor.map(decode_single, articles))

    deduplicator = Deduplicator()
    articles = deduplicator.process(articles)
    logger.info(f"Trovati {len(articles)} articoli unici dopo la deduplicazione.")

    repository = ArticleRepository()
    new_articles = repository.filter_new_articles(articles)
    logger.info(f"Rilevati {len(new_articles)} nuovi articoli non presenti nel database.")

    if new_articles:
        # Limita a 100 per velocità e stabilità
        new_articles = new_articles[:100]
        logger.info(f"Scaricamento del testo completo per {len(new_articles)} articoli...")
        downloader = ArticleDownloader()
        new_articles = downloader.process(new_articles)
        logger.info(f"Download completato. Articoli scaricati con successo: {len(new_articles)}.")

        logger.info("Pulizia del testo e standardizzazione date...")
        cleaner = TextCleaner()
        new_articles = cleaner.process(new_articles)

        logger.info("Salvataggio articoli nel database...")
        saved_count = repository.save_many(new_articles)
        logger.info(f"Salvati {saved_count} nuovi articoli nel database SQLite.")
    else:
        logger.info("Nessun nuovo articolo da scaricare o salvare.")


def run_compliance():
    """Valuta la conformità del brand per tutti gli articoli in stato pendente."""
    init_database()
    logger.info("Inizio fase di Compliance check per articoli pendenti...")

    repository = ArticleRepository()
    pending_articles = repository.get_pending_compliance()
    
    if pending_articles:
        logger.info(f"Trovati {len(pending_articles)} articoli in attesa di valutazione compliance.")
        comp_filter = ComplianceFilter()
        comp_filter.evaluate_articles(pending_articles, repository)
    else:
        logger.info("Nessun articolo pendente da verificare.")


def run_classify_new_articles():
    """Classifica gli articoli conformi appena inseriti usando il modello BERTopic esistente."""
    init_database()
    logger.info("Avvio classificazione automatica nuovi articoli con modello esistente...")
    
    article_repo = ArticleRepository()
    topic_repo = TopicRepository()
    
    # 1. Recupera gli articoli conformi senza topic assegnato
    from app.database.db import SessionLocal
    from app.database.models import ArticleModel
    from sqlalchemy import select
    
    with SessionLocal() as session:
        pending_articles = session.scalars(
            select(ArticleModel).where(
                ArticleModel.is_compliant == True,
                ArticleModel.topic_id == None
            )
        ).all()
        
    if not pending_articles:
        logger.info("Nessun nuovo articolo conforme da classificare.")
        return
        
    logger.info(f"Trovati {len(pending_articles)} articoli conformi senza topic.")
    
    # 2. Carica la mappa dei topic attivi
    active_topics_map = topic_repo.get_active_topics_map()
    active_labels_map = topic_repo.get_active_topic_labels_map()
    
    if not active_topics_map:
        logger.warning("Nessun topic attivo registrato nel database. Esegui prima la fase di addestramento 'analyze'.")
        return
        
    # 3. Esegui la classificazione dei testi con BERTopic
    modeler = FintechTopicModeler()
    texts = []
    for a in pending_articles:
        title = a.title or ""
        summary = a.summary or ""
        content = a.content or ""
        text = f"{title}\n{summary}\n{content}".strip()
        texts.append(text or "Empty article")
        
    predicted_bertopic_ids = modeler.predict_topics(texts)
    
    updates = []
    for i, a in enumerate(pending_articles):
        pred_bt_id = predicted_bertopic_ids[i]
        
        # Mappa il BERTopic ID all'ID primario del database
        db_topic_id = active_topics_map.get(pred_bt_id)
        # Se non trovato, proviamo a metterlo in 'Other / Unclassified' (solitamente -1)
        if db_topic_id is None:
            db_topic_id = active_topics_map.get(-1)
            
        label = active_labels_map.get(pred_bt_id, "Other / Unclassified") if db_topic_id is not None else "Other / Unclassified"
        
        updates.append({
            "id": a.id,
            "topic_id": db_topic_id,
            "topic_label": label
        })
        
    logger.info(f"Salvataggio delle predizioni dei topic per {len(updates)} articoli...")
    article_repo.update_article_topics(updates)


def run_analyze():
    """Esegue topic modeling BERTopic, scoring dei trend XGBoost e pianificazione dei post."""
    init_database()
    logger.info("Inizio fase di Analisi dei Trend e Topic Modeling...")

    article_repo = ArticleRepository()
    trend_repo = TopicTrendRepository()
    plan_repo = GenerationPlanRepository()

    # Recupera solo gli articoli recenti delle ultime 2 settimane (con fallback a minimo 100 articoli)
    all_articles = article_repo.get_articles_for_training(days=14, min_count=100)
    logger.info(f"Recuperati {len(all_articles)} articoli (finestra mobile 14gg o fallback) dal database per l'analisi.")

    if not all_articles:
        logger.warning("Nessun articolo presente nel database. Topic modeling interrotto.")
        return

    logger.info("Esecuzione BERTopic per la scoperta e classificazione dei topic...")
    modeler = FintechTopicModeler()
    try:
        topics, topic_labels, topic_keywords = modeler.train(all_articles, repository=article_repo)
        
        # Prepara i dati dei topic scoperti da salvare storicamente
        discovered_topics = []
        for topic_id, label in topic_labels.items():
            discovered_topics.append({
                "topic_id": topic_id,
                "label": label,
                "keywords": topic_keywords.get(topic_id, "")
            })
            
        topic_repo = TopicRepository()
        bertopic_to_db_map = topic_repo.save_topics(discovered_topics)
        
        updates = []
        for i, article in enumerate(all_articles):
            bt_id = int(topics[i])
            db_id = bertopic_to_db_map.get(bt_id)
            label = topic_labels.get(bt_id, "Unknown")
            
            # Mutazione in-place per l'analisi successiva del trend scorer
            article.topic_id = db_id
            article.topic_label = label
            
            updates.append({
                "id": article.id,
                "topic_id": db_id,
                "topic_label": label
            })

        logger.info("Aggiornamento dei topic assegnati agli articoli nel database...")
        article_repo.update_article_topics(updates)

        logger.info("Calcolo ed elaborazione del punteggio dei trend con XGBoost...")
        scorer = TrendScorer()
        trends = scorer.calculate_trends(all_articles)
        
        logger.info("Salvataggio dei trend aggiornati nel database...")
        trend_repo.save_topic_trends(trends)

        # Log dei trend rilevati
        logger.info("=== SUMMARY DEI TOPIC TRENDS (Primi 10) ===")
        for t in trends[:10]:
            topic_id = t["topic_id"]
            topic_articles = [a for a in all_articles if a.topic_id == topic_id]
            total_vol = len(topic_articles)
            compliant_vol = sum(1 for a in topic_articles if a.is_compliant is True)
            
            logger.info(
                f"[Score: {t['trend_score']:7.2f}] {t['topic_label']} "
                f"(Volume: {total_vol}, Compliant: {compliant_vol}/{total_vol}, "
                f"Freshness: {t['freshness_score']:.2f})"
            )
        logger.info("==========================================")

        logger.info("Generazione del piano di allocazione post giornaliero...")
        planner = PostPlanner()
        # Mappa le keywords usando l'ID di database del topic invece del BERTopic ID
        db_topic_keywords = {
            bertopic_to_db_map[bt_id]: kw
            for bt_id, kw in topic_keywords.items()
            if bt_id in bertopic_to_db_map
        }
        plan = planner.plan_posts(all_articles, trends, topic_keywords=db_topic_keywords)
        
        logger.info("Salvataggio del piano di generazione nel database...")
        plan_repo.save_generation_plan(plan)

        logger.info("=== PIANO DI ALLOCAZIONE POST GIORNALIERO ===")
        for p in plan:
            if p["allocated_posts"] > 0:
                logger.info(
                    f"[{p['allocated_posts']:2d} post] {p['topic_label']} | "
                    f"Trend Score: {p['trend_score']:.2f} | "
                    f"Compliance: {int(p['compliance_rate'] * 100)}%"
                )
        logger.info("=============================================")

    except Exception as e:
        logger.exception(f"Errore critico durante la fase di analisi e topic modeling: {e}")


def run_generate():
    """Esegue la generazione dei post tramite RAG basandosi sul piano salvato nel database."""
    init_database()
    logger.info("Inizio fase di Generazione Post tramite RAG...")

    # Assicura che la directory di output esista
    posts_dir = Path("data/posts")
    posts_dir.mkdir(parents=True, exist_ok=True)

    # Pulizia vecchi post per evitare sovrapposizioni
    for f in posts_dir.glob("*.md"):
        try:
            f.unlink()
        except OSError as e:
            logger.warning(f"Impossibile rimuovere il file {f}: {e}")

    article_repo = ArticleRepository()
    plan_repo = GenerationPlanRepository()
    generator = BlogGenerator()

    # Query piani attivi
    plans = plan_repo.get_active_plans()

    if not plans:
        logger.warning("Nessun piano di generazione attivo trovato nel database. Esegui prima la fase 'analyze'.")
        return

    # Carica il modello SentenceTransformer dal singleton service
    logger.info("Recupero del SentenceTransformer condiviso per codifica query RAG...")
    encoder = get_embedding_model()

    total_generated = 0

    for plan in plans:
        topic_id = plan.topic_id
        topic_label = plan.topic_label
        budget = plan.allocated_posts
        keywords = plan.keywords if plan.keywords else ""
        search_trends = plan.search_trends if plan.search_trends else ""

        logger.info(f"Elaborazione Topic {topic_id}: '{topic_label}' (Post da generare: {budget})")

        # Recupera articoli utilizzabili (compliant e non ancora usati)
        unused_articles = article_repo.get_unused_compliant_by_topic(topic_id)
        
        retrieved_all = []
        if unused_articles:
            # Costruisce l'indice FAISS in memoria al volo
            retriever = RAGRetriever()
            built = retriever.build_index(unused_articles)

            if built:
                keywords_list = [k.strip() for k in keywords.split(",") if k.strip()]
                seed_query = " ".join(keywords_list[:2]) if keywords_list else topic_label
                
                # Calcola il vettore della query
                query_vector = encoder.encode(seed_query, convert_to_numpy=True)
                
                # Estrae 3 fonti per ogni post pianificato
                k_total = 3 * budget
                retrieved_all = retriever.retrieve(query_vector, k=k_total)

        # Raggruppa gli articoli per chunk da 3
        chunks = [retrieved_all[i : i + 3] for i in range(0, len(retrieved_all), 3)]

        post_repo = GeneratedPostRepository()
        seo_checker = SEOQualityChecker()

        # Carica gli embedding esistenti per il confronto
        past_posts = post_repo.get_all_embeddings()
        past_embeddings = [np.frombuffer(p[1], dtype=np.float32) for p in past_posts]

        for post_idx in range(1, budget + 1):
            post_articles = chunks[post_idx - 1] if post_idx - 1 < len(chunks) else []

            post_content = generator.generate_post(
                topic_label=topic_label,
                keywords=keywords,
                search_trends=search_trends,
                rag_articles=post_articles
            )

            # Estrai slug e titolo dal Front Matter
            slug_match = re.search(r"^slug:\s*(.+)$", post_content, re.MULTILINE)
            slug = slug_match.group(1).strip("'\" ") if slug_match else f"topic-{topic_id}-post-{post_idx}"
            url = f"/blog/{slug}"

            title_match = re.search(r"^title:\s*(.+)$", post_content, re.MULTILINE)
            title = title_match.group(1).strip("'\" ") if title_match else f"Post {topic_label}"

            # Valutazione SEO iniziale
            seo_res = seo_checker.check_seo(post_content, keywords)
            seo_score = seo_res["score"]

            # Auto-correzione: se il punteggio SEO è inferiore a 60, tenta un secondo invio correttivo
            if seo_score < 60.0:
                logger.warning(f"  [Post {post_idx}/{budget}] Punteggio SEO insufficiente ({seo_score}/100). Tentativo di auto-correzione...")
                feedback = (
                    f"Il testo precedente ha ottenuto un punteggio SEO insufficiente ({seo_score}/100) per i seguenti motivi:\n"
                    + "\n".join([f"- {w}" for w in seo_res["warnings"]])
                    + "\nPer favore riscrivi l'articolo assicurandoti di espanderlo (minimo 500 parole), strutturare bene gli heading H1 (# ), H2 (## ), H3 (### ) ed inserire in modo naturale le parole chiave."
                )
                post_content = generator.generate_post(
                    topic_label=topic_label,
                    keywords=keywords,
                    search_trends=search_trends,
                    rag_articles=post_articles,
                    feedback=feedback
                )
                
                # Rivalutazione SEO post-correzione
                seo_res = seo_checker.check_seo(post_content, keywords)
                seo_score = seo_res["score"]
                
                # Riestrai titolo e slug corretti se cambiati
                slug_match = re.search(r"^slug:\s*(.+)$", post_content, re.MULTILINE)
                if slug_match:
                    slug = slug_match.group(1).strip("'\" ")
                    url = f"/blog/{slug}"
                title_match = re.search(r"^title:\s*(.+)$", post_content, re.MULTILINE)
                if title_match:
                    title = title_match.group(1).strip("'\" ")

            # Calcolo embedding del post
            new_emb = encoder.encode(post_content, convert_to_numpy=True)
            
            # Controllo duplicati semantici
            max_sim = seo_checker.check_similarity(new_emb, past_embeddings)
            if max_sim > 0.92:
                logger.warning(f"  [Post {post_idx}/{budget}] ALTA SIMILARITÀ rilevata ({max_sim:.2%}) con post storici. Possibile duplicato!")

            # Salvataggio nel database
            needs_review_flag = seo_score < 60.0
            post_repo.save_post(
                topic_id=topic_id,
                title=title,
                content=post_content,
                url=url,
                embedding=new_emb.astype(np.float32).tobytes(),
                seo_score=seo_score,
                max_similarity=max_sim,
                needs_review=needs_review_flag
            )

            # Aggiungi il nuovo embedding alla lista per i confronti successivi nello stesso batch
            past_embeddings.append(new_emb)

            # Salvataggio su file markdown
            filename = f"topic_{topic_id}_post_{post_idx}.md"
            filepath = posts_dir / filename
            filepath.write_text(post_content, encoding="utf-8")

            is_rag = "RAG" if post_articles else "NO-RAG"
            review_status = " [NECESSITA REVISIONE]" if needs_review_flag else ""
            logger.info(
                f"  [Post {post_idx}/{budget}] Generato '{filename}' ({is_rag} mode, "
                f"SEO Score: {seo_score}/100, Max Similarity: {max_sim:.2%}){review_status}"
            )
            total_generated += 1

        # Aggiorna gli articoli come usati
        if retrieved_all:
            used_ids = [art.id for art in retrieved_all]
            article_repo.mark_articles_as_used(used_ids)
            logger.info(f"  Marcati {len(used_ids)} articoli come utilizzati nel database.")

    logger.info(f"Generazione completata con successo! Creati {total_generated} post in: {posts_dir.resolve()}")


def run_all():
    """Esegue l'intero flusso sequenzialmente in un unico ciclo."""
    logger.info("=== AVVIO PIPELINE END-TO-END ===")
    run_ingest()
    run_compliance()
    run_analyze()
    run_generate()
    logger.info("=== PIPELINE COMPLETATA CON SUCCESSO ===")
