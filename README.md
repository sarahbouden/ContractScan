# ContractScan

**ContractScan** est un POC de comparaison automatique de clauses contractuelles. Il compare un template de référence (« Thales ») à un template imposé par un fournisseur, détecte les divergences clause par clause, et laisse un juriste valider chaque décision (Human-in-the-Loop) avant de générer un rapport PDF. Le LLM (Mistral) tourne intégralement en local via Ollama — aucune donnée contractuelle ne quitte la machine.

## Architecture

```
                    ┌─────────────────────────┐
                    │   Interface Streamlit    │
                    │        (app.py)          │
                    └────────────┬─────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                         │
        ▼                        ▼                         ▼
┌───────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  src/parser.py │      │ src/extractor.py │      │ src/comparator.py│
│  PDF / DOCX    │─────▶│  Extraction des  │─────▶│  Similarité +    │
│  → texte brut  │      │  clauses (LLM)   │      │  scoring + diff  │
└───────────────┘      └────────┬─────────┘      └────────┬─────────┘
                                 │                          │
                                 ▼                          ▼
                        ┌──────────────┐          ┌──────────────────┐
                        │ Ollama /     │          │ sentence-        │
                        │ Mistral      │          │ transformers      │
                        │ (100% local) │          │ (embeddings)      │
                        └──────────────┘          └────────┬─────────┘
                                                            │
                                                            ▼
                                                  ┌──────────────────┐
                                                  │ src/reporter.py  │
                                                  │ Rapport PDF      │
                                                  │ (FPDF2)          │
                                                  └──────────────────┘
```

## Prérequis

- Python 3.11+ (testé avec Python 3.12)
- [Ollama](https://ollama.com/download) installé localement
- Modèle Mistral (`ollama pull mistral`, ~4 Go)
- Docker + Docker Compose (optionnel, pour le déploiement conteneurisé)

## Installation

```bash
git clone https://github.com/sarahbouden/ContractScan.git
cd ContractScan
python -m venv venv && source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt
ollama pull mistral
```

> Sous Windows, si `pip install` échoue sur `scikit-learn` (pas de wheel précompilé
> pour les toutes dernières versions de Python), recréer le venv avec Python 3.12 :
> `py -3.12 -m venv venv`.

## Préparer les données de test (CUAD)

```bash
python scripts/download_cuad.py   # télécharge 10 contrats PDF depuis HuggingFace (CUAD)
python scripts/pdf_to_docx.py     # convertit les 5 premiers en DOCX
```

## Lancement

**Sans Docker (développement) :**
```bash
streamlit run app.py
```

**Avec Docker :**
```bash
docker compose up --build
```

Ouvrir ensuite [http://localhost:8501](http://localhost:8501).

> **Docker + Ollama sur l'hôte** : le conteneur ne peut pas joindre Ollama via
> `localhost` (qui désignerait le conteneur lui-même). `docker-compose.yml`
> définit `OLLAMA_BASE_URL=http://host.docker.internal:11434` pour pointer
> vers l'hôte — inutile d'y toucher si Ollama tourne sur la même machine que
> Docker Desktop.

## Performance

L'analyse d'une paire de contrats tourne entièrement sur CPU/GPU local (Mistral 7B
quantifié via Ollama) : selon la machine, compter de 1 à 5 minutes pour une
analyse complète (extraction des deux contrats + comparaison + divergences).
Sur GPU d'entrée de gamme (ex. 6 Go de VRAM), la génération de texte est le
facteur limitant, pas la lecture des contrats — c'est pourquoi `src/extractor.py`
demande des extraits de clause courts plutôt que le texte intégral, et
`src/comparator.py` regroupe les descriptions de divergence par lots au lieu
d'un appel LLM par clause.

## Utilisation

1. Charger le template Thales (PDF ou DOCX) et le template Fournisseur.
2. Cliquer sur « Analyser les contrats » : extraction du texte, extraction des clauses via Mistral, puis comparaison par similarité sémantique.
3. Filtrer les clauses par statut (Conforme / À vérifier / Critique) et les passer en revue une par une.
4. Pour chaque clause : consulter la divergence détectée, choisir une décision (Accepter / Rejeter / À négocier) et ajouter un commentaire juridique.
5. Générer et télécharger le rapport PDF final.

## Captures d'écran

*(à ajouter après la démo)*

- `docs/screenshot_upload.png` — écran de chargement des deux contrats
- `docs/screenshot_synthese.png` — synthèse et métriques globales
- `docs/screenshot_clause.png` — revue clause par clause avec décision
- `docs/screenshot_rapport.png` — extrait du rapport PDF généré

## Sécurité

| Point | Détail |
|---|---|
| LLM 100 % local | Mistral via Ollama — aucun appel réseau externe |
| Données en mémoire | Aucun stockage des contrats sur disque après la session |
| Aucune base de données | Pas de persistance, pas de logs contractuels |
| Human-in-the-loop | Aucune décision automatique — le juriste valide tout |
| Docker isolé | Conteneur local, pas de port exposé sur internet |

## Licence

MIT
