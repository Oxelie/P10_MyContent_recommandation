"""Azure Function for article recommendations using ALS collaborative filtering."""

import json
import logging
import os
import joblib
import azure.functions as func

app = func.FunctionApp()

# Chemins vers les artifacts (relatifs au dossier de la fonction)
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "model_artifacts")

# Chargement des artifacts au démarrage (une seule fois, pas à chaque appel)
logging.info("Chargement des artifacts...")
model = joblib.load(os.path.join(ARTIFACTS_DIR, "als_model.pkl"))
user_item_matrix = joblib.load(os.path.join(ARTIFACTS_DIR, "user_item_matrix.pkl"))
user_to_index = joblib.load(os.path.join(ARTIFACTS_DIR, "user_to_index.pkl"))
index_to_article = joblib.load(os.path.join(ARTIFACTS_DIR, "index_to_article.pkl"))
fallback_articles = joblib.load(os.path.join(ARTIFACTS_DIR, "fallback_articles.pkl"))
logging.info("Artifacts chargés.")


def recommend_for_user(user_id: int, top_n: int = 5) -> list[int]:
    """Return top N article recommendations for a given user.

    Args:
        user_id: The user identifier.
        top_n: Number of articles to recommend.

    Returns:
        List of recommended article_ids. Falls back to popular articles if user is unknown.
    """
    if user_id not in user_to_index:
        logging.info(f"Utilisateur {user_id} inconnu — fallback sur articles populaires.")
        return [int(a) for a in fallback_articles[:top_n]]

    user_index = user_to_index[user_id]
    item_indices, _ = model.recommend(
        user_index,
        user_item_matrix[user_index],
        N=top_n,
        filter_already_liked_items=True
    )
    return [int(index_to_article[int(idx)]) for idx in item_indices]


@app.route(route="recommend", auth_level=func.AuthLevel.ANONYMOUS)
def recommend(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP trigger that returns top 5 article recommendations for a user.

    Args:
        req: HTTP request containing user_id as query parameter or JSON body.

    Returns:
        JSON response with list of recommended article_ids.
    """
    logging.info("Requête de recommandation reçue.")

    # Récupération du user_id depuis les paramètres de la requête ou le body JSON
    user_id = req.params.get("user_id")
    if not user_id:
        try:
            body = req.get_json()
            user_id = body.get("user_id")
        except ValueError:
            pass

    if not user_id:
        return func.HttpResponse(
            json.dumps({"error": "Paramètre user_id manquant."}),
            status_code=400,
            mimetype="application/json"
        )

    try:
        user_id = int(user_id)
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "user_id doit être un entier."}),
            status_code=400,
            mimetype="application/json"
        )

    recommendations = recommend_for_user(user_id)

    response_body = {
        "user_id": user_id,
        "recommendations": recommendations
    }

    return func.HttpResponse(
        json.dumps(response_body),
        status_code=200,
        mimetype="application/json"
    )
