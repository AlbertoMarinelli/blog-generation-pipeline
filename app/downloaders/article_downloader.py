import trafilatura

from app.models.article import Article


class ArticleDownloader:

    def process(self, articles: list[Article]) -> list[Article]:

        enriched_articles = []

        for article in articles:

            downloaded = trafilatura.fetch_url(article.url)

            if downloaded is None:
                continue

            content = trafilatura.extract(downloaded)

            if content is None:
                continue

            article.content = content

            enriched_articles.append(article)

        return enriched_articles