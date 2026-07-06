import json
import os
import torch  # noqa: F401  (pré-import requis avant sentence_transformers sous Windows, sinon échec de chargement des DLL torch)
from json_repair import repair_json
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

# Modèle d'embeddings local — aucun appel réseau
embedder = SentenceTransformer("all-MiniLM-L6-v2")
llm = OllamaLLM(
    model="mistral",
    temperature=0,
    num_predict=1024,
    base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
)

DIVERGENCE_PROMPT = PromptTemplate.from_template("""
Tu es un expert juridique. Compare ces deux clauses de contrats et
décris la divergence principale en 1 phrase courte et précise.
Sois factuel, pas d'opinion.

Clause Thales : {thales_text}
Clause Fournisseur : {supplier_text}

Divergence :
""")

# Regrouper les descriptions de divergence en un seul appel Mistral (au lieu
# d'un appel par clause) réduit fortement le temps total d'analyse : chaque
# appel LLM a un coût fixe non négligeable, et un contrat peut compter une
# quinzaine de clauses à comparer.
DIVERGENCE_BATCH_PROMPT = PromptTemplate.from_template("""
Tu es un expert juridique. Pour chaque paire de clauses ci-dessous,
décris la divergence principale en 1 phrase courte et factuelle.

{pairs_block}

Retourne UNIQUEMENT un JSON valide de la forme :
{{"divergences": {{"<id>": "<description>", ...}}}}
Une entrée par id. Ne retourne rien d'autre que le JSON.
""")

# Nombre de paires traitées par appel LLM. Mistral a une fenêtre de contexte
# limitée (4096 tokens) : un lot trop grand tronquerait le prompt.
_BATCH_SIZE = 5
_BATCH_CLAUSE_MAX_CHARS = 300


def _chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def describe_divergences_batch(pairs: list[dict]) -> dict[str, str]:
    """
    Génère les descriptions de divergence pour plusieurs paires de clauses
    en un minimum d'appels Mistral (par lots de _BATCH_SIZE).
    `pairs` : liste de {"id", "thales_text", "supplier_text"}.
    Retourne un dict {id: description}.
    """
    descriptions: dict[str, str] = {}
    chain = DIVERGENCE_BATCH_PROMPT | llm

    for batch in _chunked(pairs, _BATCH_SIZE):
        pairs_block = "\n\n".join(
            f"[{p['id']}]\n"
            f"Clause Thales : {p['thales_text'][:_BATCH_CLAUSE_MAX_CHARS]}\n"
            f"Clause Fournisseur : {p['supplier_text'][:_BATCH_CLAUSE_MAX_CHARS]}"
            for p in batch
        )
        raw_response = chain.invoke({"pairs_block": pairs_block})

        clean = raw_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            try:
                data = json.loads(repair_json(clean))
            except (json.JSONDecodeError, ValueError):
                data = {}

        batch_divergences = data.get("divergences", {}) if isinstance(data, dict) else {}
        for p in batch:
            desc = batch_divergences.get(p["id"], "")
            if desc:
                descriptions[p["id"]] = desc
            else:
                # Repli si le lot entier ou cette entrée a échoué : un appel
                # individuel classique, plus lent mais fiable.
                descriptions[p["id"]] = describe_divergence(
                    p["thales_text"], p["supplier_text"]
                )

    return descriptions


def compute_similarity(text1: str, text2: str) -> float:
    """Calcule la similarité cosinus entre deux textes via embeddings."""
    embeddings = embedder.encode([text1, text2])
    score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    return round(float(score), 3)


def get_status(similarity: float) -> str:
    """Détermine le statut selon le score de similarité."""
    if similarity >= 0.85:
        return "CONFORME"      # Clauses quasi-identiques
    elif similarity >= 0.60:
        return "A_VERIFIER"    # Divergence mineure
    else:
        return "CRITIQUE"      # Divergence majeure


def describe_divergence(thales_text: str, supplier_text: str) -> str:
    """Génère une description de la divergence via Mistral."""
    chain = DIVERGENCE_PROMPT | llm
    return chain.invoke({
        "thales_text": thales_text[:800],
        "supplier_text": supplier_text[:800]
    }).strip()


def align_clauses(
    thales_clauses: list[dict],
    supplier_clauses: list[dict]
) -> list[dict]:
    """
    Aligne les clauses par type entre les deux contrats.
    Pour chaque type présent dans Thales, cherche la clause
    correspondante chez le fournisseur.
    Retourne une liste de paires avec score et divergence.
    """
    results = []

    # Index des clauses fournisseur par type
    supplier_index = {}
    for clause in supplier_clauses:
        ctype = clause.get("type", "Autre")
        if ctype not in supplier_index:
            supplier_index[ctype] = []
        supplier_index[ctype].append(clause)

    for i, thales_clause in enumerate(thales_clauses):
        ctype = thales_clause.get("type", "Autre")
        thales_text = thales_clause.get("texte", "")

        # Chercher la meilleure clause fournisseur du même type
        best_match = None
        best_score = 0.0

        candidates = supplier_index.get(ctype, supplier_clauses[:3])
        for supplier_clause in candidates:
            supplier_text = supplier_clause.get("texte", "")
            score = compute_similarity(thales_text, supplier_text)
            if score > best_score:
                best_score = score
                best_match = supplier_clause

        status = get_status(best_score)

        results.append({
            "id": f"CMP_{i+1:03d}",
            "type": ctype,
            "titre": thales_clause.get("titre", ctype),
            "criticite": thales_clause.get("criticite", "MEDIUM"),
            "thales_text": thales_text,
            "supplier_text": best_match.get("texte", "Clause absente") if best_match else "Clause absente",
            "similarity_score": best_score,
            "status": status,
            "divergence": "",
            "decision": None,        # Rempli par l'utilisateur
            "commentaire": ""        # Rempli par l'utilisateur
        })

    # Une seule (ou quelques) passe(s) Mistral pour toutes les divergences,
    # au lieu d'un appel LLM par clause A_VERIFIER/CRITIQUE.
    pairs_needing_divergence = [
        {"id": r["id"], "thales_text": r["thales_text"], "supplier_text": r["supplier_text"]}
        for r in results
        if r["status"] in ["A_VERIFIER", "CRITIQUE"] and r["supplier_text"] != "Clause absente"
    ]
    if pairs_needing_divergence:
        divergences = describe_divergences_batch(pairs_needing_divergence)
        for r in results:
            if r["id"] in divergences:
                r["divergence"] = divergences[r["id"]]

    return results
