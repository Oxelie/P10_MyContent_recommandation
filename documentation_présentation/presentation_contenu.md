# Contenu de la présentation — My Content

> Soutenance Projet 10 · Parcours AI Engineer · Stéphanie Duhem · Juillet 2026

---

## Slide 1 — Page de titre

**Parcours AI Engineer — SOUTENANCE PROJET 10**
*"Développer un système de recommandation d'articles - My Content"*
Stéphanie Duhem - Juillet 2026

---

## Slide 2 — 00. Contexte & déroulé du projet

### Le contexte
- My Content : recommandation de lecture → développer un premier **MVP de recommandation d'articles**
- **User story** : "En tant qu'utilisateur, je vais recevoir une sélection de 5 articles."
- **Données** : jeu de données public Globocom (Kaggle) — interactions utilisateurs / articles
- **Contrainte technique** : architecture serverless sur Azure

### Les grandes étapes du projet
- Analyse exploratoire des données et des embeddings d'articles
- Test de deux approches : **Content-Based Filtering** et **Collaborative Filtering**
- Déploiement de la meilleure approche serverless avec **Azure Function**
- Réflexion sur l'architecture cible pour nouveaux utilisateurs et articles

---

## Slide 3 — 01-A. Dataset

### Globocom — News Portal User Interactions (Kaggle)

| Métrique | Valeur |
|----------|--------|
| Utilisateurs | 322 897 |
| Articles cliqués | 46 033 |
| Articles au total | 364 047 |
| Dimensions d'embedding | 250 |

### Conclusions de l'exploration des données
- Distribution très asymétrique des clics : médiane **4 clics**, moyenne **9,25 clics**, max **1 232 clics**
- Matrice user × article très creuse (sparse) : **99,98 % de zéros**
- Embeddings bruts : 364 047 × 250 dims → **364 Mo**
- Les métadonnées (catégorie, nombre de mots, date) → enrichissement de l'affichage

### Problème spécifique à ce dataset
- **Cold-start sévère** : 25 % des utilisateurs ≤ 2 clics
- **Cold-start utilisateur** : nouvel utilisateur sans historique → stratégie du *fallback*
- **Cold-start article** : nouvel article jamais cliqué → géré différemment selon l'approche *(cf. comparaison des modèles)*

---

## Slide 4 — 01-B. Panorama des stratégies de recommandation

### Les grandes familles de moteurs de recommandation

| Stratégie | Principe | Exemple |
|-----------|----------|---------|
| **Content-Based Filtering** | Similarité entre items (contenu, embeddings) | Articles → similarité cosinus Linkedin (jobs) Pandora (Music) IMDb |
| **Collaborative Filtering** | Comportements collectifs (qui a aimé quoi) | ALS, SVD, KNN sur matrice user × item Amazon (CF historique)|
| **Hybride** | Combinaison de plusieurs signaux | Netflix, Spotify, YouTube |
| **Popularité / Editorial** | Top articles, curation humaine | Fallback cold-start Reddit (tri par votes) App Store, Le Monde|
| **Contextuel** | Heure, localisation, appareil, saisonnalité | Publicité ciblée, recherche locale Uber Eats, Booking.com |

