import streamlit as st
from src.parser import extract_text_from_bytes
from src.extractor import extract_clauses
from src.comparator import align_clauses
from src.reporter import generate_pdf_report

# ── Configuration de la page ─────────────────────────────────────────
st.set_page_config(
    page_title="ContractScan — Thales",
    page_icon="⚖️",
    layout="wide"
)

# ── CSS personnalisé ─────────────────────────────────────────────────
st.markdown("""
<style>
.main-title {
    font-size: 28px; font-weight: 700;
    color: #0C447C; border-bottom: 3px solid #185FA5;
    padding-bottom: 8px; margin-bottom: 20px;
}
.status-conforme  { background: #EAF3DE; padding: 4px 10px; border-radius: 12px; color: #3B6D11; font-weight: 600; }
.status-averifier { background: #FAEEDA; padding: 4px 10px; border-radius: 12px; color: #854F0B; font-weight: 600; }
.status-critique  { background: #FCEBEB; padding: 4px 10px; border-radius: 12px; color: #A32D2D; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────
st.markdown('<div class="main-title">⚖️ ContractScan — Comparaison automatique de clauses</div>',
            unsafe_allow_html=True)
st.caption("POC de comparaison contractuelle avec Human-in-the-Loop · Déploiement local sécurisé")

# ── Upload des contrats ──────────────────────────────────────────────
st.subheader("1. Charger les deux contrats")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Template Thales**")
    thales_file = st.file_uploader(
        "Template de référence Thales",
        type=["pdf", "docx"],
        key="thales"
    )

with col2:
    st.markdown("**Template Fournisseur**")
    supplier_file = st.file_uploader(
        "Template imposé par le fournisseur",
        type=["pdf", "docx"],
        key="supplier"
    )

# ── Analyse ──────────────────────────────────────────────────────────
if thales_file and supplier_file:
    if st.button("🔍 Analyser les contrats", type="primary"):

        with st.spinner("Extraction du texte..."):
            thales_text = extract_text_from_bytes(thales_file.read(), thales_file.name)
            supplier_text = extract_text_from_bytes(supplier_file.read(), supplier_file.name)

        with st.spinner("Extraction des clauses via Mistral (peut prendre 30-60 sec)..."):
            thales_clauses = extract_clauses(thales_text)
            supplier_clauses = extract_clauses(supplier_text)

        with st.spinner("Comparaison et scoring des clauses..."):
            results = align_clauses(thales_clauses, supplier_clauses)

        st.session_state["results"] = results
        st.success(f"✅ {len(results)} clauses analysées")

# ── Résultats et Human-in-the-Loop ───────────────────────────────────
if "results" in st.session_state:
    results = st.session_state["results"]

    # Métriques de synthèse
    st.subheader("2. Synthèse de l'analyse")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total clauses", len(results))
    col2.metric("Conformes",
                sum(1 for r in results if r["status"] == "CONFORME"))
    col3.metric("À vérifier",
                sum(1 for r in results if r["status"] == "A_VERIFIER"))
    col4.metric("Critiques",
                sum(1 for r in results if r["status"] == "CRITIQUE"))

    # Filtre par statut
    st.subheader("3. Revue et décision par clause (Human-in-the-Loop)")
    filter_status = st.radio(
        "Filtrer par statut",
        ["Tous", "CRITIQUE", "A_VERIFIER", "CONFORME"],
        horizontal=True
    )

    filtered = results if filter_status == "Tous" else [
        r for r in results if r["status"] == filter_status
    ]

    # Affichage clause par clause
    for clause in filtered:
        status = clause["status"]
        icon = {"CONFORME": "🟢", "A_VERIFIER": "🟡", "CRITIQUE": "🔴"}.get(status, "⚪")
        score_pct = int(clause["similarity_score"] * 100)

        with st.expander(
            f"{icon} {clause['id']} — {clause['type']} "
            f"| Score : {score_pct}% | Criticité : {clause['criticite']}"
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**📄 Clause Thales**")
                st.info(clause["thales_text"][:500])

            with col2:
                st.markdown("**📄 Clause Fournisseur**")
                st.info(clause["supplier_text"][:500])

            if clause.get("divergence"):
                st.warning(f"⚠️ **Divergence détectée :** {clause['divergence']}")

            # Décision Human-in-the-Loop
            col_dec, col_com = st.columns([1, 2])
            with col_dec:
                decision = st.radio(
                    "Décision",
                    ["Accepter", "Rejeter", "À négocier"],
                    key=f"dec_{clause['id']}",
                    index=0
                )
                clause["decision"] = decision

            with col_com:
                comment = st.text_area(
                    "Commentaire",
                    key=f"com_{clause['id']}",
                    height=80,
                    placeholder="Notes juridiques, points à négocier..."
                )
                clause["commentaire"] = comment

    # Export rapport PDF
    st.subheader("4. Exporter le rapport")
    if st.button("📥 Générer le rapport PDF", type="primary"):
        output_path = generate_pdf_report(
            results,
            output_path="rapport_comparaison.pdf"
        )
        with open(output_path, "rb") as f:
            st.download_button(
                label="⬇️ Télécharger le rapport PDF",
                data=f.read(),
                file_name="rapport_comparaison_contractuelle.pdf",
                mime="application/pdf"
            )
        st.success("Rapport généré avec succès.")

else:
    st.info("⬆️ Chargez les deux contrats pour démarrer l'analyse.")
