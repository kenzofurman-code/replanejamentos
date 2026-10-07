from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, Any

from ..services import versions as vstore
from .replan import SCHEDULE_VERSIONS

router = APIRouter(prefix="/api/versions", tags=["Versions"])


def _check_domain(domain: str):
    if domain not in vstore.DOMAINS:
        raise HTTPException(status_code=404, detail=f"Tela desconhecida: {domain}")


@router.get("/{project_id}")
def list_versions(project_id: str):
    """Versões de cada tela, a versão ativa e as edições salvas nela."""
    return vstore.summary(project_id, SCHEDULE_VERSIONS.get(project_id, []))


@router.post("/{project_id}/{domain}/import")
async def import_version(project_id: str, domain: str, version_name: str = Form(""), file: UploadFile = File(...)):
    """Importa a planilha do modelo separado da tela como nova versão (e a torna ativa)."""
    _check_domain(domain)
    if domain == "cronograma":
        raise HTTPException(status_code=400, detail="Use /api/replan/import-schedule para o cronograma.")
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Envie a planilha no formato .xlsx do modelo desta tela.")
    try:
        vid = vstore.add_version(project_id, domain, version_name.strip() or file.filename, await file.read())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Planilha fora do modelo: {e}")
    return {"status": "success", "version_id": vid}


class ActivateRequest(BaseModel):
    version_id: str


@router.post("/{project_id}/{domain}/activate")
def activate_version(project_id: str, domain: str, req: ActivateRequest):
    _check_domain(domain)
    known = [v["id"] for v in SCHEDULE_VERSIONS.get(project_id, [])] if domain == "cronograma" else None
    try:
        vstore.set_active(project_id, domain, req.version_id, known)
    except KeyError:
        raise HTTPException(status_code=404, detail="Versão não encontrada.")
    return {"status": "success", "active": req.version_id}


class EditsRequest(BaseModel):
    edits: Dict[str, Any]


@router.put("/{project_id}/{domain}/edits")
def save_edits(project_id: str, domain: str, req: EditsRequest):
    """Grava as edições feitas na tela na versão ativa."""
    _check_domain(domain)
    vstore.save_edits(project_id, domain, req.edits)
    return {"status": "success"}


@router.delete("/{project_id}/{domain}/edits")
def restore_version(project_id: str, domain: str):
    """Descarta as edições da versão ativa (volta ao que veio na importação)."""
    _check_domain(domain)
    vstore.save_edits(project_id, domain, {})
    return {"status": "reset"}