### Exemple Netflix — stratégie multi-niveau
- **Par région** : pondération différente selon les marchés (coréens → K-dramas, France → films d'auteur)
- **Par moment** : recommandations différentes le soir VS le week-end
- **Par profil** : un même compte avec plusieurs profils → modèles séparés
- **Hybridation** : CF (comportements) + CB (similarité de contenu) + éditorial (mise en avant de nouveautés)

> My Content MVP : CB + CF testés, hybridation prévue dans l'architecture cible

---

## Slide 5 — 01-C. Deux approches de recommandation testées

### Content-Based Filtering
- Recommander des **articles similaires** à ceux déjà lus
- Comparaison du contenu textuel via les **embeddings**
- ACP appliquée : 250 → 50 dimensions — **variance conservée à 94,53 %** & **80 % de gain mémoire** (364 Mo → 72,8 Mo)
- Métrique : similarité cosinus entre vecteurs d'articles
- Implémentation sans algorithme : approche directe (embeddings → PCA → similarité cosinus)

### Collaborative Filtering (ALS)
- Recommander des articles lus par des **users similaires**
- Aucune analyse du contenu — basé uniquement sur les **clics**
- Algorithme : ALS (Alternating Least Squares, library `implicit`) adapté au **feedback implicite** & optimisé pour les **matrices creuses**
- Métrique : produit scalaire (dot product) entre vecteur utilisateur et vecteurs articles

### Évaluation commune
- Protocole **leave-one-out** sur **500 utilisateurs test** : on masque le dernier article lu de chaque utilisateur test (trié chronologiquement par `click_timestamp`)
- On vérifie si cet article apparaît dans le top des 5 recommandations → score **Hit Rate@5** (⚠ métrique stricte)

---

## Slide 5 — 02-A. Content-Based Filtering — Principe

### Pipeline
**Article lu** *(embeddings 250 dims)* → **ACP** *(réduction → 50 dims)* → **Similarité Cosinus** *(vs tous les autres articles)* → **TOP 5** *(articles les plus proches)*

### Avantages
- Fonctionne dès 1 seul clic
- Cold-start article géré : un nouvel article dispose immédiatement de son embedding → recommandable sans aucun clic préalable
- Résultats interprétables (similarité sémantique)
- Pas de réentraînement pour nouveaux articles ni nouveaux utilisateurs

### Limites
- N'exploite pas les comportements collectifs
- Risque de bulle de filtre (articles trop similaires)
- Dépend de la qualité des embeddings textuels

---

## Slide 6 — 02-B. Content-Based Filtering — Résultats

| Métrique | Valeur |
|----------|--------|
| Hit Rate@5 | **0,40 %** |
| Temps d'évaluation | ~5 min |
| Taille de l'artifact | 72.8 Mo |
| Variance ACP conservée | 94,53 % |

### Analyse
- Sur 500 utilisateurs testés, l'article masqué n'apparaît que très rarement dans le Top 5 : **0,40 %** des cas
- La similarité cosinus capture la proximité sémantique mais pas les préférences individuelles
- Deux articles de même catégorie peuvent être recommandés même si l'utilisateur ne les aurait pas choisis
- Le leave-one-out est strict : un bon article recommandé qui n'est pas exactement l'article masqué n'est pas comptabilisé
- Temps d'évaluation très **rapide** — **Faible taille** de la matrice d'embeddings réduits grâce à l'ACP

---

## Slide 7 — 03-A. Collaborative Filtering (ALS) — Principe

### Pipeline
**Matrice user × article** *(322k × 46k, sparse, 99,98 % de zéros)* → **ALS** *(définit 2 matrices compactes)* → **user_factors** *(322 897 × 50 facteurs latents)* + **item_factors** *(46 033 × 50 facteurs latents)* → **TOP 5** *(par produit scalaire entre les 2 matrices)*

### Avantages
- Exploite les comportements des 322 897 utilisateurs
- Capture des **profils de goût** complexes
- Ne nécessite pas le contenu des articles
- **Efficace** sur données implicites (clics)

### Limites
- **Cold-start user** : contourné par **fallback**
- **Cold-start article** : le CF ne peut pas le recommander (contrairement au Content-Based)
- Faible interprétabilité (facteurs latents, abstraits → effet boite noire)
- Réentraînement complet obligatoire si ajout de nouveaux articles ou utilisateurs

---

## Slide 8 — 03-B. Collaborative Filtering (ALS) — Résultats

| Métrique | Valeur |
|----------|--------|
| Hit Rate@5 | **10,60 %** |
| Temps d'évaluation | ~355 min |
| Taille totale des artifacts (sur disque) | 119.1 Mo |
| Facteurs latents | 50 |

### Analyse
- Sur 500 utilisateurs testés, l'article masqué apparaît dans le Top 5 dans **10,60 %** des cas
- **26 fois plus performant** que le Content-Based sur ce jeu de données
- **Temps d'évaluation long** (~355 min) : le leave-one-out nécessite un réentraînement partiel par utilisateur — acceptable pour l'évaluation mais non viable en production

---

## Slide 9 — 04-A. Comparaison quantitative

| Critères | Content-Based | Collaborative Filtering |
|----------|---------------|------------------------|
| Hit Rate@5 | 0,40 % | **10,60 %** |
| Temps d'évaluation | ~5 min | ~355 min |
| Taille des artifacts | 72.8 Mo | 119.1 Mo (disque) |
| Explicabilité | 94.53 % de variance conservée ACP | 50 facteurs latents (boîte noire) |

---

## Slide 10 — 04-B. Comparaison qualitative

| Critères | Content-Based | Collaborative Filtering |
|----------|---------------|------------------------|
| Cold-start utilisateur | Dès 1 clic | Historique requis |
| Cold-start article | Géré (embedding disponible) | Non géré |
| Ajout de nouveaux articles | pca.transform() suffit | Réentraînement complet |
| Ajout de nouveaux utilisateurs | Pas de réentraînement | Réentraînement complet |
| Interprétabilité | Bonne (similarité sémantique) | Faible (facteurs latents) |
| Temps d'entraînement | Rapide | Long (ALS itératif) |

---

## Slide 11 — 05. Choix retenu & stratégie pour le MVP

### Modèle retenu : le Collaborative Filtering (ALS)
- Hit Rate@5 **26 fois supérieure** au CB (**10,60 %** vs 0,40 %) → la qualité de recommandation prime pour valider un MVP
- Exploiter aux mieux les comportements collectifs de **322 897 utilisateurs**

### Les limites du CF sont connues et gérées
- Cold-start utilisateur → fallback top 5 articles populaires (article #1 : 37 213 clics)
- Cold-start article → CB dans l'architecture cible
- Interprétabilité limitée → acceptable pour un MVP

### Vision production : architecture hybride
- Utilisateur avec historique → CF (ALS)
- Nouvel utilisateur, quelques clics (pas encore dans l'ALS) → Content-Based
- Nouvel utilisateur, 0 clic → Fallback popularité
- Nouvel article → embedding calculé + PCA → disponible immédiatement via CB, intégré à l'ALS au prochain réentraînement

---

## Slide 12 — 06. Description fonctionnelle de l'application

### Flux de l'application
**Utilisateur** *(sélectionne son ID dans Streamlit)* → **HTTP GET** → **Azure Function** *(func-mycontent-reco)* → **joblib** → **Azure Blob Storage** *(5 artifacts .pkl)*

### Détails
- **Entrée** : identifiant utilisateur (entier) via paramètre URL ou body JSON
- **Traitement** : artifacts chargés une seule fois au démarrage (pas à chaque appel) → appel quasi-instantané
- **Sortie** : JSON avec user_id + liste de 5 article_id recommandés
- **Fallback** : utilisateur inconnu → top 5 articles les plus populaires automatiquement
- **Affichage** : pour chaque article → catégorie, nombre de mots, date de publication

---

## Slide 13 — 07. Démo avec interface Streamlit

### Fonctionnalités
- **Liste déroulante** des 200 premiers utilisateurs connus + 1 utilisateur fictif
- **Profil affiché** dès la sélection : nombre de clics et catégories déjà consultées
- **Bouton** "Obtenir les recommandations" → appel HTTP vers l'Azure Function
- **Affichage du Top 5 en cartes** : ID article, ID catégorie, nombre de mots, date de publication
- **Message contextuel** : fallback popularité si utilisateur inconnu, récapitulatif historique sinon

---

## Slide 14 — 07. Démo avec interface Streamlit - suite

*(captures d'écran de l'interface : affichage complet pour utilisateur fictif avec fallback, liste déroulante de sélection des utilisateurs, utilisateur n°122 avec son historique de 42 clics et les catégories consultées, et son Top 5 recommandations)*

---

## Slide 15 — 08. Architecture retenue — Schéma

### Phase entraînement (local)
**Notebooks Python** *(exploration, CB, CF, comparaison)* → **Script d'entraînement** *(`train_and_save_model.py`)* → **Azure Blob Storage** *(5 artifacts .pkl)*

### Phase inférence (Azure — chargement au démarrage)
**Azure Function** *(func-mycontent-reco, Python 3.12, Consumption plan)* ↔ **HTTP GET (user_id)** ↔ **Application Streamlit** *(interface locale MVP, Top 5 + métadonnées)*

---

## Slide 16 — 09. Cold-start — Problème & solution actuelle

### Pourquoi le cold-start est déterminant pour My Content
- My Content est en phase de lancement → beaucoup de nouveaux utilisateurs attendus
- L'architecture cible doit absolument prévoir ce cas dès la conception

### Cold-start utilisateur
- **Problème** : un nouvel utilisateur sans historique de clics ne peut pas être traité par l'ALS
- **Solution MVP** : fallback automatique sur les 5 articles les plus populaires

### Cold-start article
- **Problème** : un nouvel article jamais cliqué n'a pas de ligne dans la matrice — l'ALS ne peut pas le recommander
- **Solution MVP** : non géré
- **Solution CIBLE** : utiliser les embeddings (Content-Based) pour les nouveaux articles

---

## Slide 17 — 10. Architecture cible — Nouveaux utilisateurs & articles

### Routage intelligent selon le profil utilisateur

```
Requête (user_id) → Azure Function (routeur)
    ├── Utilisateur avec historique  → Collaborative Filtering (ALS)
    ├── Nouvel utilisateur (1 clic)  → Content-Based
    └── Aucun historique             → Fallback Top5 - popularité
```

### Mise à jour des données
- **Nouveaux articles** : calcul embedding → ACP (`pca.transform()`) → upload Blob Storage → disponible immédiatement pour le Content-Based, intégré à l'ALS au prochain réentraînement
- **Nouveaux utilisateurs** : CB dès le 1er clic, fallback à 0 clic — intégrés à l'ALS au prochain réentraînement (⚠ user_id central)

### Stratégie de réentraînement de l'ALS
- Réentraînement **périodique** (ex. toutes les nuits ou toutes les semaines) : le plus courant en production
- Réentraînement **par seuil** : déclenché quand un volume significatif est atteint (ex. +5 % de nouveaux utilisateurs)
- Entre deux réentraînements, le CB prend le relais pour les nouveaux articles et utilisateurs

---

## Slide 18 — 11. Industrialisation & MLOps

### Versioning — GitHub
- Dépôt : `Oxelie/P10_MyContent_recommandation`
- Branche `dev` : développement local (Azurite)
- Branche `main` : production Azure (Blob Storage)

### Structure du projet
```
notebooks/
    01_exploration.ipynb
    02_content_based.ipynb
    03_collaborative_filtering.ipynb
    04_comparaison.ipynb
scripts/
    train_and_save_model.py
azure_function/
    function_app.py · requirements.txt
app/
    streamlit_app.py
```

### Entraînement & déploiement
- Script `train_and_save_model.py` : entraîne le modèle sur le dataset complet et sauvegarde les 5 artifacts
- Artifacts versionnés sur **Azure Blob Storage** — séparation claire entraînement / inférence
- Déploiement : `func azure functionapp publish`

---

## Slide 19 — 12. Bilan & perspectives

### Réalisations du MVP
- 2 approches testées et comparées (CB + CF)
- CF (ALS) avec **Hit Rate@5 = 10,60 %**
- Azure Function déployée et opérationnelle
- Interface Streamlit fonctionnelle
- Fallback cold-start implémenté
- Code versionné sur GitHub (dev / main)
- Validation technique d'un système de recommandation **ServerLess** sur Azure

### Perspectives de production
- Architecture hybride CF + Content-Based
- Pipeline de réentraînement automatisé (Azure ML)
- Collecte de vraies données utilisateurs My Content
- Authentification Azure Function (FUNCTION level)
- A/B testing des approches en production
- Métriques métier : taux de clic, engagement (temps passé, articles lus)

---

## Slide 20 — 13. Évolutions possibles du moteur de recommandation

### Suivi de la diversité des recommandations
- **Problème** : si un utilisateur reçoit toujours les mêmes 5 articles → signal d'appauvrissement du modèle ou d'un biais de renforcement, ‘bulle de filtre’ qui s’installe progressivement
- **Solution** : tracer les recommandations produites par utilisateur et dans le temps → détecter les répétitions, mesurer la diversité (entropie, taux de renouvellement)

### Adaptation au comportement de l'utilisateur face aux recommandations
- **Signal implicite** : l'utilisateur clique-t-il sur les articles recommandés ? Les lit-il en entier ?
- **Profil de curiosité** : certains utilisateurs cherchent à rester dans leur thème (bulle assumée), d'autres aiment découvrir — le modèle devrait s'adapter
- **Levier** : ajuster la pondération diversité / pertinence selon le profil observé (ex. paramètre α sur la similarité cosinus ou bruit exploratoire sur l'ALS)

### Prise en compte de la saisonnalité
- **Exemples concrets** : Coupe du Monde → pic d'articles sportifs ; fêtes de fin d'année → actualités culturelles/économiques ; élections → articles politiques
- **Risque sans gestion** : le modèle sur-recommande des articles populaires au moment de l'entraînement, même si la saison est passée
- **Solutions** : pondérer les clics récents plus fortement (decay temporel), réentraîner plus fréquemment en période de pic, ou ajouter un signal calendaire explicite

---

## Slide 21 — Annexe. Documentation

### Panorama des stratégies de recommandation
- [Recommender Systems Handbook](https://www.researchgate.net/publication/227268858_Recommender_Systems_Handbook)
- ["The Netflix Recommender System" — Gomez-Uribe, Hunt 2015](https://ailab-ua.github.io/courses/resources/netflix_recommender_system_tmis_2015.pdf)

### Collaborative Filtering / ALS
- [github.com/benfred/implicit](https://github.com/benfred/implicit)
- ["Collaborative Filtering for Implicit Feedback Datasets" — Hu, Koren, Volinsky 2008](https://ieeexplore.ieee.org/document/4781121)

### Collaborative Filtering / SVD
- [Recommender System made easy with Scikit-Surprise](https://surpriselib.com/)

### Content-Based / embeddings
- [Scikit-learn — Décomposition PCA](https://scikit-learn.org/stable/modules/decomposition.html#pca)
- [Scikit-learn — Similarité cosinus](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html)

### Azure Functions / Serverless
- [Bindings Blob Storage](https://learn.microsoft.com/fr-fr/azure/azure-functions/functions-bindings-storage-blob)
- [Créer une application de fonction serverless avec Azure Functions](https://learn.microsoft.com/fr-fr/azure/azure-functions/functions-create-function-app-portal)

### Évaluation — Hit Rate@K
- [Evaluating Recommender Systems — Metrics for evaluating Recommender Systems](https://towardsdatascience.com/evaluating-recommender-systems-metrics-and-methodologies-9b9f4a7e58c4/)
- [Ranking Evaluation Metrics for Recommender Systems](https://towardsdatascience.com/ranking-evaluation-metrics-for-recommender-systems-263d0a66ef54/)

---

