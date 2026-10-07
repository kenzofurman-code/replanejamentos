"""Garante que as planilhas separadas geram o mesmo resultado que a planilha original."""
import os
import sys
import glob
import json
import pickle
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.excel_reader import parse_excel_project
from app.services.split_io import write_split_files, parse_split_project
from app.services.replan_engine import run_replan_calculation

TEMPLATE = os.path.join(ROOT, "backend", "data", "templates", "Modelo_Padrao_Replanejamento.xlsx")


def _engine(parsed):
    return json.loads(json.dumps(run_replan_calculation(parsed), default=str, sort_keys=True))


def _roundtrip(parsed):
    with tempfile.TemporaryDirectory() as d:
        write_split_files(parsed, d)
        return parse_split_project(d)


def _diffs(a, b, path="", out=None):
    """Diferenças entre dois resultados; ignora centavos de arredondamento e listas de vínculos vazias."""
    out = [] if out is None else out
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if abs(a - b) > 0.011:
            out.append((path, a, b))
    elif isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            va, vb = a.get(k), b.get(k)
            if va in ([], None) and vb in ([], None):
                continue
            _diffs(va, vb, f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _diffs(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append((path, a, b))
    return out


def _assert_same(original):
    split = _roundtrip(original)
    diffs = _diffs(_engine(original), _engine(split))
    assert not diffs, diffs[:10]


def test_modelo_padrao():
    _assert_same(parse_excel_project(TEMPLATE))


def test_planilhas_legadas_em_cache():
    # Usa o cache já extraído da planilha gigante, sem abrir o .xlsx de 60 MB.
    caches = [p for p in glob.glob(os.path.join(ROOT, "backend", "data", "cache", "*.pkl")) if os.path.getsize(p) > 100_000]
    if not caches:
        return
    for p in caches:
        with open(p, "rb") as f:
            _assert_same(pickle.load(f))
