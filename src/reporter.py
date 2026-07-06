from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime

# Police coeur Helvetica = encodage latin-1 uniquement. Le texte des contrats
# (issu de PDF réels) contient souvent des caractères typographiques
# (guillemets courbes, tirets longs...) hors de ce jeu de caractères.
_UNICODE_REPLACEMENTS = {
    "‘": "'", "’": "'",   # guillemets simples courbes
    "“": '"', "”": '"',   # guillemets doubles courbes
    "–": "-", "—": "-",   # tirets demi/em
    "…": "...",                # points de suspension
    "•": "-",                  # puce
    " ": " ",                   # espace insécable
}


def _safe_text(text: str) -> str:
    """Rend un texte compatible avec la police coeur latin-1 de FPDF."""
    if not text:
        return text
    for char, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class ContractReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(24, 95, 165)   # Bleu Thales
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, "ContractScan - Rapport de comparaison contractuelle",
                  align="C", fill=True, ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()} | Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                  align="C")


STATUS_COLORS = {
    "CONFORME":   (234, 243, 222),   # Vert clair
    "A_VERIFIER": (250, 238, 218),   # Jaune clair
    "CRITIQUE":   (252, 235, 235),   # Rouge clair
}

STATUS_LABELS = {
    "CONFORME":   "[OK] Conforme",
    "A_VERIFIER": "[!] A verifier",
    "CRITIQUE":   "[X] Critique",
}

DECISION_COLORS = {
    "Accepter":    (234, 243, 222),
    "Rejeter":     (252, 235, 235),
    "À négocier":  (250, 238, 218),
}


def generate_pdf_report(
    results: list[dict],
    output_path: str = "rapport_comparaison.pdf"
) -> str:
    """
    Génère un rapport PDF avec :
    - Résumé exécutif (compteurs par statut)
    - Tableau détaillé clause par clause
    - Décisions et commentaires du juriste
    """
    pdf = ContractReport()
    pdf.add_page()

    # ── Résumé exécutif ──────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Résumé exécutif", ln=True)
    pdf.set_font("Helvetica", size=10)

    total = len(results)
    conformes = sum(1 for r in results if r["status"] == "CONFORME")
    a_verifier = sum(1 for r in results if r["status"] == "A_VERIFIER")
    critiques = sum(1 for r in results if r["status"] == "CRITIQUE")

    pdf.set_fill_color(*STATUS_COLORS["CONFORME"])
    pdf.cell(60, 7, f"  Conformes : {conformes}/{total}", fill=True, ln=False, border=1)
    pdf.set_fill_color(*STATUS_COLORS["A_VERIFIER"])
    pdf.cell(60, 7, f"  À vérifier : {a_verifier}/{total}", fill=True, ln=False, border=1)
    pdf.set_fill_color(*STATUS_COLORS["CRITIQUE"])
    pdf.cell(60, 7, f"  Critiques : {critiques}/{total}", fill=True, ln=True, border=1)
    pdf.ln(4)

    # ── Tableau détaillé ─────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Détail des clauses", ln=True)

    for clause in results:
        status = clause.get("status", "A_VERIFIER")
        decision = clause.get("decision", "Non traité")
        color = STATUS_COLORS.get(status, (240, 240, 240))
        dec_color = DECISION_COLORS.get(decision, (240, 240, 240))

        clause_id = _safe_text(str(clause.get("id", "")))
        clause_type = _safe_text(str(clause.get("type", "")))
        thales_text = _safe_text(clause.get("thales_text", ""))
        supplier_text = _safe_text(clause.get("supplier_text", ""))
        divergence = _safe_text(clause.get("divergence", ""))
        commentaire = _safe_text(clause.get("commentaire", ""))
        decision_safe = _safe_text(decision)

        # En-tête de clause
        pdf.set_fill_color(*color)
        pdf.set_font("Helvetica", "B", 10)
        label = STATUS_LABELS.get(status, status)
        pdf.cell(0, 7,
                 f"  {clause_id} - {clause_type} | {label} | Score : {clause['similarity_score']}",
                 fill=True, border=1, ln=True)

        # Texte Thales
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, "  Template Thales :", ln=True)
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(0, 5,
                       f"  {thales_text[:300]}",
                       border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Texte Fournisseur
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, "  Template Fournisseur :", ln=True)
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(0, 5,
                       f"  {supplier_text[:300]}",
                       border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Divergence détectée
        if divergence:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(130, 60, 0)
            pdf.multi_cell(0, 5,
                           f"  Divergence : {divergence}",
                           border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)

        # Décision du juriste
        pdf.set_fill_color(*dec_color)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6,
                 f"  Décision juriste : {decision_safe}",
                 fill=True, border=1, ln=True)

        # Commentaire
        if commentaire:
            pdf.set_font("Helvetica", "I", 9)
            pdf.multi_cell(0, 5,
                           f"  Commentaire : {commentaire}",
                           border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(2)

    pdf.output(output_path)
    return output_path
