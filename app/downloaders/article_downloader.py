import trafilatura
from googlenewsdecoder import new_decoderv1

from app.models.article import Article


class ArticleDownloader:

    def process(self, articles: list[Article]) -> list[Article]:

        enriched_articles = []

        for article in articles:

            url_to_fetch = article.url
            if "news.google.com" in url_to_fetch:
                try:
                    decoded = new_decoderv1(url_to_fetch)
                    if decoded.get("status"):
                        url_to_fetch = decoded["decoded_url"]
                        article.url = url_to_fetch  # Update to direct URL
                except Exception as e:
                    print(f"Failed to decode Google News link {url_to_fetch}: {e}")

            downloaded = trafilatura.fetch_url(url_to_fetch)

            if downloaded is None:
                continue

            content = trafilatura.extract(downloaded)

            if content is None:
                continue

            article.content = content

            enriched_articles.append(article)

        return enriched_articles