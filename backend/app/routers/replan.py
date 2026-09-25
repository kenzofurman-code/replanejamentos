import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from ..services.replan_engine import run_replan_calculation
from ..services.excel_reader import parse_excel_project
from ..services.exporter import export_replan_to_excel
from ..services.schedule_importer import parse_ms_project_xml, parse_schedule_excel_tab, parse_ms_project_mpp, get_group_leaf_tasks, try_float
from ..services.piemonte_scanner import scan_piemonte_projects
from .projects import PROJECT_CACHE

router = APIRouter(prefix="/api/replan", tags=["Replan"])

import pickle
import os

VERSIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "schedule_versions.pkl")
CUSTOM_LINKS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "custom_links.pkl")

def _load_versions() -> Dict[str, List[Dict[str, Any]]]:
    try:
        if os.path.exists(VERSIONS_FILE):
            with open(VERSIONS_FILE, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Erro ao carregar schedule_versions: {e}")
    return {}

def _save_versions(versions: Dict[str, List[Dict[str, Any]]]):
    try:
        os.makedirs(os.path.dirname(VERSIONS_FILE), exist_ok=True)
        with open(VERSIONS_FILE, "wb") as f:
            pickle.dump(versions, f)
    except Exception as e:
        print(f"Erro ao salvar schedule_versions: {e}")

SCHEDULE_VERSIONS: Dict[str, List[Dict[str, Any]]] = _load_versions()

def _load_custom_links() -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    try:
        if os.path.exists(CUSTOM_LINKS_FILE):
            with open(CUSTOM_LINKS_FILE, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Erro ao carregar custom_links: {e}")
    return {}

def _save_custom_links(links_data: Dict[str, Dict[str, List[Dict[str, Any]]]]):
    try:
        os.makedirs(os.path.dirname(CUSTOM_LINKS_FILE), exist_ok=True)
        with open(CUSTOM_LINKS_FILE, "wb") as f:
            pickle.dump(links_data, f)
    except Exception as e:
        print(f"Erro ao salvar custom_links: {e}")

class ReplanRequest(BaseModel):
    project_id: str
    file_path: Optional[str] = None
    cycle_start_day: int = 21
    cycle_end_day: int = 20
    cutoff_med_num: Optional[int] = None
    version_id: Optional[str] = None
    custom_measurements: Optional[Dict[str, float]] = None
    custom_measurements_l5: Optional[Dict[str, float]] = None
    custom_measurements_l6: Optional[Dict[str, Dict[str, float]]] = None
    custom_monthly_medicao: Optional[Dict[str, Dict[str, float]]] = None
    custom_monthly_medicao_l6: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None
    custom_weights: Optional[Dict[str, float]] = None
    custom_schedule_overrides: Optional[Dict[str, Any]] = None
    custom_links_by_l5: Optional[Dict[str, List[Dict[str, Any]]]] = None
    export_target: Optional[str] = "current"
    active_tab: Optional[str] = "ff_replanejado"
    dist_view_mode: Optional[str] = "val"
    ff_rep_view_mode: Optional[str] = "val"
    ff_view_mode: Optional[str] = "val"

@router.post("/simulate")
def simulate_replan(req: ReplanRequest):
    """
    Executes a high-speed replan simulation returning data for all 7 application tabs.
    """
    if req.project_id in PROJECT_CACHE:
        parsed = PROJECT_CACHE[req.project_id]["data"]
    elif req.file_path:
        parsed = parse_excel_project(req.file_path)
        PROJECT_CACHE[req.project_id] = {
            "file_path": req.file_path,
            "data": parsed
        }
    else:
        # Automatically resolve project file from scan_piemonte_projects
        projs = scan_piemonte_projects()
        found = next((p for p in projs if p["id"] == req.project_id), None)
        if found and found.get("latest_file"):
            fpath = found["latest_file"]["path"]
            parsed = parse_excel_project(fpath)
            PROJECT_CACHE[req.project_id] = {
                "file_path": fpath,
                "data": parsed
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail="Projeto não carregado. Por favor, carregue o projeto primeiro."
            )

    # Check if a custom schedule version was selected
    schedule_override = None
    if req.version_id and req.version_id != "atual" and req.project_id in SCHEDULE_VERSIONS:
        found_v = next((v for v in SCHEDULE_VERSIONS[req.project_id] if v["id"] == req.version_id), None)
        if found_v:
            schedule_override = found_v["tasks"]

    custom_links = req.custom_links_by_l5
    saved_links = _load_custom_links()
    if custom_links is None and req.project_id in saved_links:
        custom_links = saved_links[req.project_id]

    try:
        result = run_replan_calculation(
            parsed_data=parsed,
            cycle_start_day=req.cycle_start_day,
            cycle_end_day=req.cycle_end_day,
            cutoff_med_num=req.cutoff_med_num,
            custom_measurements=req.custom_measurements,
            custom_measurements_l5=req.custom_measurements_l5,
            custom_measurements_l6=req.custom_measurements_l6,
            custom_monthly_medicao=req.custom_monthly_medicao,
            custom_monthly_medicao_l6=req.custom_monthly_medicao_l6,
            custom_weights=req.custom_weights,
            schedule_tasks_override=schedule_override,
            custom_schedule_overrides=req.custom_schedule_overrides,
            custom_links_by_l5=custom_links
        )
        
        # Inject custom schedule versions into tab_cronograma
        is_atual_active = (not req.version_id or req.version_id == "atual")
        result["tab_cronograma"]["versions"] = [
            {"id": "atual", "name": "Revisão Atual (Arquivo)", "active": is_atual_active}
        ]
        if req.project_id in SCHEDULE_VERSIONS:
            for v in SCHEDULE_VERSIONS[req.project_id]:
                result["tab_cronograma"]["versions"].append({
                    "id": v["id"],
                    "name": v["name"],
                    "active": (req.version_id == v["id"])
                })

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no cálculo de replanejamento: {str(e)}")

@router.post("/import-schedule")
async def import_schedule(
    project_id: str = Form(...),
    version_name: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Upload an MS Project (.mpp, .xml) or Excel (.xlsx) schedule file to create a new version of the schedule.
    """
    content = await file.read()
    filename = file.filename.lower()

    try:
        if filename.endswith(".mpp"):
            parsed_crono = parse_ms_project_mpp(content, filename=file.filename)
        elif filename.endswith(".xml"):
            parsed_crono = parse_ms_project_xml(content)
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            parsed_crono = parse_schedule_excel_tab(content)
        else:
            raise HTTPException(status_code=400, detail="Formato não suportado. Envie um arquivo .mpp (MS Project), .xml ou .xlsx (Excel).")

        version_id = f"v_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if project_id not in SCHEDULE_VERSIONS:
            SCHEDULE_VERSIONS[project_id] = []

        SCHEDULE_VERSIONS[project_id].append({
            "id": version_id,
            "name": version_name or parsed_crono["version_name"],
            "tasks": parsed_crono["tasks"],
            "task_count": len(parsed_crono["tasks"]),
            "created_at": str(datetime.datetime.now())
        })
        _save_versions(SCHEDULE_VERSIONS)

        return {
            "status": "success",
            "version_id": version_id,
            "version_name": version_name or parsed_crono["version_name"],
            "tasks_count": len(parsed_crono["tasks"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao importar cronograma: {str(e)}")

@router.post("/export")
def export_replan(req: ReplanRequest):
    """
    Simulates and exports the replanned curve and WBS tree to a clean Excel spreadsheet.
    """
    if req.project_id in PROJECT_CACHE:
        parsed = PROJECT_CACHE[req.project_id]["data"]
    elif req.file_path:
        parsed = parse_excel_project(req.file_path)
    else:
        raise HTTPException(status_code=400, detail="Projeto não carregado.")

    schedule_override = None
    if req.version_id and req.project_id in SCHEDULE_VERSIONS:
        found_v = next((v for v in SCHEDULE_VERSIONS[req.project_id] if v["id"] == req.version_id), None)
        if found_v:
            schedule_override = found_v["tasks"]

    custom_links = req.custom_links_by_l5
    saved_links = _load_custom_links()
    if custom_links is None and req.project_id in saved_links:
        custom_links = saved_links[req.project_id]

    result = run_replan_calculation(
        parsed_data=parsed,
        cycle_start_day=req.cycle_start_day,
        cycle_end_day=req.cycle_end_day,
        cutoff_med_num=req.cutoff_med_num,
        custom_measurements=req.custom_measurements,
        custom_measurements_l5=req.custom_measurements_l5,
        custom_measurements_l6=req.custom_measurements_l6,
        custom_monthly_medicao=req.custom_monthly_medicao,
        custom_monthly_medicao_l6=req.custom_monthly_medicao_l6,
        custom_weights=req.custom_weights,
        schedule_tasks_override=schedule_override,
        custom_schedule_overrides=req.custom_schedule_overrides,
        custom_links_by_l5=custom_links
    )

    excel_io, filename = export_replan_to_excel(
        replan_result=result,
        export_target=req.export_target or "current",
        active_tab=req.active_tab or "ff_replanejado",
        dist_view_mode=req.dist_view_mode or "val",
        ff_rep_view_mode=req.ff_rep_view_mode or "val",
        ff_view_mode=req.ff_view_mode or "val"
    )

    return StreamingResponse(
        excel_io,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

class SaveLinksRequest(BaseModel):
    project_id: str
    links_by_l5: Dict[str, List[Dict[str, Any]]]

@router.post("/save-links")
def save_links(req: SaveLinksRequest):
    """
    Persists custom distribution links for a project.
    """
    all_links = _load_custom_links()
    all_links[req.project_id] = req.links_by_l5
    _save_custom_links(all_links)
    return {"status": "success", "saved_count": len(req.links_by_l5)}

class ResetLinksRequest(BaseModel):
    project_id: str

@router.post("/reset-links")
def reset_links(req: ResetLinksRequest):
    """
    Resets custom distribution links back to original imported baseline.
    """
    all_links = _load_custom_links()
    if req.project_id in all_links:
        del all_links[req.project_id]
        _save_custom_links(all_links)
    return {"status": "reset"}

@router.get("/expand-group")
def expand_group(project_id: str, group_id: str, version_id: Optional[str] = None):
    """
    Given a group task ID or name, returns all descendant leaf tasks.
    """
    tasks = None
    if version_id and version_id != "atual" and project_id in SCHEDULE_VERSIONS:
        found_v = next((v for v in SCHEDULE_VERSIONS[project_id] if v["id"] == version_id), None)
        if found_v:
            tasks = found_v["tasks"]
    if not tasks and project_id in PROJECT_CACHE:
        tasks = PROJECT_CACHE[project_id]["data"].get("tasks", {})
    if not tasks:
        projs = scan_piemonte_projects()
        found = next((p for p in projs if p["id"] == project_id), None)
        if found and found.get("latest_file"):
            parsed = parse_excel_project(found["latest_file"]["path"])
            tasks = parsed.get("tasks", {})

    leaves = get_group_leaf_tasks(group_id, tasks or {})
    return {
        "group_id": group_id,
        "leaf_tasks": [
            {
                "id": str(t.get("id")),
                "name": t.get("name"),
                "duration": try_float(t.get("duration"), 0.0),
                "wbs": t.get("wbs") or t.get("outline") or "",
                "start": t.get("start"),
                "finish": t.get("finish")
            }
            for t in leaves
        ]
    }
