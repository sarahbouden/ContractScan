import os, base64, io
from datasets import load_dataset

os.makedirs("data/contracts/pdf", exist_ok=True)

dataset = load_dataset("dvgodoy/CUAD_v1_Contract_Understanding_PDF", split="train")

# Télécharger les 10 premiers contrats pour les tests
for i, sample in enumerate(dataset.select(range(10))):
    pdf_bytes = base64.b64decode(sample["pdf_bytes_base64"])
    filename = f"data/contracts/pdf/contract_{i+1:03d}.pdf"
    with open(filename, "wb") as f:
        f.write(pdf_bytes)
    print(f"Téléchargé : {filename}")

print("10 contrats PDF téléchargés.")
