"""Streamlit application for My Content article recommendation system."""

import requests
import streamlit as st
import pandas as pd
import joblib
import os

# URL de l'Azure Function (locale pour le développement, Azure pour la production)
AZURE_FUNCTION_URL = os.getenv("AZURE_FUNCTION_URL", "https://func-mycontent-reco.azurewebsites.net/api/recommend")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "news-portal-user-interactions-by-globocom")
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "model_artifacts")

FICTITIOUS_USER_ID = 999999


@st.cache_data
def load_user_data() -> tuple[list[int], dict[int, int]]:
    """Load user IDs and their click counts from artifacts.

    Returns:
        Tuple of (list of user_ids, dict of user_id → click count).
    """
    user_to_index = joblib.load(os.path.join(ARTIFACTS_DIR, "user_to_index.pkl"))
    user_item_matrix = joblib.load(os.path.join(ARTIFACTS_DIR, "user_item_matrix.pkl"))
    user_ids = sorted(list(user_to_index.keys()))[:200]
    # ajout de la mention du nbre de clics pour chaque utilisateur dans le dictionnaire click_counts (pour affichage dans le selectbox)
    click_counts = {uid: int(user_item_matrix[user_to_index[uid]].nnz) for uid in user_ids}
    return user_ids, click_counts


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


def format_user_option(user_id: int, click_counts: dict[int, int]) -> str:
    """Format a user ID for display in the selectbox.

    Args:
        user_id: The user identifier.
        click_counts: Dict of user_id → click count.

    Returns:
        Formatted string for display.
    """
    if user_id == FICTITIOUS_USER_ID:
        return "Nouvel utilisateur — 0 clic (fallback)"
    count = click_counts.get(user_id, 0)
    return f"{user_id} — {count} clic(s)"


# ── Interface ──────────────────────────────────────────────────────────────────

st.set_page_config(page_title="My Content — Recommandations", page_icon="📰", layout="centered")

st.title("📰 My Content")
st.subheader("Système de recommandation d'articles")
st.markdown("Sélectionnez un utilisateur pour obtenir ses 5 articles recommandés.")

st.divider()

user_ids, click_counts = load_user_data()
articles_metadata = load_articles_metadata()

# Ajout de l'utilisateur fictif en tête de liste pour tester le fallback
all_options = [FICTITIOUS_USER_ID] + user_ids

selected_user_id = st.selectbox(
    label="Identifiant utilisateur",
    options=all_options,
    index=0,
    format_func=lambda uid: format_user_option(uid, click_counts)
)

if st.button("Obtenir les recommandations", type="primary"):
    with st.spinner("Chargement des recommandations..."):
        recommendations = get_recommendations(selected_user_id)

    if recommendations is not None:
        if selected_user_id == FICTITIOUS_USER_ID:
            st.info("Utilisateur inconnu du modèle — affichage du **fallback : top 5 articles les plus populaires**.")
        else:
            count = click_counts.get(selected_user_id, 0)
            st.success(f"Top 5 articles recommandés pour l'utilisateur **{selected_user_id}** (historique {count} clic(s)) :")

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
