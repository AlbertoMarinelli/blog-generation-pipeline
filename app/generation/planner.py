import math
from config import DAILY_POST_BUDGET
from app.database.models import ArticleModel


class PostPlanner:

    def plan_posts(self, articles: list[ArticleModel], trends: list[dict]) -> list[dict]:
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

        return calculated_trends
