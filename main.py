import argparse
import logging
import sys

from app.pipeline import (
    run_ingest,
    run_compliance,
    run_classify_new_articles,
    run_analyze,
    run_generate,
    run_all,
    run_build_index
)

# Configure basic logging for the console output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("cli")


def main():
    """Main CLI entry point for the Fintech Blog Generation Pipeline."""
    parser = argparse.ArgumentParser(
        description="Fintech Blog Generation Pipeline CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Global arguments
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )

    # Subcommands configuration
    subparsers = parser.add_subparsers(
        dest="command",
        help="Specific pipeline command to run"
    )

    subparsers.add_parser("ingest", help="Collect RSS feeds, download, and clean articles.")
    subparsers.add_parser("compliance", help="Check brand compliance for pending articles.")
    subparsers.add_parser("classify", help="Classify compliant articles using the existing BERTopic model.")
    subparsers.add_parser("analyze", help="Run BERTopic discovery, XGBoost trend scoring, and planning.")
    subparsers.add_parser("generate", help="Generate final blog posts using RAG and Gemini.")
    subparsers.add_parser("build-index", help="Build/rebuild the vector index of published posts using FAISS.")
    subparsers.add_parser("run-all", help="Run the entire pipeline sequentially (default behavior).")

    args = parser.parse_args()

    # Adjust log level based on verbosity flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Logging level set to DEBUG.")

    # Execute target pipeline phase
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
    elif args.command == "build-index":
        run_build_index()
    elif args.command == "run-all" or not args.command:
        # Fallback to running all phases if no command is specified for backward compatibility
        if not args.command:
            logger.info("No command specified. Running full pipeline end-to-end...")
        run_all()


if __name__ == "__main__":
    main()