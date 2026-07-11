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
    logger.info("Avvio ingestion RSS...")
    run_ingest()


@task(name="Compliance Check")
def compliance_task():
    logger.info("Avvio controlli di compliance...")
    run_compliance()


@task(name="Classificazione Nuovi Articoli")
def classify_task():
    logger.info("Avvio classificazione automatica su topic esistenti...")
    run_classify_new_articles()


@task(name="Trend Analysis & Planning")
def analyze_task():
    logger.info("Avvio topic modeling (BERTopic) e analisi dei trend (XGBoost)...")
    run_analyze()


@task(name="Post Generation (RAG)")
def generate_task():
    logger.info("Avvio generazione post giornalieri tramite RAG e LLM...")
    run_generate()


# 1. Pipeline Giornaliera: Raccolta Dati, Compliance e Classificazione
@flow(name="Daily Ingestion and Compliance Pipeline")
def daily_ingest_compliance_flow():
    ingest_task()
    compliance_task()
    classify_task()


# 2. Pipeline Settimanale: Addestramento Modello, Storicizzazione e Trend Analysis
@flow(name="Weekly Topic Analysis Pipeline")
def weekly_analysis_flow():
    analyze_task()


# 3. Pipeline Giornaliera: Generazione Post Blog
@flow(name="Daily Post Generation Pipeline")
def daily_generation_flow():
    generate_task()


# 4. Pipeline Demo: Esegue tutto in sequenza per scopi di debug/valutazione
@flow(name="Demo End-to-End Pipeline")
def demo_pipeline():
    logger.info("--- [DEMO E2E] Fase 1: Ingest, Compliance & Classificazione ---")
    ingest_task()
    compliance_task()
    
    logger.info("--- [DEMO E2E] Fase 2: Analisi Settimanale (Re-clustering & Trend Analysis) ---")
    analyze_task()
    
    logger.info("--- [DEMO E2E] Fase 3: Generazione Giornaliera Post ---")
    generate_task()


def serve_scheduled_flows():
    """Configura e serve le tre pipeline con pianificazione stile produzione."""
    logger.info("Configurazione dei deployment schedulati per le pipeline...")
    
    # 1. Ingestion e Compliance: ogni giorno alle 01:00
    dep_ingest = daily_ingest_compliance_flow.to_deployment(
        name="daily-ingest-compliance",
        schedule=CronSchedule(cron="0 1 * * *", timezone="Europe/Rome")
    )
    
    # 2. Analisi topic e trend: ogni lunedì alle 02:00
    dep_analysis = weekly_analysis_flow.to_deployment(
        name="weekly-topic-analysis",
        schedule=CronSchedule(cron="0 2 * * 1", timezone="Europe/Rome")
    )
    
    # 3. Generazione post: ogni giorno alle 06:00
    dep_generate = daily_generation_flow.to_deployment(
        name="daily-generation",
        schedule=CronSchedule(cron="0 6 * * *", timezone="Europe/Rome")
    )
    
    logger.info("Avvio del server di orchestrazione Prefect (Ascolto schedulazioni)...")
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
            "Uso: python flow.py [daily-ingest | weekly-analysis | daily-generate | demo | serve]\n"
            "Default: demo (esegue tutto in sequenza per test)"
        )
