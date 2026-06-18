"""Train the ALS collaborative filtering model and save all artifacts for deployment."""

import os
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from implicit.als import AlternatingLeastSquares


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "news-portal-user-interactions-by-globocom")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "model_artifacts")

ALS_FACTORS = 50
ALS_ITERATIONS = 20
ALS_REGULARIZATION = 0.1
RANDOM_STATE = 42
FALLBACK_TOP_N = 5


def load_clicks(data_dir: str) -> pd.DataFrame:
    """Load the full clicks dataset from parquet.

    Args:
        data_dir: Path to the data directory.

    Returns:
        DataFrame containing all click interactions.
    """
    path = os.path.join(data_dir, "clicks_full.parquet")
    clicks = pd.read_parquet(path)
    print(f"Clics chargés : {clicks.shape}")
    return clicks


def build_mappings(clicks: pd.DataFrame) -> tuple[dict, dict, dict]:
    """Build user and article index mappings from click data.

    Args:
        clicks: DataFrame containing user-article click interactions.

    Returns:
        Tuple of (user_to_index, article_to_index, index_to_article).
    """
    user_ids = clicks["user_id"].unique()
    article_ids = clicks["click_article_id"].unique()

    user_to_index = {user_id: idx for idx, user_id in enumerate(user_ids)}
    article_to_index = {article_id: idx for idx, article_id in enumerate(article_ids)}
    index_to_article = {idx: article_id for article_id, idx in article_to_index.items()}

    print(f"Utilisateurs : {len(user_to_index)}")
    print(f"Articles : {len(article_to_index)}")
    return user_to_index, article_to_index, index_to_article


def build_user_item_matrix(
    clicks: pd.DataFrame,
    user_to_index: dict,
    article_to_index: dict
) -> csr_matrix:
    """Build a sparse user-item interaction matrix from click data.

    Args:
        clicks: DataFrame containing user-article click interactions.
        user_to_index: Mapping from user_id to row index.
        article_to_index: Mapping from article_id to column index.

    Returns:
        Sparse matrix of shape (n_users, n_articles) with click counts as values.
    """
    click_counts = clicks.groupby(["user_id", "click_article_id"]).size().reset_index(name="click_count")

    row_indices = click_counts["user_id"].map(user_to_index).values
    col_indices = click_counts["click_article_id"].map(article_to_index).values
    values = click_counts["click_count"].values

    matrix = csr_matrix(
        (values, (row_indices, col_indices)),
        shape=(len(user_to_index), len(article_to_index))
    )
    print(f"Matrice user-item : {matrix.shape}, densité : {matrix.nnz / (matrix.shape[0] * matrix.shape[1]):.6f}")
    return matrix


def train_als_model(user_item_matrix: csr_matrix) -> AlternatingLeastSquares:
    """Train an ALS model on the user-item matrix.

    Args:
        user_item_matrix: Sparse user-item interaction matrix.

    Returns:
        Trained ALS model.
    """
    model = AlternatingLeastSquares(
        factors=ALS_FACTORS,
        iterations=ALS_ITERATIONS,
        regularization=ALS_REGULARIZATION,
        random_state=RANDOM_STATE
    )
    model.fit(user_item_matrix)
    print("Modèle ALS entraîné")
    return model


def get_fallback_articles(clicks: pd.DataFrame, top_n: int = FALLBACK_TOP_N) -> list[int]:
    """Get the most popular articles as fallback recommendations.

    Args:
        clicks: DataFrame containing user-article click interactions.
        top_n: Number of popular articles to return.

    Returns:
        List of the most clicked article_ids.
    """
    return (
        clicks["click_article_id"]
        .value_counts()
        .head(top_n)
        .index
        .tolist()
    )


def save_artifacts(
    model: AlternatingLeastSquares,
    user_item_matrix: csr_matrix,
    user_to_index: dict,
    index_to_article: dict,
    fallback_articles: list[int],
    output_dir: str
) -> None:
    """Save all model artifacts needed for deployment.

    Args:
        model: Trained ALS model.
        user_item_matrix: Sparse user-item interaction matrix needed for inference.
        user_to_index: Mapping from user_id to matrix row index.
        index_to_article: Mapping from matrix column index to article_id.
        fallback_articles: List of popular article_ids for cold-start fallback.
        output_dir: Directory where artifacts will be saved.
    """
    os.makedirs(output_dir, exist_ok=True)

    joblib.dump(model, os.path.join(output_dir, "als_model.pkl"))
    joblib.dump(user_item_matrix, os.path.join(output_dir, "user_item_matrix.pkl"))
    joblib.dump(user_to_index, os.path.join(output_dir, "user_to_index.pkl"))
    joblib.dump(index_to_article, os.path.join(output_dir, "index_to_article.pkl"))
    joblib.dump(fallback_articles, os.path.join(output_dir, "fallback_articles.pkl"))

    print(f"Artifacts sauvegardés dans : {output_dir}")
    for filename in ["als_model.pkl", "user_item_matrix.pkl", "user_to_index.pkl", "index_to_article.pkl", "fallback_articles.pkl"]:
        size_mb = os.path.getsize(os.path.join(output_dir, filename)) / 1e6
        print(f"  {filename} : {size_mb:.1f} Mo")


if __name__ == "__main__":
    print("=== Entraînement et sauvegarde du modèle CF ===\n")

    clicks = load_clicks(DATA_DIR)
    user_to_index, article_to_index, index_to_article = build_mappings(clicks)
    user_item_matrix = build_user_item_matrix(clicks, user_to_index, article_to_index)
    model = train_als_model(user_item_matrix)
    fallback_articles = get_fallback_articles(clicks)

    print(f"\nFallback articles (top {FALLBACK_TOP_N}) : {fallback_articles}")

    save_artifacts(model, user_item_matrix, user_to_index, index_to_article, fallback_articles, OUTPUT_DIR)

    print("\nTerminé !")
