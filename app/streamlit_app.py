"""Streamlit application for My Content article recommendation system."""

import requests
import streamlit as st
import pandas as pd
import joblib
import os

# URL de l'Azure Function (locale pour le développement, Azure pour la production)
AZURE_FUNCTION_URL = os.getenv("AZURE_FUNCTION_URL", "http://localhost:7071/api/recommend")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "news-portal-user-interactions-by-globocom")
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "model_artifacts")


@st.cache_data
def load_user_ids() -> list[int]:
    """Load a sample of user IDs from the clicks dataset.

    Returns:
        List of user IDs available for recommendation.
    """
    user_to_index = joblib.load(os.path.join(ARTIFACTS_DIR, "user_to_index.pkl"))
    return sorted(list(user_to_index.keys()))[:200]


@st.cache_data
def load_articles_metadata() -> pd.DataFrame:
    """Load articles metadata and format publication date.

    Returns:
        DataFrame with article_id as index and metadata columns.
    """
    metadata = pd.read_csv(os.path.join(DATA_DIR, "articles_metadata.csv"))
    metadata["created_at"] = pd.to_datetime(metadata["created_at_ts"], unit="ms").dt.strftime("%d/%m/%Y")
    return metadata.set_index("article_id")


def get_recommendations(user_id: int) -> list[int] | None:
    """Call the Azure Function to get article recommendations for a user.

    Args:
        user_id: The user identifier.

    Returns:
        List of recommended article_ids, or None if the request failed.
    """
    try:
        response = requests.get(AZURE_FUNCTION_URL, params={"user_id": user_id}, timeout=10)
        response.raise_for_status()
        return response.json().get("recommendations", [])
    except requests.exceptions.RequestException as error:
        st.error(f"Erreur lors de l'appel à l'Azure Function : {error}")
        return None


# ── Interface ──────────────────────────────────────────────────────────────────

st.set_page_config(page_title="My Content — Recommandations", page_icon="📰", layout="centered")

st.title("📰 My Content")
st.subheader("Système de recommandation d'articles")
st.markdown("Sélectionnez un utilisateur pour obtenir ses 5 articles recommandés.")

st.divider()

user_ids = load_user_ids()
articles_metadata = load_articles_metadata()

selected_user_id = st.selectbox(
    label="Identifiant utilisateur",
    options=user_ids,
    index=0
)

if st.button("Obtenir les recommandations", type="primary"):
    with st.spinner("Chargement des recommandations..."):
        recommendations = get_recommendations(selected_user_id)

    if recommendations is not None:
        st.success(f"Top 5 articles recommandés pour l'utilisateur **{selected_user_id}** :")
        for rank, article_id in enumerate(recommendations, start=1):
            if article_id in articles_metadata.index:
                row = articles_metadata.loc[article_id]
                st.markdown(
                    f"**{rank}.** Article `{article_id}` — "
                    f"Catégorie `{int(row['category_id'])}` · "
                    f"{int(row['words_count'])} mots · "
                    f"Publié le {row['created_at']}"
                )
            else:
                st.markdown(f"**{rank}.** Article `{article_id}`")
