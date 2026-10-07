"""
Extração ÚNICA de uma planilha Físico-Financeira gigante para planilhas separadas.

Uso (na raiz do repositório):
    python backend/tools/extrair_planilha.py "C:\\caminho\\Planilha.xlsx" "Nome da Obra"

Cria backend/data/projects/<slug>/ com orcamento.xlsx, cronograma.xlsx,
distribuicao.xlsx, medicao.xlsx e project.json. Depois disso o sistema lê
apenas essas planilhas pequenas; a original não precisa mais ser aberta.
"""
import os
import sys
import json
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.excel_reader import parse_excel_project  # noqa: E402
from app.services.split_io import write_split_files  # noqa: E402
from app.services.piemonte_scanner import UPLOADED_PROJECTS_DIR  # noqa: E402
from app.routers.projects import _slugify  # noqa: E402


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, name = sys.argv[1], sys.argv[2]
    parsed = parse_excel_project(src)
    slug = _slugify(name)
    out = os.path.join(UPLOADED_PROJECTS_DIR, slug)
    written = write_split_files(parsed, out)
    with open(os.path.join(out, "project.json"), "w", encoding="utf-8") as f:
        json.dump({"id": slug, "name": name, "created_at": datetime.datetime.now().isoformat(),
                   "format": "split", "extracted_from": os.path.basename(src)}, f, indent=2, ensure_ascii=False)
    print(f"Obra '{name}' -> {out}")
    for w in written:
        print(f"  {w}: {os.path.getsize(os.path.join(out, w)) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
