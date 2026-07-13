# Projet 10 — Système de recommandation d'articles — My Content

Projet Master AI Engineer (CentraleSupelec / OpenClassrooms).  
Développement d'un MVP de moteur de recommandation d'articles de presse pour la start-up **My Content**, avec déploiement serverless sur Azure.

---

## Contexte

My Content est une application de lecture d'articles de presse. L'objectif du MVP est de proposer à chaque utilisateur 5 articles personnalisés en fonction de son historique de lecture, à partir de données de clics réelles (dataset Globocom).

---

## Données

Source : [News Portal User Interactions by Globocom](https://www.kaggle.com/datasets/gspmoreira/news-portal-user-interactions-by-globocom)

| Donnée | Valeur |
|--------|--------|
| Utilisateurs | 322 897 |
| Articles cliqués | 46 033 |
| Articles total | 364 047 |
| Clics totaux | ~3 millions |
| Sparsité de la matrice | 99,98 % |

Les données ne contiennent que du **feedback implicite** (clics), sans notes ni likes.

---

## Approches testées

### Content-Based Filtering (CB)
- Embeddings pré-calculés (250 dimensions) réduits par **PCA à 50 dimensions** (94,53 % de variance conservée, gain mémoire −80 %)
- Recommandation par **similarité cosinus** entre articles
- Avantage : gère le cold-start article (embedding disponible dès la publication)
- Precision@5 = **0,0040**

### Collaborative Filtering — ALS (CF)
- Algorithme **ALS** (Alternating Least Squares) via la librairie `implicit`
- Choisi pour deux raisons : feedback implicite uniquement + matrice très creuse
- Factorise la matrice user × article en deux matrices de 50 facteurs latents :
  - `user_factors` : 322 897 × 50 (129,2 Mo)
  - `item_factors` : 46 033 × 50 (18,4 Mo)
- Precision@5 = **0,1060** (×26 par rapport au CB)

**Choix retenu pour le MVP : CF (ALS)**

---

## Structure du projet

```
projet_10/
│
├── notebooks/
│   ├── 01_exploration.ipynb          # Analyse exploratoire des données
│   ├── 02_content_based.ipynb        # Approche modèle Content-Based Filtering
│   ├── 03_collaborative_filtering.ipynb  # Approche modèle ALS (implicit)
│   └── 04_comparaison.ipynb          # Comparaison quantitative et qualitative des 2 approches
│
├── scripts/
│   └── train_and_save_model.py       # Entraînement et sauvegarde des artifacts
│
├── azure_function/
│   ├── function_app.py               # Azure Function — endpoint /recommend
│   ├── host.json
│   └── requirements.txt
│
├── app/
│   └── streamlit_app.py              # Interface utilisateur Streamlit
│
└── presentation/
    └── my_content_presentation_v3.html  # Support de soutenance
```

---

## Artifacts du modèle

Sauvegardés en local et uploadés sur **Azure Blob Storage** :

| Fichier | Contenu | Taille |
|---------|---------|--------|
| `als_model.pkl` | Modèle ALS entraîné | 73,8 Mo |
| `user_item_matrix.pkl` | Matrice user × article (sparse) | 36,7 Mo |
| `user_to_index.pkl` | Mapping user_id → index matrice | 7,6 Mo |
| `index_to_article.pkl` | Mapping index → article_id | 1 Mo |
| `fallback_articles.pkl` | Top-5 articles populaires (cold-start) | 41 octets |

---

## Déploiement Azure

| Ressource | Détail |
|-----------|--------|
| Groupe de ressources | `rg-mycontent` (France Central) |
| Compte de stockage | `stmycontent2026` — conteneur `artifacts` |
| Azure Function | `func-mycontent-reco` — plan Consommation |
| URL endpoint | `https://func-mycontent-reco.azurewebsites.net/api/recommend` |

### Appel de l'API

```bash
curl "https://func-mycontent-reco.azurewebsites.net/api/recommend?user_id=<USER_ID>"
```

Réponse : liste de 5 `article_id` recommandés avec leurs métadonnées disponibles dans le dataset (catégorie, nombre de mots et date de publication) 
Si l'utilisateur est inconnu : retour du fallback top-5 articles populaires.

### Gestion des crédits Azure

La Function App est **mise en pause** entre les sessions pour éviter toute consommation inutile.

```bash
# Redémarrer avant utilisation
az functionapp start --name func-mycontent-reco --resource-group rg-mycontent

# Remettre en pause après
az functionapp stop --name func-mycontent-reco --resource-group rg-mycontent
```

---

## Lancer l'interface Streamlit

```bash
# Activer l'environnement
conda activate env_p10_chantepie

# Lancer l'application
streamlit run app/streamlit_app.py
```

---

## Branches Git

| Branche | Usage |
|---------|-------|
| `main` | Production — connectée à Azure Blob Storage |
| `dev` | Développement local — connectée à Azurite (émulateur Azure) |

---

## Résultats clés

| Critère | Content-Based | Collaborative Filtering (ALS) |
|---------|--------------|-------------------------------|
| Precision@5 | 0,0040 | **0,1060** |
| Cold-start article | ✅ Géré | ❌ Non géré |
| Cold-start utilisateur | Partiel | Fallback popularité |
| Taille artifacts | 72,8 Mo | 147,6 Mo |
| Explicabilité | Variance PCA (94,53 %) | 50 facteurs latents |

---

## Environnement Python

```bash
conda activate env_p10_chantepie  # Python 3.12
```

Dépendances principales : `implicit`, `scikit-learn`, `pandas`, `numpy`, `joblib`, `streamlit`, `azure-storage-blob`, `azure-functions`
