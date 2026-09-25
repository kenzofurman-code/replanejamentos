import os
import re
import json
import shutil
import unicodedata
import datetime
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from ..services.piemonte_scanner import scan_piemonte_projects, UPLOADED_PROJECTS_DIR
from ..services.excel_reader import parse_excel_project
from ..services.replan_engine import run_replan_calculation
from ..services.template_generator import generate_standard_replan_template
from ..services.schedule_importer import parse_ms_project_xml, parse_schedule_excel_tab, parse_ms_project_mpp

router = APIRouter(prefix="/api/projects", tags=["Projects"])

# In-memory cache for fast interactive replanning
PROJECT_CACHE: Dict[str, Dict[str, Any]] = {}

TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "templates"))
TEMPLATE_FILE = os.path.join(TEMPLATE_DIR, "Modelo_Padrao_Replanejamento.xlsx")

def _slugify(text: str) -> str:
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_').lower()
    return slug or "obra"

@router.get("/template")
def download_template():
    """
    Downloads the official standard Excel template for project import.
    """
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    if not os.path.exists(TEMPLATE_FILE):
        buf = generate_standard_replan_template()
        with open(TEMPLATE_FILE, "wb") as f:
            f.write(buf.getvalue())
            
    return FileResponse(
        TEMPLATE_FILE,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Modelo_Padrao_Replanejamento.xlsx"
    )

@router.get("", response_model=List[Dict[str, Any]])
def list_projects():
    """
    Returns all projects found in uploaded folder and Piemonte directories.
    """
    projs = scan_piemonte_projects()
    return projs

@router.get("/{project_id}")
def get_project(project_id: str):
    """
    Returns project details and its available Excel files.
    """
    projs = scan_piemonte_projects()
    found = next((p for p in projs if p["id"] == project_id), None)
    if not found:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return found

