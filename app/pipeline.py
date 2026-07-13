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
    """Initializes the database schema and performs self-healing database migrations."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully.")


def run_ingest():
    """Executes the data collection, fetching, and text pre-processing stage for new articles."""
    init_database()
    logger.info("Starting article ingestion from RSS feeds...")

    collector = RSSCollector(RSS_FEEDS)
    articles = collector.collect()
    logger.info(f"Collected {len(articles)} articles from RSS feeds.")

    if not articles:
        logger.warning("No articles found in RSS feeds.")
        return

    # [DIDACTIC_LIMITATION] Slice to the first 150 articles to optimize execution speed in educational demo pipelines.
    # articles = articles[:150]
    logger.info("Decoding Google News links...")

    def decode_single(article):
        if "news.google.com" in article.url:
            try:
                decoded = new_decoderv1(article.url)
                if decoded.get("status"):
                    article.url = decoded["decoded_url"]
            except Exception as e:
                logger.debug(f"Error decoding Google News URL {article.url}: {e}")
        return article

    with ThreadPoolExecutor(max_workers=5) as executor:
        articles = list(executor.map(decode_single, articles))

    deduplicator = Deduplicator()
    articles = deduplicator.process(articles)
    logger.info(f"Found {len(articles)} unique articles after deduplication.")

    repository = ArticleRepository()
    new_articles = repository.filter_new_articles(articles)
    logger.info(f"Identified {len(new_articles)} new articles not currently in the database.")

    if new_articles:
        # [DIDACTIC_LIMITATION] Limit newly downloaded articles to 100 to reduce resource usage and run quicker in local tests.
        # new_articles = new_articles[:100]
        logger.info(f"Downloading full text for {len(new_articles)} articles...")
        downloader = ArticleDownloader()
        new_articles = downloader.process(new_articles)
        logger.info(f"Download complete. Successfully fetched: {len(new_articles)}.")

        logger.info("Cleaning raw texts and standardizing dates...")
        cleaner = TextCleaner()
        new_articles = cleaner.process(new_articles)

        logger.info("Saving processed articles to database...")
        saved_count = repository.save_many(new_articles)
        logger.info(f"Saved {saved_count} new articles into the SQLite database.")
    else:
        logger.info("No new articles to download or save.")


def run_compliance():
    """Evaluates brand compliance checks for all raw articles in a pending state."""
    init_database()
    logger.info("Starting brand compliance checking for pending articles...")

    repository = ArticleRepository()
    pending_articles = repository.get_pending_compliance()
    
    if pending_articles:
        logger.info(f"Found {len(pending_articles)} articles awaiting compliance evaluation.")
        comp_filter = ComplianceFilter()
        comp_filter.evaluate_articles(pending_articles, repository)
    else:
        logger.info("No pending articles to verify.")


def run_classify_new_articles():
    """Classifies compliant articles that lack topic assignments using the pre-existing BERTopic model."""
    init_database()
    logger.info("Starting automatic classification of new articles using existing topic model...")
    
    article_repo = ArticleRepository()
    topic_repo = TopicRepository()
    
    # 1. Retrieve compliant articles that do not have any topic ID assigned yet
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
        logger.info("No new compliant articles to classify.")
        return
        
    logger.info(f"Found {len(pending_articles)} compliant articles without a topic assignment.")
    
    # 2. Load the map of currently active database topics
    active_topics_map = topic_repo.get_active_topics_map()
    active_labels_map = topic_repo.get_active_topic_labels_map()
    
    if not active_topics_map:
        logger.warning("No active topics found in the database. Run the 'analyze' stage first to discover topics.")
        return
        
    # 3. Predict topic IDs using the pre-trained BERTopic model
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
        
        # Map the predicted BERTopic cluster ID to the primary database topic ID
        db_topic_id = active_topics_map.get(pred_bt_id)
        # Default to 'Other / Unclassified' if no matching cluster is found (usually index -1)
        if db_topic_id is None:
            db_topic_id = active_topics_map.get(-1)
            
        label = active_labels_map.get(pred_bt_id, "Other / Unclassified") if db_topic_id is not None else "Other / Unclassified"
        
        updates.append({
            "id": a.id,
            "topic_id": db_topic_id,
            "topic_label": label
        })
        
    logger.info(f"Saving predicted topic assignments for {len(updates)} articles...")
    article_repo.update_article_topics(updates)


def run_analyze():
    """Runs BERTopic clustering, XGBoost trend scoring, and schedules daily generation allocations."""
    init_database()
    logger.info("Starting topic analysis, trend scoring, and post planning...")

    article_repo = ArticleRepository()
    trend_repo = TopicTrendRepository()
    plan_repo = GenerationPlanRepository()

    # [DIDACTIC_LIMITATION] Restrict training query to a sliding window of the last 14 days, falling back to a minimum of 100 articles
    # to guarantee sufficient dataset size for BERTopic clustering within sandboxed classroom setups.
    all_articles = article_repo.get_articles_for_training(days=14, min_count=100)
    logger.info(f"Retrieved {len(all_articles)} articles (14-day window or fallback) from database for analysis.")

    if not all_articles:
        logger.warning("No articles available in database. Aborting topic modeling.")
        return

    logger.info("Running BERTopic discovery and topic assignment...")
    modeler = FintechTopicModeler()
    try:
        topics, topic_labels, topic_keywords = modeler.train(all_articles, repository=article_repo)
        
        # Prepare discovered topics list for historical snapshot records
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
            
            # In-place model mutation for subsequent trend analysis scoring
            article.topic_id = db_id
            article.topic_label = label
            
            updates.append({
                "id": article.id,
                "topic_id": db_id,
                "topic_label": label
            })

        logger.info("Updating topic assignments for database articles...")
        article_repo.update_article_topics(updates)

        logger.info("Calculating topic trends using XGBoost panel regression...")
        scorer = TrendScorer()
        trends = scorer.calculate_trends(all_articles)
        
        logger.info("Saving fresh trend scores to the database...")
        trend_repo.save_topic_trends(trends)

        # Log identified trends
        logger.info("=== SUMMARY OF TOPIC TRENDS (Top 10) ===")
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

        logger.info("Generating daily post budget allocation plan...")
        planner = PostPlanner()
        # Map topic keywords using database primary IDs instead of BERTopic cluster IDs
        db_topic_keywords = {
            bertopic_to_db_map[bt_id]: kw
            for bt_id, kw in topic_keywords.items()
            if bt_id in bertopic_to_db_map
        }
        plan = planner.plan_posts(all_articles, trends, topic_keywords=db_topic_keywords)
        
        logger.info("Saving daily post generation plan to database...")
        plan_repo.save_generation_plan(plan)

        logger.info("=== DAILY POST ALLOCATION PLAN ===")
        for p in plan:
            if p["allocated_posts"] > 0:
                logger.info(
                    f"[{p['allocated_posts']:2d} posts] {p['topic_label']} | "
                    f"Trend Score: {p['trend_score']:.2f} | "
                    f"Compliance: {int(p['compliance_rate'] * 100)}%"
                )
        logger.info("====================================")

    except Exception as e:
        logger.exception(f"Critical error during analysis and topic modeling: {e}")



def run_generate():
    """Generates blog articles using RAG and Gemini based on the active plan in the database."""
    init_database()
    logger.info("Starting blog post generation stage via RAG...")

    # Ensure output directory exists
    posts_dir = Path("data/posts")
    posts_dir.mkdir(parents=True, exist_ok=True)

    # Clean up old posts to avoid overlapping/duplicate files
    for f in posts_dir.glob("*.md"):
        try:
            f.unlink()
        except OSError as e:
            logger.warning(f"Could not remove old file {f}: {e}")

    article_repo = ArticleRepository()
    plan_repo = GenerationPlanRepository()
    generator = BlogGenerator()

    # Query active plans
    plans = plan_repo.get_active_plans()

    if not plans:
        logger.warning("No active generation plans found. Run the 'analyze' command first.")
        return

    # Retrieve the shared SentenceTransformer singleton model for embedding RAG queries
    logger.info("Retrieving shared SentenceTransformer instance for encoding RAG queries...")
    encoder = get_embedding_model()

    total_generated = 0

    for plan in plans:
        topic_id = plan.topic_id
        topic_label = plan.topic_label
        budget = plan.allocated_posts
        keywords = plan.keywords if plan.keywords else ""
        search_trends = plan.search_trends if plan.search_trends else ""

        logger.info(f"Processing Topic {topic_id}: '{topic_label}' (Posts to generate: {budget})")

        # Retrieve compliant, unused articles for RAG context
        unused_articles = article_repo.get_unused_compliant_by_topic(topic_id)
        
        retrieved_all = []
        if unused_articles:
            # Build the FAISS vector index in-memory on the fly
            retriever = RAGRetriever()
            built = retriever.build_index(unused_articles)

            if built:
                keywords_list = [k.strip() for k in keywords.split(",") if k.strip()]
                seed_query = " ".join(keywords_list[:2]) if keywords_list else topic_label
                
                # Encode the query text
                query_vector = encoder.encode(seed_query, convert_to_numpy=True)
                
                # Retrieve 3 source articles for each planned post allocation
                k_total = 3 * budget
                retrieved_all = retriever.retrieve(query_vector, k=k_total)

        # Group retrieved articles into chunk lists of 3 sources each
        chunks = [retrieved_all[i : i + 3] for i in range(0, len(retrieved_all), 3)]

        post_repo = GeneratedPostRepository()
        seo_checker = SEOQualityChecker()

        # Load existing post embeddings to check for semantic duplication
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

            # Extract slug and title attributes from the YAML Front Matter
            slug_match = re.search(r"^slug:\s*(.+)$", post_content, re.MULTILINE)
            slug = slug_match.group(1).strip("'\" ") if slug_match else f"topic-{topic_id}-post-{post_idx}"
            url = f"/blog/{slug}"

            title_match = re.search(r"^title:\s*(.+)$", post_content, re.MULTILINE)
            title = title_match.group(1).strip("'\" ") if title_match else f"Post {topic_label}"

            # Initial SEO evaluation
            seo_res = seo_checker.check_seo(post_content, keywords)
            seo_score = seo_res["score"]

            # Auto-correction: if SEO score is below threshold, trigger a second correction pass
            if seo_score < 60.0:
                logger.warning(f"  [Post {post_idx}/{budget}] Insufficient SEO score ({seo_score}/100). Triggering auto-correction pass...")
                feedback = (
                    f"The generated content failed the SEO requirements ({seo_score}/100) due to:\n"
                    + "\n".join([f"- {w}" for w in seo_res["warnings"]])
                    + "\nPlease rewrite the article ensuring you extend the length (min 500 words), structure headings properly (H1, H2, H3), and use keywords naturally."
                )
                post_content = generator.generate_post(
                    topic_label=topic_label,
                    keywords=keywords,
                    search_trends=search_trends,
                    rag_articles=post_articles,
                    feedback=feedback
                )
                
                # Evaluate updated SEO score
                seo_res = seo_checker.check_seo(post_content, keywords)
                seo_score = seo_res["score"]
                
                # Re-extract correct title and slug
                slug_match = re.search(r"^slug:\s*(.+)$", post_content, re.MULTILINE)
                if slug_match:
                    slug = slug_match.group(1).strip("'\" ")
                    url = f"/blog/{slug}"
                title_match = re.search(r"^title:\s*(.+)$", post_content, re.MULTILINE)
                if title_match:
                    title = title_match.group(1).strip("'\" ")

            # Calculate post embedding
            new_emb = encoder.encode(post_content, convert_to_numpy=True)
            
            # Check for semantic similarity duplicates
            max_sim = seo_checker.check_similarity(new_emb, past_embeddings)
            if max_sim > 0.92:
                logger.warning(f"  [Post {post_idx}/{budget}] HIGH SEMANTIC SIMILARITY detected ({max_sim:.2%}) with prior posts. Possible duplicate!")

            # Search and append recommended internal link recommendations
            from app.services.published_index import PublishedPostsIndex
            pub_index = PublishedPostsIndex()
            related_ids = pub_index.search_similar_posts(new_emb, k=2)
            related_posts = post_repo.get_posts_by_ids(related_ids)
            if related_posts:
                references_md = "\n\n### Recommended Articles\n"
                for rp in related_posts:
                    references_md += f"* [{rp.title}]({rp.url})\n"
                post_content += references_md
                logger.info(f"  [Post {post_idx}/{budget}] Attached {len(related_posts)} related posts as footer recommendations.")

            # Save generated post to database
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

            # Append the new embedding to prevent similarity collisions inside the same execution batch
            past_embeddings.append(new_emb)

            # Save generated content to a local markdown file
            filename = f"topic_{topic_id}_post_{post_idx}.md"
            filepath = posts_dir / filename
            filepath.write_text(post_content, encoding="utf-8")

            is_rag = "RAG" if post_articles else "NO-RAG"
            review_status = " [NEEDS REVIEW]" if needs_review_flag else ""
            logger.info(
                f"  [Post {post_idx}/{budget}] Generated '{filename}' ({is_rag} mode, "
                f"SEO Score: {seo_score}/100, Max Similarity: {max_sim:.2%}){review_status}"
            )
            total_generated += 1

        # Mark source articles as used in the database
        if retrieved_all:
            used_ids = [art.id for art in retrieved_all]
            article_repo.mark_articles_as_used(used_ids)
            logger.info(f"  Marked {len(used_ids)} source articles as used in database.")

    logger.info(f"Generation workflow completed successfully! Created {total_generated} post files in: {posts_dir.resolve()}")


def run_all():
    """Runs all pipeline phases end-to-end sequentially."""
    logger.info("=== STARTING END-TO-END PIPELINE ===")
    
    # Import legacy archive posts from data/posts/old for the end-to-end demo
    try:
        from app.services.post_importer import import_old_posts
        import_old_posts()
    except Exception as e:
        logger.error(f"Error importing old posts: {e}")

    run_ingest()
    run_compliance()
    run_analyze()
    run_generate()
    logger.info("=== PIPELINE RUN COMPLETE ===")


def run_build_index():
    """Builds or updates the vector similarity index of published blog posts."""
    init_database()
    logger.info("Starting index build of published posts...")
    from app.services.published_index import PublishedPostsIndex
    indexer = PublishedPostsIndex()
    indexer.build_index_from_db()
