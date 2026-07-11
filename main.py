import argparse
import logging
import sys

from app.pipeline import (
    run_ingest,
    run_compliance,
    run_classify_new_articles,
    run_analyze,
    run_generate,
    run_all
)

# Configura il logging di base per la console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("cli")


def main():
    parser = argparse.ArgumentParser(
        description="Fintech Blog Generation Pipeline CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Argomenti globali
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Abilita log dettagliati di livello DEBUG"
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        help="Comando specifico della pipeline da avviare"
    )

    subparsers.add_parser("ingest", help="Esegue la raccolta RSS, scaricamento e pulizia articoli.")
    subparsers.add_parser("compliance", help="Verifica la conformità del brand per gli articoli pendenti.")
    subparsers.add_parser("classify", help="Classifica gli articoli conformi non assegnati usando il modello esistente.")
    subparsers.add_parser("analyze", help="Esegue topic modeling BERTopic, scoring trend XGBoost e piano post.")
    subparsers.add_parser("generate", help="Genera gli articoli di blog finali (RAG + Gemini) basati sul piano.")
    subparsers.add_parser("run-all", help="Avvia l'intera pipeline in sequenza (comportamento predefinito).")

    args = parser.parse_args()

    # Imposta il livello di log in base all'argomento verbose
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Livello di logging impostato su DEBUG.")

    # Esecuzione del comando selezionato
    if args.command == "ingest":
        run_ingest()
    elif args.command == "compliance":
        run_compliance()
    elif args.command == "classify":
        run_classify_new_articles()
    elif args.command == "analyze":
        run_analyze()
    elif args.command == "generate":
        run_generate()
    elif args.command == "run-all" or not args.command:
        # Se non viene specificato alcun comando, esegui tutto (retrocompatibilità)
        if not args.command:
            logger.info("Nessun comando specificato. Avvio della pipeline completa per default...")
        run_all()


if __name__ == "__main__":
    main()