import os
import re
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from sqlalchemy import select

from app.database.db import SessionLocal
from app.database.models import TopicModel, GeneratedPostModel
from app.services.embedding import get_embedding_model
from app.services.published_index import PublishedPostsIndex

logger = logging.getLogger(__name__)


def parse_markdown_post(filepath: Path) -> tuple[str, str, str]:
    """Parses YAML front matter and body from a markdown file.
    
    Returns:
        tuple[str, str, str]: (title, slug, body)
    """
    content = filepath.read_text(encoding="utf-8")
    front_matter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    title = ""
    slug = ""
    body = ""
    if front_matter_match:
        yaml_content = front_matter_match.group(1)
        body = front_matter_match.group(2)
        title_match = re.search(r"^title:\s*(.+)$", yaml_content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip("'\" ")
        slug_match = re.search(r"^slug:\s*(.+)$", yaml_content, re.MULTILINE)
        if slug_match:
            slug = slug_match.group(1).strip("'\" ")
    else:
        body = content
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            
    if not title:
        title = filepath.stem
    if not slug:
        title_slug = title.lower()
        title_slug = re.sub(r'[^\w\s-]', '', title_slug)
        title_slug = re.sub(r'[\s_-]+', '-', title_slug)
        slug = title_slug.strip('-')
        
    return title, slug, body


def import_old_posts():
    """Imports fake/old posts from 'data/posts/old' as published articles in the database,
    calculates their embeddings if they are not already indexed, and ensures they are never deleted.
    Also rebuilds the FAISS recommendation index if new posts are imported.
    """
    logger.info("Checking for old posts to import from 'data/posts/old'...")
    old_posts_dir = Path("data/posts/old")
    if not old_posts_dir.exists():
        logger.info("No 'data/posts/old' directory found. Skipping import.")
        return
        
    md_files = list(old_posts_dir.glob("*.md"))
    if not md_files:
        logger.info("No markdown files found in 'data/posts/old'. Skipping import.")
        return
        
    # Lazy database initialization
    from app.database.db import init_db
    init_db()
    
    with SessionLocal() as session:
        # 1. Ensure the special topic for legacy/imported posts exists
        legacy_topic = session.scalars(
            select(TopicModel).where(TopicModel.topic_id == -100)
        ).first()
        
        if not legacy_topic:
            legacy_topic = TopicModel(
                topic_id=-100,
                label="Imported / Archive Posts",
                keywords="old, archive, historic, legacy",
                is_active=False
            )
            session.add(legacy_topic)
            session.commit()
            logger.info("Created legacy topic in database for imported archive posts.")
            
        legacy_topic_id = legacy_topic.id
        
        # 2. Iterate through old post files and import if not already in the database
        encoder = None
        imported_count = 0
        
        for filepath in md_files:
            try:
                title, slug, content = parse_markdown_post(filepath)
                url = f"/blog/{slug}"
                
                # Check if the post is already indexed in the database (by URL or title)
                exists = session.scalars(
                    select(GeneratedPostModel).where(
                        (GeneratedPostModel.url == url) | (GeneratedPostModel.title == title)
                    )
                ).first()
                
                if exists:
                    logger.debug(f"Old post '{title}' already indexed in database.")
                    continue
                    
                logger.info(f"Indexing new old post: '{title}'...")
                
                if encoder is None:
                    encoder = get_embedding_model()
                
                # Compute embedding
                full_content = filepath.read_text(encoding="utf-8")
                embedding = encoder.encode(full_content, convert_to_numpy=True)
                
                db_post = GeneratedPostModel(
                    topic_id=legacy_topic_id,
                    title=title,
                    content=full_content,
                    url=url,
                    embedding=embedding.astype(np.float32).tobytes(),
                    seo_score=100.0,
                    max_similarity=0.0,
                    needs_review=False,
                    is_published=True,
                    published_at=datetime.utcnow()
                )
                session.add(db_post)
                imported_count += 1
            except Exception as e:
                logger.error(f"Error importing old post {filepath}: {e}")
                
        if imported_count > 0:
            session.commit()
            logger.info(f"Successfully imported {imported_count} new old posts into the database.")
            # Rebuild the FAISS index so they are immediately available
            indexer = PublishedPostsIndex()
            indexer.build_index_from_db()
        else:
            logger.info("All old posts in 'data/posts/old' are already indexed in the database.")
            
            # Ensure the FAISS index file exists
            if not os.path.exists("data/published_posts.index"):
                logger.info("FAISS index file not found. Rebuilding from database...")
                indexer = PublishedPostsIndex()
                indexer.build_index_from_db()
