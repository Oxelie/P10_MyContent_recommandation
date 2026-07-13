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
    """Load user IDs, click counts, and article popularity from artifacts.

    Returns:
        Tuple of (list of user_ids, dict of user_id → click count).
    """
    user_to_index = joblib.load(os.path.join(ARTIFACTS_DIR, "user_to_index.pkl"))
    user_item_matrix = joblib.load(os.path.join(ARTIFACTS_DIR, "user_item_matrix.pkl"))
    user_ids = sorted(list(user_to_index.keys()))[:200]
    click_counts = {uid: int(user_item_matrix[user_to_index[uid]].nnz) for uid in user_ids}
    return user_ids, click_counts


@st.cache_data
def load_full_artifacts() -> tuple:
    """Load artifacts needed for user history display.

    Returns:
        Tuple of (user_to_index, user_item_matrix, index_to_article).
    """
    user_to_index = joblib.load(os.path.join(ARTIFACTS_DIR, "user_to_index.pkl"))
    user_item_matrix = joblib.load(os.path.join(ARTIFACTS_DIR, "user_item_matrix.pkl"))
    index_to_article = joblib.load(os.path.join(ARTIFACTS_DIR, "index_to_article.pkl"))
    return user_to_index, user_item_matrix, index_to_article


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
    return f"Utilisateur n°{user_id}"


def get_user_categories(user_id: int, user_to_index: dict, user_item_matrix, index_to_article: dict, articles_metadata: pd.DataFrame) -> list[int]:
    """Return the list of distinct category_ids clicked by the user.

    Args:
        user_id: The user identifier.
        user_to_index: Mapping user_id → matrix row index.
        user_item_matrix: Sparse user × article matrix.
        index_to_article: Mapping matrix column index → article_id.
        articles_metadata: DataFrame with article metadata.

    Returns:
        Sorted list of distinct category_ids the user has clicked.
    """
    if user_id not in user_to_index:
        return []
    user_index = user_to_index[user_id]
    clicked_indices = user_item_matrix[user_index].nonzero()[1]
    clicked_articles = [index_to_article[int(idx)] for idx in clicked_indices]
    known_articles = [a for a in clicked_articles if a in articles_metadata.index]
    categories = articles_metadata.loc[known_articles, "category_id"].dropna().astype(int).unique().tolist()
    return sorted(categories)


# ── Interface ──────────────────────────────────────────────────────────────────

st.set_page_config(page_title="My Content — Recommandations", page_icon="📰", layout="centered")

st.title("📰 My Content")
st.subheader("Système de recommandation d'articles")
st.markdown("Sélectionnez un utilisateur pour obtenir ses 5 articles recommandés.")

st.divider()

user_ids, click_counts = load_user_data()
articles_metadata = load_articles_metadata()
user_to_index, user_item_matrix, index_to_article = load_full_artifacts()

# Ajout de l'utilisateur fictif en tête de liste pour tester le fallback
all_options = [FICTITIOUS_USER_ID] + user_ids

selected_user_id = st.selectbox(
    label="Identifiant utilisateur & historique en nombre de clics",
    options=all_options,
    index=0,
    format_func=lambda uid: format_user_option(uid, click_counts)
)

# Affichage de l'historique de catégories de l'utilisateur sélectionné
if selected_user_id != FICTITIOUS_USER_ID:
    user_categories = get_user_categories(selected_user_id, user_to_index, user_item_matrix, index_to_article, articles_metadata)
    count = click_counts.get(selected_user_id, 0)
    categories_str = " · ".join([f"`{c}`" for c in user_categories]) if user_categories else "—"
    st.caption(f"Historique : {count} clic(s)")
    st.caption(f"Catégories consultées : {categories_str}")

if st.button("Obtenir les recommandations", type="primary"):
    with st.spinner("Chargement des recommandations..."):
        recommendations = get_recommendations(selected_user_id)

    if recommendations is not None:
        if selected_user_id == FICTITIOUS_USER_ID:
            st.info("Utilisateur inconnu du modèle — affichage du **fallback : top 5 articles les plus populaires**")
        else:
            count = click_counts.get(selected_user_id, 0)
            st.success(f"Top 5 articles recommandés pour l'utilisateur **{selected_user_id}** :")

        for rank, article_id in enumerate(recommendations, start=1):
            if article_id in articles_metadata.index:
                row = articles_metadata.loc[article_id]
                col_rank, col_info = st.columns([0.5, 4])
                with col_rank:
                    st.markdown(f"**#{rank}**")
                with col_info:
                    st.markdown(
                        f"Article `{article_id}` &nbsp;·&nbsp; "
                        f"📁 Catégorie `{int(row['category_id'])}` &nbsp;·&nbsp; "
                        f"📝 {int(row['words_count'])} mots &nbsp;·&nbsp; "
                        f"📅 {row['created_at']}"
                    )
            else:
                st.markdown(f"**#{rank}.** Article `{article_id}`")
