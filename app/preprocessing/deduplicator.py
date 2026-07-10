from app.models.article import Article


class Deduplicator:

    def process(self, articles: list[Article]) -> list[Article]:

        seen = set()

        unique = []

        for article in articles:

            if article.url in seen:
                continue

            seen.add(article.url)

            unique.append(article)

        return unique