@router.post("/upload")
async def upload_project(
    project_name: str = Form(...),
    file: UploadFile = File(...),
    schedule_file: Optional[UploadFile] = File(None)
):
    """
    Uploads a new project spreadsheet (standard template or legacy format).
    Parses, validates, and initializes the project.
    """
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="O arquivo principal deve ser uma planilha Excel (.xlsx ou .xlsm).")
    
    slug = _slugify(project_name)
    proj_dir = os.path.join(UPLOADED_PROJECTS_DIR, slug)
    os.makedirs(proj_dir, exist_ok=True)
    
    safe_filename = re.sub(r'[^\w\.\-\(\) ]', '_', file.filename)
    dest_path = os.path.join(proj_dir, safe_filename)
    
    try:
        content = await file.read()
        with open(dest_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo no servidor: {str(e)}")
        
    # Test parse the uploaded file to ensure validity
    try:
        parsed = parse_excel_project(dest_path)
    except Exception as e:
        # Cleanup invalid file/folder if newly created
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"Não foi possível processar a planilha. Verifique as colunas do modelo: {str(e)}")

    # Save metadata JSON
    meta = {
        "id": slug,
        "name": project_name.strip(),
        "created_at": datetime.datetime.now().isoformat(),
        "original_filename": file.filename
    }
    with open(os.path.join(proj_dir, "project.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        
    # Handle optional schedule file upload (XML / MPP / XLSX)
    if schedule_file and schedule_file.filename:
        s_name = schedule_file.filename
        s_dest = os.path.join(proj_dir, re.sub(r'[^\w\.\-\(\) ]', '_', s_name))
        s_content = await schedule_file.read()
        with open(s_dest, "wb") as f:
            f.write(s_content)
            
        try:
            from .replan import SCHEDULE_VERSIONS, _save_versions
            tasks_extra = []
            if s_name.endswith(".xml"):
                tasks_extra = parse_ms_project_xml(s_content)
            elif s_name.endswith((".xlsx", ".xlsm")):
                tasks_extra = parse_schedule_excel_tab(s_content)
            elif s_name.endswith(".mpp"):
                tasks_extra = parse_ms_project_mpp(s_content, s_name)
                
            if tasks_extra:
                if slug not in SCHEDULE_VERSIONS:
                    SCHEDULE_VERSIONS[slug] = []
                ver_id = f"upload_{int(datetime.datetime.now().timestamp())}"
                SCHEDULE_VERSIONS[slug].insert(0, {
                    "id": ver_id,
                    "name": s_name,
                    "upload_time": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "tasks_count": len(tasks_extra),
                    "tasks": tasks_extra
                })
                _save_versions(SCHEDULE_VERSIONS)
        except Exception as err:
            print(f"Aviso: cronograma complementar não pôde ser processado: {err}")

    # Prime cache
    PROJECT_CACHE[slug] = {
        "metadata": {
            "id": slug,
            "name": project_name.strip(),
            "folder_name": slug,
            "path": proj_dir,
            "has_ff": True,
            "files": [{
                "filename": safe_filename,
                "path": dest_path,
                "size_mb": round(len(content) / (1024 * 1024), 2),
                "modified_time": os.stat(dest_path).st_mtime
            }],
            "latest_file": {
                "filename": safe_filename,
                "path": dest_path
            }
        },
        "file_path": dest_path,
        "data": parsed
    }
    
    return {
        "status": "success",
        "project_id": slug,
        "project_name": project_name.strip(),
        "total_budget": parsed["total_budget"],
        "budget_items_count": len(parsed["budget_items"]),
        "tasks_count": len(parsed["tasks"]),
        "links_count": len(parsed["all_links"])
    }

@router.delete("/{project_id}")
def delete_project(project_id: str):
    """
    Deletes an uploaded project and its files from the server.
    """
    proj_dir = os.path.join(UPLOADED_PROJECTS_DIR, project_id)
    if not os.path.exists(proj_dir):
        raise HTTPException(status_code=404, detail="Projeto não encontrado para exclusão.")
        
    try:
        shutil.rmtree(proj_dir)
        if project_id in PROJECT_CACHE:
            del PROJECT_CACHE[project_id]
        return {"status": "success", "message": f"Projeto {project_id} excluído com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao excluir projeto: {str(e)}")

@router.post("/{project_id}/load")
def load_project_file(project_id: str, file_path: Optional[str] = None):
    """
    Parses and caches the project spreadsheet in high speed.
    """
    projs = scan_piemonte_projects()
    found = next((p for p in projs if p["id"] == project_id), None)
    if not found:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")

    # Target file
    target_path = file_path
    if not target_path:
        if found["latest_file"]:
            target_path = found["latest_file"]["path"]
        else:
            raise HTTPException(status_code=400, detail="Nenhum arquivo Físico-Financeiro encontrado para esta obra.")

    # Fast cache return if already loaded and file is unchanged
    if project_id in PROJECT_CACHE and PROJECT_CACHE[project_id]["file_path"] == target_path:
        cached = PROJECT_CACHE[project_id]["data"]
        return {
            "status": "success",
            "cached": True,
            "project_name": cached["project_name"],
            "total_budget": cached["total_budget"],
            "start_date": str(cached["start_date"]),
            "end_date": str(cached["end_date"]),
            "cutoff_med_num": cached["cutoff_med_num"],
            "budget_items_count": len(cached["budget_items"]),
            "tasks_count": len(cached["tasks"]),
            "links_count": len(cached["all_links"]),
            "history_count": len(cached["history_monthly"])
        }

    try:
        parsed = parse_excel_project(target_path)
        PROJECT_CACHE[project_id] = {
            "metadata": found,
            "file_path": target_path,
            "data": parsed
        }
        return {
            "status": "success",
            "cached": False,
            "project_name": parsed["project_name"],
            "total_budget": parsed["total_budget"],
            "start_date": str(parsed["start_date"]),
            "end_date": str(parsed["end_date"]),
            "cutoff_med_num": parsed["cutoff_med_num"],
            "budget_items_count": len(parsed["budget_items"]),
            "tasks_count": len(parsed["tasks"]),
            "links_count": len(parsed["all_links"]),
            "history_count": len(parsed["history_monthly"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar planilha: {str(e)}")
