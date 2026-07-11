import math
from config import DAILY_POST_BUDGET
from app.database.models import ArticleModel


class PostPlanner:

    def _fetch_google_trends(self, query: str) -> list[str]:
        try:
            from pytrends.request import TrendReq
            # Create request with timeout and generic headers
            pytrends = TrendReq(hl='en-US', tz=360, timeout=10)
            pytrends.build_payload(kw_list=[query], timeframe='today 1-m')
            rq = pytrends.related_queries()
            if query in rq and rq[query]['top'] is not None:
                top_df = rq[query]['top']
                # Extract top 5 related queries
                return top_df['query'].tolist()[:5]
        except Exception as e:
            print(f"Warning: Google Trends query failed for '{query}': {e}.")
        return []

    def plan_posts(self, articles: list[ArticleModel], trends: list[dict], topic_keywords: dict = None) -> list[dict]:
        if not trends or DAILY_POST_BUDGET <= 0:
            print("No trends available or daily post budget is set to 0. Post planning skipped.")
            return []

        # 1. Group articles by topic to count total and compliant articles
        topic_articles = {}
        for a in articles:
            if a.topic_id is None or a.topic_id == -1:
                continue
            if a.topic_id not in topic_articles:
                topic_articles[a.topic_id] = []
            topic_articles[a.topic_id].append(a)

        # 2. Compute compliance rate and effective score for each topic
        calculated_trends = []
        for t in trends:
            tid = t["topic_id"]
            articles_in_topic = topic_articles.get(tid, [])
            total_vol = len(articles_in_topic)
            compliant_vol = sum(1 for a in articles_in_topic if a.is_compliant == True)
            compliance_rate = compliant_vol / total_vol if total_vol > 0 else 0.0
            
            # Effective Score = trend_score * compliance_rate
            effective_score = t["trend_score"] * compliance_rate

            calculated_trends.append({
                "topic_id": tid,
                "topic_label": t["topic_label"],
                "trend_score": t["trend_score"],
                "compliance_rate": compliance_rate,
                "effective_score": effective_score,
                "allocated_posts": 0
            })

        # 3. Proportional Budget Allocation using Largest Remainder Method
        active_trends = [ct for ct in calculated_trends if ct["effective_score"] > 0]
        total_effective_score = sum(ct["effective_score"] for ct in active_trends)

        if total_effective_score > 0:
            budget = DAILY_POST_BUDGET
            
            # First pass: Allocate math.floor of the fractional share
            for ct in active_trends:
                fractional_share = (ct["effective_score"] / total_effective_score) * budget
                ct["allocated_posts"] = math.floor(fractional_share)
                ct["remainder"] = fractional_share - ct["allocated_posts"]

            allocated_sum = sum(ct["allocated_posts"] for ct in active_trends)
            remaining_posts = budget - allocated_sum

            # Distribute remaining posts to topics with the largest remainders
            # Sort by remainder descending
            active_trends.sort(key=lambda x: x["remainder"], reverse=True)
            for i in range(int(remaining_posts)):
                idx = i % len(active_trends)
                active_trends[idx]["allocated_posts"] += 1

            # Map the allocated counts back to the primary trends list
            allocated_map = {ct["topic_id"]: ct["allocated_posts"] for ct in active_trends}
            for ct in calculated_trends:
                ct["allocated_posts"] = allocated_map.get(ct["topic_id"], 0)
        else:
            print("Warning: All active topics have 0% compliance. No posts can be allocated.")

        # 4. Fetch Google Trends search queries only for active topics
        for ct in calculated_trends:
            tid = ct["topic_id"]
            ct["keywords"] = topic_keywords.get(tid, "") if topic_keywords else ""
            ct["search_trends"] = ""

            if ct["allocated_posts"] > 0:
                # Take top 1 or 2 keywords from local keywords as seed query
                keywords_list = [k.strip() for k in ct["keywords"].split(",") if k.strip()]
                # Using first two words (e.g. "open banking")
                seed_query = " ".join(keywords_list[:2]) if keywords_list else ct["topic_label"]

                print(f"Fetching Google Trends for topic {tid} ('{seed_query}')...")
                trends_list = self._fetch_google_trends(seed_query)

                if trends_list:
                    ct["search_trends"] = ", ".join(trends_list)
                    print(f"-> Google Trends found: {ct['search_trends']}")
                else:
                    print("-> Google Trends unavailable. Falling back directly to local c-TF-IDF keywords.")
                    # Fallback to local keywords
                    ct["search_trends"] = ct["keywords"]

        return calculated_trends
