# Architecture du projet — My Content

## Architecture déployée (MVP)

```mermaid
graph LR
    A["🖥️ Application Streamlit\ninterface utilisateur\nlancée en local"] -->|"HTTP GET /recommend?user_id=X"| B["⚡ Azure Function\nfunc-mycontent-reco\nConsumption plan · Python 3.12"]
    B -->|"joblib.load() au démarrage"| C["☁️ Azure Blob Storage\nstmycontent2026 / artifacts\n5 fichiers .pkl"]
    B -->|"JSON {user_id, recommendations}"| A
```

### Phase entraînement (local)

```mermaid
graph LR
    N["📓 Notebooks Python\n01_exploration\n02_content_based\n03_collaborative_filtering\n04_comparaison"] --> S["🐍 Script\ntrain_and_save_model.py"]
    S -->|"joblib.dump()"| PKL["📦 5 artifacts .pkl\nmodel_artifacts/"]
    PKL -->|"az storage blob upload"| BLOB["☁️ Azure Blob Storage"]
```

### Phase inférence (Azure)

```mermaid
sequenceDiagram
    participant U as Utilisateur (Streamlit)
    participant F as Azure Function
    participant B as Azure Blob Storage

    Note over F: Au démarrage — chargement unique des artifacts
    F->>B: joblib.load(als_model.pkl)
    F->>B: joblib.load(user_item_matrix.pkl)
    F->>B: joblib.load(user_to_index.pkl)
    F->>B: joblib.load(index_to_article.pkl)
    F->>B: joblib.load(fallback_articles.pkl)

    U->>F: GET /recommend?user_id=122
    alt Utilisateur connu
        F->>F: model.recommend(user_index, ...)
        F-->>U: {"recommendations": [284985, 58580, ...]}
    else Utilisateur inconnu (cold-start)
        F->>F: fallback_articles[:5]
        F-->>U: {"recommendations": [169974, 272143, ...]}
    end
```

---

## Architecture cible (hybride)

```mermaid
graph TD
    REQ["Requête\nuser_id"] --> AF["Azure Function\nrouteur"]
    AF -->|"Utilisateur avec historique"| CF["Collaborative Filtering ALS\nuser_factors · item_factors"]
    AF -->|"Nouvel utilisateur ≥ 1 clic"| CB["Content-Based Filtering\nembedding → PCA → cosinus"]
    AF -->|"0 clic"| FB["Fallback popularité\nTop 5 articles les plus cliqués"]
```

### Gestion des nouveaux articles (cible)

```mermaid
graph LR
    ART["Nouvel article publié"] --> EMB["Calcul embedding\n250 dims"]
    EMB --> PCA["pca.transform()\n→ 50 dims"]
    PCA --> BLOB["Upload Blob Storage"]
    BLOB -->|"immédiatement"| CB_DISP["Disponible via CB"]
    BLOB -->|"prochain réentraînement"| ALS_DISP["Intégré à l'ALS"]
```

---

## Artifacts du modèle

| Fichier | Contenu | Taille |
|---------|---------|--------|
| `als_model.pkl` | Modèle ALS entraîné (`implicit`) | 73,8 Mo |
| `user_item_matrix.pkl` | Matrice user × article (sparse CSR) | 36,7 Mo |
| `user_to_index.pkl` | Mapping user_id → index matrice | 7,6 Mo |
| `index_to_article.pkl` | Mapping index → article_id | 1 Mo |
| `fallback_articles.pkl` | Top-5 articles populaires | 41 octets |

**Total : 147,6 Mo** · Stockés sur Azure Blob Storage (`stmycontent2026/artifacts`)

---

## Infrastructure Azure

| Ressource | Détail |
|-----------|--------|
| Groupe de ressources | `rg-mycontent` (France Central) |
| Compte de stockage | `stmycontent2026` |
| Azure Function | `func-mycontent-reco` — plan Consommation |
| URL endpoint | `https://func-mycontent-reco.azurewebsites.net/api/recommend` |

> ⚠️ La Function App est mise en pause entre les sessions pour économiser les crédits.
>
> ```bash
> az functionapp start --name func-mycontent-reco --resource-group rg-mycontent
> az functionapp stop --name func-mycontent-reco --resource-group rg-mycontent
> ```
