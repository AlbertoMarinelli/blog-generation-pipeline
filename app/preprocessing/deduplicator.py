from app.entities.article import Article


class Deduplicator:
    """Pre-processing module that filters out duplicate articles from the collection batch."""

    def process(self, articles: list[Article]) -> list[Article]:
        """Deduplicates a list of articles based on their URL.

        Args:
            articles (list[Article]): The list of raw articles to filter.

        Returns:
            list[Article]: A list of unique articles.
        """
        seen = set()
        unique = []
        for article in articles:
            if article.url in seen:
                continue
            seen.add(article.url)
            unique.append(article)
        return unique