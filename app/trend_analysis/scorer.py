import numpy as np
import pandas as pd
import xgboost as xgb
from datetime import datetime
from app.database.models import ArticleModel


class TrendScorer:
    """Computes trend scores for identified topics using an XGBoost panel regression model or rules-based fallbacks."""

    def calculate_trends(self, articles: list[ArticleModel]) -> list[dict]:
        """Calculates trend scores for active topics based on article volumes, freshness, and diversity.

        Args:
            articles (list[ArticleModel]): The list of topic-assigned articles to analyze.

        Returns:
            list[dict]: A sorted list of trend dictionaries, ordered by trend score descending.
        """
        # Filter out articles with no topic or unclassified (-1)
        valid_articles = [
            a for a in articles 
            if a.topic_id is not None and "Other / Unclassified" not in (a.topic_label or "")
        ]

        if not valid_articles:
            print("No valid topic-assigned articles available for trend scoring.")
            return []

        # 1. Parse publication dates and build basic DataFrame
        records = []
        for a in valid_articles:
            try:
                # The format standardized by TextCleaner is %Y-%m-%d %H:%M:%S
                dt = datetime.strptime(a.published, "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = datetime.utcnow()
            records.append({
                "id": a.id,
                "topic_id": a.topic_id,
                "topic_label": a.topic_label,
                "source": a.source or "Unknown",
                "published_dt": dt
            })

        df = pd.DataFrame(records)
        max_date = df["published_dt"].max()

        # 2. Calculate Freshness for each article
        # Exponential decay: fresher articles get score close to 1.0, older articles decay towards 0.0
        df["days_diff"] = (max_date - df["published_dt"]).dt.total_seconds() / (24 * 3600)
        df["freshness"] = np.exp(-0.1 * df["days_diff"])

        # 3. Calculate daily time-series counts per topic to build a panel dataset
        df["day"] = df["published_dt"].dt.date
        daily_counts = df.groupby(["topic_id", "day"]).size().reset_index(name="daily_volume")

        unique_days = sorted(df["day"].unique())
        num_days = len(unique_days)
        topics_list = df["topic_id"].unique()

        predictions_dict = {}

        # We need at least 3 distinct days to build lag_1, lag_2 and target (t+1)
        if num_days >= 3:
            # Create a complete grid of (topic, day) to ensure zero-volume days are accounted for
            grid = []
            for t in topics_list:
                for d in unique_days:
                    grid.append((t, d))
            grid_df = pd.DataFrame(grid, columns=["topic_id", "day"])
            
            panel_df = pd.merge(grid_df, daily_counts, on=["topic_id", "day"], how="left").fillna(0)
            panel_df = panel_df.sort_values(by=["topic_id", "day"])

            # Compute Lags
            panel_df["lag_1"] = panel_df.groupby("topic_id")["daily_volume"].shift(1)
            panel_df["lag_2"] = panel_df.groupby("topic_id")["daily_volume"].shift(2)
            panel_df["target"] = panel_df.groupby("topic_id")["daily_volume"].shift(-1)

            # Drop NaNs to create training set
            train_df = panel_df.dropna()

            # We train XGBoost only if we have a minimum number of samples to avoid trivial models
            if len(train_df) >= 10:
                print(f"Training XGBoost Regressor on {len(train_df)} panel data points...")
                X = train_df[["daily_volume", "lag_1", "lag_2"]]
                y = train_df["target"]

                # Hyperparameters optimized for small datasets to prevent overfitting
                model = xgb.XGBRegressor(
                    n_estimators=20,
                    max_depth=2,
                    learning_rate=0.08,
                    random_state=42
                )
                model.fit(X, y)

                # Prepare prediction features (using current day, lag 1, and lag 2)
                predict_rows = []
                for t in topics_list:
                    topic_data = panel_df[panel_df["topic_id"] == t].sort_values("day")
                    last_row = topic_data.iloc[-1]
                    second_last = topic_data.iloc[-2] if len(topic_data) > 1 else last_row
                    third_last = topic_data.iloc[-3] if len(topic_data) > 2 else second_last

                    predict_rows.append({
                        "topic_id": t,
                        "daily_volume": last_row["daily_volume"],
                        "lag_1": second_last["daily_volume"],
                        "lag_2": third_last["daily_volume"]
                    })
                
                predict_df = pd.DataFrame(predict_rows)
                preds = model.predict(predict_df[["daily_volume", "lag_1", "lag_2"]])
                preds = np.clip(preds, 0, None)  # Ensure volume is non-negative
                predictions_dict = dict(zip(predict_df["topic_id"], preds))
            else:
                print(f"Only {len(train_df)} training samples available. Using rule-based daily trend extrapolation.")
                # Fallback rule-based forecasting: current volume + acceleration
                for t in topics_list:
                    topic_data = panel_df[panel_df["topic_id"] == t].sort_values("day")
                    v_today = topic_data.iloc[-1]["daily_volume"]
                    v_yesterday = topic_data.iloc[-2]["daily_volume"] if len(topic_data) > 1 else v_today
                    predictions_dict[t] = max(0.0, float(v_today + (v_today - v_yesterday)))
        else:
            print(f"Insufficient timeline depth ({num_days} days). Using average daily volume as forecasted volume.")
            # Fallback for very small databases (average volume per day)
            for t in topics_list:
                total_vol = len(df[df["topic_id"] == t])
                predictions_dict[t] = total_vol / max(1.0, float(num_days))

        # 4. Calculate aggregate stats and combine with predictions into Trend Scores
        topic_stats = df.groupby(["topic_id", "topic_label"]).agg(
            total_volume=("id", "count"),
            mean_freshness=("freshness", "mean"),
            unique_sources=("source", "nunique")
        ).reset_index()

        trends = []
        for _, row in topic_stats.iterrows():
            tid = int(row["topic_id"])
            tlabel = str(row["topic_label"])
            vol = int(row["total_volume"])
            freshness = float(row["mean_freshness"])
            diversity = float(row["unique_sources"] / vol) if vol > 0 else 0.0
            
            # Forecasted volume from XGBoost or Fallback
            pred_vol = float(predictions_dict.get(tid, vol / max(1.0, float(num_days))))

            # Composite scoring formula:
            # Score = ForecastedVolume * (1 + Freshness) * (1 + SourceDiversity)
            score = pred_vol * (1.0 + freshness) * (1.0 + diversity)

            trends.append({
                "topic_id": tid,
                "topic_label": tlabel,
                "volume": vol,
                "freshness_score": freshness,
                "source_diversity": diversity,
                "trend_score": round(score, 4)
            })

        # Sort topics by trend score in descending order
        trends.sort(key=lambda x: x["trend_score"], reverse=True)
        return trends
