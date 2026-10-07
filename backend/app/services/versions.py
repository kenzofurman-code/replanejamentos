"""
Versões por tela (orçamento, cronograma, distribuição, medição).

Cada obra tem backend/data/versions/<project_id>/index.json:
    {
      "<domain>": {
        "active": "atual" | "<version_id>",
        "versions": [{"id", "name", "created_at", "file"}],   # importadas (não inclui "atual")
        "edits": {"<version_id>": {...}}                       # edições feitas na tela, por versão
      }
    }
"atual" = planilha da própria obra (backend/data/projects/<id>/<domain>.xlsx).
As versões importadas de orçamento/distribuição/medição guardam a planilha em <domain>_<version_id>.xlsx.
As versões do cronograma continuam em schedule_versions.pkl (aceitam MPP/XML); aqui ficam só a ativa e as edições.
Edições gravam sempre na versão ativa; "restaurar" apaga as edições e volta ao que veio na importação.
"""
import os
import json
import copy
import datetime
from typing import Dict, Any, Optional

from .split_io import _read_orcamento, _read_distribuicao, _read_medicao

DOMAINS = ("orcamento", "cronograma", "distribuicao", "medicao")
ATUAL = "atual"
ATUAL_NAME = "Revisão Atual (Arquivo)"

VERSIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "versions"))
LEGACY_LINKS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "custom_links.pkl"))


def _dir(project_id: str) -> str:
    return os.path.join(VERSIONS_DIR, project_id)


def _index_path(project_id: str) -> str:
    return os.path.join(_dir(project_id), "index.json")


def _empty_domain() -> Dict[str, Any]:
    return {"active": ATUAL, "versions": [], "edits": {}}


def load_index(project_id: str) -> Dict[str, Any]:
    path = _index_path(project_id)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            idx = json.load(f)
    else:
        idx = {}
        # Migra vínculos editados antes das versões (custom_links.pkl) para a revisão atual
        if os.path.exists(LEGACY_LINKS_FILE):
            import pickle
            try:
                with open(LEGACY_LINKS_FILE, "rb") as f:
                    legacy = pickle.load(f)
                if legacy.get(project_id):
                    idx["distribuicao"] = _empty_domain()
                    idx["distribuicao"]["edits"][ATUAL] = {"links_by_l5": legacy[project_id]}
            except Exception as e:
                print(f"Aviso: custom_links.pkl não pôde ser migrado: {e}")
    for d in DOMAINS:
        idx.setdefault(d, _empty_domain())
    return idx


def save_index(project_id: str, idx: Dict[str, Any]):
    os.makedirs(_dir(project_id), exist_ok=True)
    tmp = _index_path(project_id) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, default=str)
    os.replace(tmp, _index_path(project_id))


def version_file(project_id: str, domain: str, version_id: str) -> str:
    return os.path.join(_dir(project_id), f"{domain}_{version_id}.xlsx")


def validate_version_file(domain: str, path: str):
    """Lê a planilha para garantir que está no formato do modelo separado (levanta ValueError se não)."""
    if domain == "orcamento":
        _read_orcamento(path)
    elif domain == "distribuicao":
        _read_distribuicao(path)
    elif domain == "medicao":
        import openpyxl
        from .excel_reader import norm
        wb = openpyxl.load_workbook(path, read_only=True)
        names = {norm(s) for s in wb.sheetnames}
        wb.close()
        if not names & {"corte", "historico", "itens", "acumulado"}:
            raise ValueError("abas esperadas: Corte, Historico, Itens, Acumulado")
        _read_medicao(path, 0.0)
    else:
        raise ValueError(f"Tela sem versões por planilha: {domain}")


def add_version(project_id: str, domain: str, name: str, content: bytes) -> str:
    idx = load_index(project_id)
    version_id = f"v_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    path = version_file(project_id, domain, version_id)
    os.makedirs(_dir(project_id), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)
    try:
        validate_version_file(domain, path)
    except Exception:
        os.remove(path)
        raise
    idx[domain]["versions"].append({
        "id": version_id,
        "name": name,
        "created_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "file": os.path.basename(path),
    })
    idx[domain]["active"] = version_id
    save_index(project_id, idx)
    return version_id


def set_active(project_id: str, domain: str, version_id: str, known_ids=None):
    idx = load_index(project_id)
    ids = {ATUAL} | {v["id"] for v in idx[domain]["versions"]} | set(known_ids or [])
    if version_id not in ids:
        raise KeyError(version_id)
    idx[domain]["active"] = version_id
    save_index(project_id, idx)


def get_active(project_id: str, domain: str) -> str:
    return load_index(project_id)[domain]["active"]


def get_edits(project_id: str, domain: str, version_id: Optional[str] = None) -> Dict[str, Any]:
    idx = load_index(project_id)
    vid = version_id or idx[domain]["active"]
    return idx[domain]["edits"].get(vid) or {}


def save_edits(project_id: str, domain: str, edits: Dict[str, Any]):
    idx = load_index(project_id)
    vid = idx[domain]["active"]
    if edits:
        idx[domain]["edits"][vid] = edits
    else:
        idx[domain]["edits"].pop(vid, None)
    save_index(project_id, idx)


def summary(project_id: str, cronograma_versions=None) -> Dict[str, Any]:
    """Visão para a interface: versões de cada tela, qual está ativa e as edições da ativa."""
    idx = load_index(project_id)
    out = {}
    for d in DOMAINS:
        info = idx[d]
        imported = cronograma_versions if d == "cronograma" else info["versions"]
        versions = [{"id": ATUAL, "name": ATUAL_NAME}] + [
            {"id": v["id"], "name": v["name"], "created_at": v.get("created_at") or v.get("upload_time")}
            for v in (imported or [])
        ]
        for v in versions:
            v["has_edits"] = bool(info["edits"].get(v["id"]))
        out[d] = {"active": info["active"], "versions": versions, "edits": info["edits"].get(info["active"]) or {}}
    return out


def apply_active_versions(project_id: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Troca as partes do projeto cuja versão ativa não é a 'atual' pelos dados da versão importada."""
    idx = load_index(project_id)
    active = {d: idx[d]["active"] for d in ("orcamento", "distribuicao", "medicao")}
    if all(v == ATUAL for v in active.values()):
        return parsed

    result = dict(parsed)
    if active["orcamento"] != ATUAL:
        name, total, items, meas = _read_orcamento(version_file(project_id, "orcamento", active["orcamento"]))
        result.update(project_name=name, total_budget=total, budget_items=items,
                      history_monthly=[dict(h, value=h["pct"] * total) for h in parsed.get("history_monthly", [])])
        if active["medicao"] == ATUAL and not parsed.get("item_monthly_measurements"):
            result["item_measurements"] = meas
    if active["distribuicao"] != ATUAL:
        links_by_l5, all_links = _read_distribuicao(version_file(project_id, "distribuicao", active["distribuicao"]))
        result.update(links_by_l5=links_by_l5, all_links=all_links)
    if active["medicao"] != ATUAL:
        cutoff_n, cutoff_d, monthly, acum, history = _read_medicao(
            version_file(project_id, "medicao", active["medicao"]), result["total_budget"])
        result["budget_items"] = copy.deepcopy(result["budget_items"])
        for code, v in acum.items():
            if code in result["budget_items"]:
                result["budget_items"][code]["accum_measured_pct"] = v
        result.update(cutoff_med_num=cutoff_n, cutoff_date=cutoff_d, item_monthly_measurements=monthly,
                      item_measurements=acum, history_monthly=history)
        if history:
            result["start_date"] = datetime.date.fromisoformat(history[0]["date"])
    return result
