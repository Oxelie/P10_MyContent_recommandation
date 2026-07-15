# Projet 10 — Système de recommandation d'articles — My Content

Projet Master AI Engineer (CentraleSupelec / OpenClassrooms).  
Développement d'un MVP de moteur de recommandation d'articles de presse, avec déploiement serverless sur Azure.

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
- Hit Rate@5 = **0,0040**

### Collaborative Filtering — ALS (CF)
- Algorithme **ALS** (Alternating Least Squares) via la librairie `implicit`
- Choisi pour deux raisons : feedback implicite uniquement + matrice très creuse
- Factorise la matrice user × article en deux matrices de 50 facteurs latents :
  - `user_factors` : 322 897 × 50 (129,2 Mo)
  - `item_factors` : 46 033 × 50 (18,4 Mo)
- Hit Rate@5 = **0,1060** (×26 par rapport au CB)

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
├── documentation/
│   ├── architecture.md               # Schémas d'architecture (Mermaid)
│   └── presentation_contenu.md       # Contenu des slides de soutenance
│
├── presentation/
│   └── pres_projet_10.pdf            # Support de soutenance
│
├── requirements.txt                  # Dépendances app Streamlit uniquement
└── requirements_notebooks.txt        # Dépendances notebooks & entraînement
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
**CAS Utilisateur avec historique**
- L'utilisateur fait partie de la matrice user_to_index.
- Réponse : liste de 5 `article_id` recommandés par le modèle ALS pour cet utlisateur.

**CAS Utilisateur sans historique**
- L'utilisateur est fictif, il est créé pour les besoins de tests du fallback top-5 articles.
- Réponse : retour du fallback top-5 articles populaires.

**Affichage des résultats**
- Article ID - Catégorie ID - Nbre de mots - Date de publicaton

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

L'application se connecte par défaut à l'Azure Function déployée.

```bash
# Installer les dépendances
pip install streamlit requests pandas joblib

# Lancer l'application
streamlit run app/streamlit_app.py
```

**Note :** 
*La Function App est mise en pause entre les sessions pour économiser les crédits Azure. Contacter la développeuse pour la réactiver avant une démonstration.*


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
| Hit Rate@5 | 0,0040 | **0,1060** |
| Cold-start article | ✅ Géré | ❌ Non géré |
| Cold-start utilisateur | Partiel | Fallback popularité |
| Taille artifacts | 72,8 Mo | 119,1 Mo |
| Explicabilité | Variance PCA (94,53 %) | 50 facteurs latents |

---

## Environnement Python

Python 3.12. Deux fichiers de dépendances selon l'usage :

```bash
# Pour lancer l'interface Streamlit uniquement
pip install -r requirements.txt

# Pour reproduire les notebooks et le script d'entraînement
pip install -r requirements_notebooks.txt
```

---


## Développement local (Azurite)
Pour tester sans consommer de crédits Azure, la branche dev utilise Azurite (émulateur Azure Storage local) 

```bash
# Terminal 1 — démarrer Azurite
azurite --location AzuriteConfig

# Terminal 2 — démarrer la Function en local
cd projet_10
source ../.venv/bin/activate
cd azure_function
func start

# Terminal 3 — lancer Streamlit en pointant vers la Function locale
AZURE_FUNCTION_URL=http://localhost:7071/api/recommend streamlit run app/streamlit_app.py
```


