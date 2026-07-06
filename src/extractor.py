import json
import os
from json_repair import repair_json
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

# Initialiser Mistral local via Ollama.
# OLLAMA_BASE_URL permet de pointer vers l'hôte depuis un conteneur Docker
# (ex: http://host.docker.internal:11434), où "localhost" désignerait le
# conteneur lui-même et non la machine qui fait tourner Ollama.
# num_predict borne la longueur de génération : sur un GPU modeste, demander
# à Mistral de recopier verbatim de longs extraits de contrat pour chaque
# clause est le principal facteur de lenteur (le coût est dans les tokens
# *générés*, pas dans le texte d'entrée). On plafonne donc la sortie.
llm = OllamaLLM(
    model="mistral",
    temperature=0,
    num_predict=2048,
    base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
)

EXTRACTION_PROMPT = PromptTemplate.from_template("""
Tu es un expert juridique spécialisé dans l'analyse de contrats commerciaux.

Analyse le contrat ci-dessous et extrait TOUTES les clauses importantes.
Pour chaque clause, retourne un objet JSON avec les champs suivants :
- "id" : identifiant unique de la clause (ex: "C001", "C002"...)
- "type" : type de clause parmi : Confidentialité, Paiement, Résiliation,
  Responsabilité, Livraison, Propriété intellectuelle, Durée, Juridiction, Autre
- "titre" : titre court de la clause (5 mots max)
- "texte" : court extrait représentatif de la clause (200 caractères maximum,
  pas la clause entière)
- "criticite" : niveau de criticité parmi : HIGH, MEDIUM, LOW

Retourne UNIQUEMENT un JSON valide de la forme :
{{"clauses": [liste des clauses]}}

Ne retourne rien d'autre que le JSON. Pas d'explication, pas de markdown.

CONTRAT :
{contract_text}
""")


def extract_clauses(contract_text: str) -> list[dict]:
    """
    Extrait les clauses d'un contrat via Mistral local.
    Retourne une liste de dicts avec id, type, titre, texte, criticite.
    """
    # Tronquer si le contrat est trop long (fenêtre de contexte Mistral).
    # Une entrée plus courte réduit aussi le nombre de clauses détectées,
    # donc le volume de sortie à générer - le vrai facteur de lenteur ici.
    max_chars = 6000
    if len(contract_text) > max_chars:
        contract_text = contract_text[:max_chars] + "\n\n[...document tronqué...]"

    chain = EXTRACTION_PROMPT | llm
    raw_response = chain.invoke({"contract_text": contract_text})

    # Nettoyage de la réponse (Mistral peut ajouter des backticks)
    clean = raw_response.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    clean = clean.strip()

    try:
        data = json.loads(clean)
        return data.get("clauses", [])
    except json.JSONDecodeError as e:
        # Mistral peut retourner du texte avant/après le JSON : on cherche
        # le premier { et le dernier } et on retente le parsing.
        start = raw_response.find("{")
        end = raw_response.rfind("}") + 1
        if start != -1 and end > start:
            candidate = raw_response[start:end]
            try:
                data = json.loads(candidate)
                return data.get("clauses", [])
            except json.JSONDecodeError:
                pass
            # Dernier recours : le JSON est structurellement corrompu
            # (guillemets non échappés dans le texte des clauses, virgules
            # manquantes...). On tente une réparation automatique.
            try:
                data = json.loads(repair_json(candidate))
                return data.get("clauses", [])
            except (json.JSONDecodeError, ValueError):
                pass
        print(f"Erreur parsing JSON : {e}")
        print(f"Réponse brute : {raw_response[:500]}")
        return []
