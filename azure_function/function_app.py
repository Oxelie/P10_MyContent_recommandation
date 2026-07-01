"""Azure Function for article recommendations using ALS collaborative filtering."""

import io
import json
import logging
import os
import joblib
import azure.functions as func
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()

CONTAINER_NAME = "artifacts"
ARTIFACT_NAMES = [
    "als_model.pkl",
    "user_item_matrix.pkl",
    "user_to_index.pkl",
    "index_to_article.pkl",
    "fallback_articles.pkl",
]


def _load_artifact_from_blob(blob_client, name: str):
    """Download a joblib artifact from Azure Blob Storage into memory.

    Args:
        blob_client: Azure BlobServiceClient instance.
        name: Blob filename to download.

    Returns:
        Deserialized Python object.
    """
    blob = blob_client.get_blob_client(container=CONTAINER_NAME, blob=name)
    buffer = io.BytesIO(blob.download_blob().readall())
    return joblib.load(buffer)


logging.info("Connexion au Blob Storage et chargement des artifacts...")

_connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
_blob_service = BlobServiceClient.from_connection_string(_connection_string)

model = _load_artifact_from_blob(_blob_service, "als_model.pkl")
user_item_matrix = _load_artifact_from_blob(_blob_service, "user_item_matrix.pkl")
user_to_index = _load_artifact_from_blob(_blob_service, "user_to_index.pkl")
index_to_article = _load_artifact_from_blob(_blob_service, "index_to_article.pkl")
fallback_articles = _load_artifact_from_blob(_blob_service, "fallback_articles.pkl")

logging.info("Artifacts chargés depuis Azure Blob Storage.")


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

    return func.HttpResponse(
        json.dumps({"user_id": user_id, "recommendations": recommendations}),
        status_code=200,
        mimetype="application/json"
    )
