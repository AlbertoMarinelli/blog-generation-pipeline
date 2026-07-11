import os
import sqlite3
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer

from config import DATABASE_PATH, DAILY_POST_BUDGET
from app.database.db import SessionLocal, init_db
from app.database.models import GenerationPlanModel
from app.database.repository import ArticleRepository
from app.generation.rag import RAGRetriever
from app.generation.generator import BlogGenerator


def main():
    print("=" * 60)
    print("FINTECH BLOG POST GENERATION SYSTEM")
    print("=" * 60)

    # Initialize Database Schema & Migrations
    init_db()

    # 1. Ensure target directory for posts exists
    posts_dir = Path("data/posts")
    posts_dir.mkdir(parents=True, exist_ok=True)

    # Clean old generated posts to verify clean test run
    for f in posts_dir.glob("*.md"):
        try:
            f.unlink()
        except OSError:
            pass

    repository = ArticleRepository()
    generator = BlogGenerator()

    # 2. Query SQLite for active plans
    with SessionLocal() as session:
        plans = session.query(GenerationPlanModel).filter(
            GenerationPlanModel.allocated_posts > 0
        ).order_by(GenerationPlanModel.allocated_posts.desc()).all()

    if not plans:
        print("No active post allocation plan found in SQLite. Run main.py first.")
        return

    # 3. Load the SentenceTransformer model for query vector encoding
    print("Loading SentenceTransformer ('all-MiniLM-L6-v2') for RAG queries...")
    encoder = SentenceTransformer("all-MiniLM-L6-v2")
    print("Model loaded successfully.")

    total_generated = 0

    # 4. Generate articles per topic
    for plan in plans:
        topic_id = plan.topic_id
        topic_label = plan.topic_label
        budget = plan.allocated_posts
        keywords = plan.keywords if plan.keywords else ""
        search_trends = plan.search_trends if plan.search_trends else ""

        print(f"\n>>> Processing Topic {topic_id}: '{topic_label}'")
        print(f"    Posts to generate: {budget}")

        # Retrieve compliant and UNUSED articles for this specific topic
        unused_articles = repository.get_unused_compliant_by_topic(topic_id)
        
        retrieved_all = []
        if unused_articles:
            # Build topic-specific FAISS index ONCE
            retriever = RAGRetriever()
            built = retriever.build_index(unused_articles)

            if built:
                # Build query text from top keywords
                keywords_list = [k.strip() for k in keywords.split(",") if k.strip()]
                seed_query = " ".join(keywords_list[:2]) if keywords_list else topic_label
                
                # Compute query embedding
                query_vector = encoder.encode(seed_query, convert_to_numpy=True)
                
                # Retrieve all required RAG sources (3 per post budget) in a single FAISS query
                k_total = 3 * budget
                retrieved_all = retriever.retrieve(query_vector, k=k_total)

        # Split retrieved articles into chunks of size 3
        chunks = [retrieved_all[i : i + 3] for i in range(0, len(retrieved_all), 3)]

        # Generate each post
        for post_idx in range(1, budget + 1):
            # Take chunk if available, else empty list (falls back to No-RAG prompt)
            post_articles = chunks[post_idx - 1] if post_idx - 1 < len(chunks) else []

            post_content = generator.generate_post(
                topic_label=topic_label,
                keywords=keywords,
                search_trends=search_trends,
                rag_articles=post_articles
            )

            # Save the file
            filename = f"topic_{topic_id}_post_{post_idx}.md"
            filepath = posts_dir / filename
            filepath.write_text(post_content, encoding="utf-8")

            is_rag = "RAG" if post_articles else "NO-RAG"
            print(f"    [Post {post_idx}/{budget}] Generated '{filename}' ({is_rag} mode, sources: {len(post_articles)})")
            total_generated += 1

        # Bulk update used articles in SQLite in a single transaction
        if retrieved_all:
            used_ids = [art.id for art in retrieved_all]
            repository.mark_articles_as_used(used_ids)
            print(f"    [Database] Marked {len(used_ids)} articles as used.")

    print("\n" + "=" * 60)
    print(f"GENERATION COMPLETE: {total_generated} posts generated successfully!")
    print(f"Articles saved to: {posts_dir.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
