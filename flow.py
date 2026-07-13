import logging
import sys
from datetime import timedelta
from prefect import flow, task
from prefect.client.schemas.schedules import CronSchedule

from app.pipeline import (
    run_ingest,
    run_compliance,
    run_classify_new_articles,
    run_analyze,
    run_generate
)

logger = logging.getLogger("blog_pipeline")


@task(name="Ingestion RSS")
def ingest_task():
    logger.info("Starting RSS ingestion...")
    run_ingest()


@task(name="Compliance Check")
def compliance_task():
    logger.info("Starting compliance checks...")
    run_compliance()


@task(name="Classificazione Nuovi Articoli")
def classify_task():
    logger.info("Starting automatic classification on existing topics...")
    run_classify_new_articles()


@task(name="Trend Analysis & Planning")
def analyze_task():
    logger.info("Starting topic modeling (BERTopic) and trend analysis (XGBoost)...")
    run_analyze()


@task(name="Post Generation (RAG)")
def generate_task():
    logger.info("Starting daily post generation using RAG and LLM...")
    run_generate()


# 1. Daily Pipeline: Ingestion, Compliance, and Classification
@flow(name="Daily Ingestion and Compliance Pipeline")
def daily_ingest_compliance_flow():
    ingest_task()
    compliance_task()
    classify_task()


# 2. Weekly Pipeline: Model Training, Historical Records, and Trend Analysis
@flow(name="Weekly Topic Analysis Pipeline")
def weekly_analysis_flow():
    analyze_task()


# 3. Daily Pipeline: Blog Post Generation
@flow(name="Daily Post Generation Pipeline")
def daily_generation_flow():
    generate_task()


# 4. Setup Task for Demo environment
@task(name="Import Old Posts")
def import_old_posts_task():
    logger.info("Importing legacy/old posts for the demo environment...")
    from app.services.post_importer import import_old_posts
    try:
        import_old_posts()
    except Exception as e:
        logger.error(f"Error importing old posts: {e}")


# 5. Demo Pipeline: Run all phases in sequence for debugging/evaluation
@flow(name="Demo End-to-End Pipeline")
def demo_pipeline():
    logger.info("--- [DEMO E2E] Phase 0: Setup and legacy data import ---")
    import_old_posts_task()

    logger.info("--- [DEMO E2E] Phase 1: Ingest, Compliance & Classification ---")
    ingest_task()
    compliance_task()
    
    logger.info("--- [DEMO E2E] Phase 2: Weekly Analysis (Re-clustering & Trend Analysis) ---")
    analyze_task()
    
    logger.info("--- [DEMO E2E] Phase 3: Daily Post Generation ---")
    generate_task()


def serve_scheduled_flows():
    """Configures and runs the three pipelines using a production-grade scheduler."""
    logger.info("Configuring scheduled deployments for pipelines...")
    
    # 1. Ingestion and Compliance: daily at 01:00 Europe/Rome
    dep_ingest = daily_ingest_compliance_flow.to_deployment(
        name="daily-ingest-compliance",
        schedule=CronSchedule(cron="0 1 * * *", timezone="Europe/Rome")
    )
    
    # 2. Topic and Trend analysis: weekly on Monday at 02:00 Europe/Rome
    dep_analysis = weekly_analysis_flow.to_deployment(
        name="weekly-topic-analysis",
        schedule=CronSchedule(cron="0 2 * * 1", timezone="Europe/Rome")
    )
    
    # 3. Blog post generation: daily at 06:00 Europe/Rome
    dep_generate = daily_generation_flow.to_deployment(
        name="daily-generation",
        schedule=CronSchedule(cron="0 6 * * *", timezone="Europe/Rome")
    )
    
    logger.info("Starting Prefect orchestration server (listening to schedules)...")
    from prefect import serve
    serve(dep_ingest, dep_analysis, dep_generate)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "demo"
    
    if command == "daily-ingest":
        daily_ingest_compliance_flow()
    elif command == "weekly-analysis":
        weekly_analysis_flow()
    elif command == "daily-generate":
        daily_generation_flow()
    elif command == "demo":
        demo_pipeline()
    elif command == "serve":
        serve_scheduled_flows()
    else:
        print(
            "Usage: python flow.py [daily-ingest | weekly-analysis | daily-generate | demo | serve]\n"
            "Default: demo (runs everything in sequence for test/demo purposes)"
        )
