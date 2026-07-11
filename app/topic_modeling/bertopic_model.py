import os
import pickle
import numpy as np
from pathlib import Path
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer

from app.database.models import ArticleModel


class FintechTopicModeler:

    def __init__(self, model_dir: str = "data/models/bertopic_model", viz_dir: str = "data/visualizations"):
        self.model_dir = Path(model_dir)
        self.viz_dir = Path(viz_dir)
        self.model = None

    def train(self, articles: list[ArticleModel], repository=None) -> tuple[list[int], dict[int, str]]:
        if not articles:
            raise ValueError("No articles provided for training.")

        # Combine title, summary, and content for a richer contextual embedding
        docs = []
        for a in articles:
            title = a.title or ""
            summary = a.summary or ""
            content = a.content or ""
            
            # Combine them prioritizing title and summary/content
            text = f"{title}\n{summary}\n{content}".strip()
            # If still empty, use a placeholder
            if not text:
                text = "Empty article"
            docs.append(text)

        num_docs = len(docs)
        print(f"Training BERTopic on {num_docs} articles...")

        # Collect existing embeddings and identify articles that need embedding
        articles_to_embed = []
        embeddings_list = []
        
        for i, a in enumerate(articles):
            text = docs[i]
            if a.embedding is not None:
                # Convert bytes back to numpy array
                emb = np.frombuffer(a.embedding, dtype=np.float32)
                embeddings_list.append((a.id, emb))
            else:
                articles_to_embed.append((a.id, text))

        # Dynamically calculate embeddings for missing articles only
        if articles_to_embed:
            print(f"Computing embeddings for {len(articles_to_embed)} new/uncached articles...")
            encoder = SentenceTransformer("all-MiniLM-L6-v2")
            new_texts = [text for _, text in articles_to_embed]
            new_embs = encoder.encode(new_texts, show_progress_bar=True, convert_to_numpy=True)
            
            if repository is not None:
                db_updates = []
                for (article_id, _), emb in zip(articles_to_embed, new_embs):
                    emb_bytes = emb.astype(np.float32).tobytes()
                    db_updates.append({"id": article_id, "embedding": emb_bytes})
                repository.update_article_embeddings(db_updates)
                print(f"Saved {len(db_updates)} new embeddings to SQLite database.")
            
            for (article_id, _), emb in zip(articles_to_embed, new_embs):
                embeddings_list.append((article_id, emb))
        else:
            print("All articles have cached embeddings. Skipping SentenceTransformer encoding.")

        # Reconstruct the full embeddings matrix aligned with docs
        emb_dict = dict(embeddings_list)
        all_embeddings = np.array([emb_dict[a.id] for a in articles], dtype=np.float32)

        # Dynamically set clustering parameters based on dataset size
        # to prevent HDBSCAN crash/excessive noise on smaller datasets.
        min_cluster_size = min(10, max(2, num_docs // 15))
        min_samples = max(1, min_cluster_size // 2)

        # Initialize sub-components (using string identifier for embedding_model to avoid unnecessary loading)
        umap_model = UMAP(
            n_neighbors=min(15, num_docs - 1),
            n_components=min(5, num_docs - 2),
            min_dist=0.0,
            metric="cosine",
            random_state=42
        )
        
        hdbscan_model = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True
        )
        
        vectorizer_model = CountVectorizer(
            stop_words="english",
            ngram_range=(1, 2)
        )

        self.model = BERTopic(
            embedding_model="all-MiniLM-L6-v2",
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer_model,
            calculate_probabilities=False
        )

        topics, _ = self.model.fit_transform(docs, embeddings=all_embeddings)

        # Extract topic labels (e.g., "0_open_banking_api") and top 10 keywords
        topic_labels = {}
        topic_keywords = {}
        for topic_id, words_weights in self.model.topic_representations_.items():
            if topic_id == -1:
                topic_labels[topic_id] = "Other / Unclassified"
                topic_keywords[topic_id] = ""
            else:
                # Take top 3 keywords for the label representation
                top_words_label = [word for word, _ in words_weights[:3]]
                topic_labels[topic_id] = f"Topic {topic_id}: " + ", ".join(top_words_label)

                # Take top 10 keywords for prompt context
                top_words_all = [word for word, _ in words_weights[:10]]
                topic_keywords[topic_id] = ", ".join(top_words_all)

        # Ensure directories exist
        self.model_dir.parent.mkdir(parents=True, exist_ok=True)
        self.viz_dir.mkdir(parents=True, exist_ok=True)

        # Save visualizations
        self.save_visualizations(num_docs)

        # Save model
        self.save_model()

        return topics, topic_labels, topic_keywords

    def save_visualizations(self, num_docs: int):
        if not self.model:
            return

        # Interactive plots can fail if we don't have enough topics
        num_topics = len(set(self.model.topics_)) - (1 if -1 in self.model.topics_ else 0)

        # 1. Topic Similarity Map (needs at least 2 topics)
        if num_topics >= 2:
            try:
                fig_topics = self.model.visualize_topics()
                fig_topics.write_html(str(self.viz_dir / "topic_similarity.html"))
                print(f"Saved topic similarity visualization to {self.viz_dir / 'topic_similarity.html'}")
            except Exception as e:
                print(f"Skipping topic similarity plot: {e}")

        # 2. Topic Keyword Barchart (needs at least 1 topic)
        if num_topics >= 1:
            try:
                fig_barchart = self.model.visualize_barchart(top_n_topics=min(10, num_topics))
                fig_barchart.write_html(str(self.viz_dir / "topic_barchart.html"))
                print(f"Saved topic barchart visualization to {self.viz_dir / 'topic_barchart.html'}")
            except Exception as e:
                print(f"Skipping topic barchart plot: {e}")

            # 3. Topic Hierarchy (needs at least 3 topics)
            if num_topics >= 3:
                try:
                    fig_hierarchy = self.model.visualize_hierarchy()
                    fig_hierarchy.write_html(str(self.viz_dir / "topic_hierarchy.html"))
                    print(f"Saved topic hierarchy visualization to {self.viz_dir / 'topic_hierarchy.html'}")
                except Exception as e:
                    print(f"Skipping topic hierarchy plot: {e}")

    def save_model(self):
        if not self.model:
            return
        
        try:
            # We save the model using pickle to make it simple and single-file compatible
            with open(self.model_dir, "wb") as f:
                pickle.dump(self.model, f)
            print(f"Saved topic model to {self.model_dir}")
        except Exception as e:
            print(f"Failed to save topic model: {e}")

    def load_model(self):
        if self.model_dir.exists():
            with open(self.model_dir, "rb") as f:
                self.model = pickle.load(f)
            print(f"Loaded topic model from {self.model_dir}")
        else:
            print("No saved topic model found.")

    def predict_topics(self, docs: list[str]) -> list[int]:
        self.load_model()
        if not self.model:
            print("Nessun modello BERTopic caricato. Impossibile predire i topic.")
            return [-1] * len(docs)
        try:
            topics, _ = self.model.transform(docs)
            return [int(t) for t in topics]
        except Exception as e:
            print(f"Errore durante la predizione dei topic con BERTopic: {e}")
            return [-1] * len(docs)
