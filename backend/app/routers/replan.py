import io
import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List, Tuple
from ..services.replan_engine import run_replan_calculation
from ..services.excel_reader import parse_excel_project
from ..services.exporter import export_replan_to_excel
from ..services.schedule_importer import parse_ms_project_xml, parse_schedule_excel_tab, parse_ms_project_mpp, get_group_leaf_tasks, try_float
from ..services.piemonte_scanner import scan_piemonte_projects
from .projects import PROJECT_CACHE
from ..services import versions as vstore
from ..services.competence_finance_engine import (
    compute_competence_and_cashflow,
    load_curvas_config,
    save_curvas_config,
    generate_curvas_config_excel,
    parse_curvas_config_excel,
    get_default_stage_configs,
    calcular_curvas_financeiras,
    projetar_realizado,
    load_curvas_data,
    save_custo_projetado_data,
    save_incorrido_data,
    save_pagamentos_data,
    save_curvas_vinculo_data,
    salvar_versao_curvas,
    listar_versoes_curvas,
    excluir_versao_curvas,
    parse_custo_projetado_excel,
    parse_incorrido_excel,
    parse_conciliacao_financeira_excel,
    generate_custo_projetado_template,
    generate_incorrido_template,
    generate_conciliacao_template,
    nivel1_do_codigo
)


router = APIRouter(prefix="/api/replan", tags=["Replan"])

import pickle
import os

VERSIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "schedule_versions.pkl")

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
    custom_weights: Optional[Dict[str, Any]] = None
    custom_schedule_overrides: Optional[Dict[str, Any]] = None
    custom_links_by_l5: Optional[Dict[str, List[Dict[str, Any]]]] = None
    custom_stage_configs: Optional[Dict[str, Dict[str, Any]]] = None
    export_target: Optional[str] = "current"
    active_tab: Optional[str] = "ff_replanejado"
    dist_view_mode: Optional[str] = "val"
    ff_rep_view_mode: Optional[str] = "val"
    ff_view_mode: Optional[str] = "val"
    replan_saldo_in_pct: Optional[bool] = False

def _resolve_versions(req: "ReplanRequest", parsed: Dict[str, Any]):
    """Aplica as versões ativas de cada tela: dados importados, cronograma e vínculos editados."""
    parsed = vstore.apply_active_versions(req.project_id, parsed)
    version_id = req.version_id or vstore.get_active(req.project_id, "cronograma")
    schedule_override = None
    if version_id != "atual" and req.project_id in SCHEDULE_VERSIONS:
        found_v = next((v for v in SCHEDULE_VERSIONS[req.project_id] if v["id"] == version_id), None)
        if found_v:
            schedule_override = found_v["tasks"]
        else:
            version_id = "atual"
    custom_links = req.custom_links_by_l5
    if custom_links is None:
        custom_links = vstore.get_edits(req.project_id, "distribuicao").get("links_by_l5")

    custom_schedule = req.custom_schedule_overrides
    if not custom_schedule:
        crono_edits = vstore.get_edits(req.project_id, "cronograma")
        custom_schedule = crono_edits.get("schedule_overrides") or None

    custom_weights = req.custom_weights
    if custom_weights is None:
        custom_weights = vstore.get_edits(req.project_id, "replanejado").get("replan_weights")

    return parsed, schedule_override, version_id, custom_links, custom_schedule, custom_weights

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
        from ..database import load_project_from_db
        db_parsed = load_project_from_db(req.project_id) if req.project_id else None
        if db_parsed:
            parsed = db_parsed
            PROJECT_CACHE[req.project_id] = {
                "file_path": None,
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

    parsed, schedule_override, version_id, custom_links, custom_schedule, custom_weights = _resolve_versions(req, parsed)

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
            custom_weights=custom_weights,
            schedule_tasks_override=schedule_override,
            custom_schedule_overrides=custom_schedule,
            custom_links_by_l5=custom_links
        )
        
        # Inject custom schedule versions into tab_cronograma
        is_atual_active = (version_id == "atual")
        result["tab_cronograma"]["versions"] = [
            {"id": "atual", "name": "Revisão Atual (Arquivo)", "active": is_atual_active}
        ]
        if req.project_id in SCHEDULE_VERSIONS:
            for v in SCHEDULE_VERSIONS[req.project_id]:
                result["tab_cronograma"]["versions"].append({
                    "id": v["id"],
                    "name": v["name"],
                    "active": (version_id == v["id"])
                })

        # Cálculos das curvas de Competência Contábil e Financeiro (Fluxo de Caixa)
        stage_cfg = req.custom_stage_configs
        if not stage_cfg:
            stage_cfg = load_curvas_config(req.project_id, parsed.get("budget_items", {}))

        comp_fin_res = compute_competence_and_cashflow(
            budget_items=parsed.get("budget_items", {}),
            tab_ff_replan_rows=result.get("tab_ff_replanejado", []),
            cycles=result.get("cycles", []),
            total_proj_budget=result.get("total_budget", parsed.get("total_budget", 0.0)),
            stage_configs=stage_cfg,
            cycle_start_day=req.cycle_start_day,
            cycle_end_day=req.cycle_end_day
        )

        result["tab_competencia"] = comp_fin_res["tab_competencia"]
        result["tab_financeiro"] = comp_fin_res["tab_financeiro"]
        result["stage_configs"] = comp_fin_res["stage_configs"]
        result["extended_cycles"] = comp_fin_res["extended_cycles"]
        result["s_curves_comparison"] = comp_fin_res["s_curves_comparison"]

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
        vstore.set_active(project_id, "cronograma", version_id, [version_id])

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
        from ..database import load_project_from_db
        db_parsed = load_project_from_db(req.project_id) if req.project_id else None
        if db_parsed:
            parsed = db_parsed
        else:
            raise HTTPException(status_code=400, detail="Projeto não carregado.")

    parsed, schedule_override, _, custom_links, custom_schedule, custom_weights = _resolve_versions(req, parsed)

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
        custom_weights=custom_weights,
        schedule_tasks_override=schedule_override,
        custom_schedule_overrides=custom_schedule,
        custom_links_by_l5=custom_links
    )

    try:
        stage_cfg = req.custom_stage_configs
        if not stage_cfg:
            stage_cfg = load_curvas_config(req.project_id, parsed.get("budget_items", {}))

        comp_fin_res = compute_competence_and_cashflow(
            budget_items=parsed.get("budget_items", {}),
            tab_ff_replan_rows=result.get("tab_ff_replanejado", []),
            cycles=result.get("cycles", []),
            total_proj_budget=result.get("total_budget", parsed.get("total_budget", 0.0)),
            stage_configs=stage_cfg,
            cycle_start_day=req.cycle_start_day,
            cycle_end_day=req.cycle_end_day
        )
        result["tab_competencia"] = comp_fin_res["tab_competencia"]
        result["tab_financeiro"] = comp_fin_res["tab_financeiro"]
        result["stage_configs"] = comp_fin_res["stage_configs"]
        result["extended_cycles"] = comp_fin_res["extended_cycles"]
        result["s_curves_comparison"] = comp_fin_res["s_curves_comparison"]
    except Exception as e:
        print(f"Aviso ao calcular curvas de competência e financeiro no export: {e}")

    excel_io, filename = export_replan_to_excel(
        replan_result=result,
        export_target=req.export_target or "current",
        active_tab=req.active_tab or "ff_replanejado",
        dist_view_mode=req.dist_view_mode or "val",
        ff_rep_view_mode=req.ff_rep_view_mode or "val",
        ff_view_mode=req.ff_view_mode or "val",
        replan_saldo_in_pct=bool(req.replan_saldo_in_pct)
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
    edits = dict(vstore.get_edits(req.project_id, "distribuicao"), links_by_l5=req.links_by_l5)
    vstore.save_edits(req.project_id, "distribuicao", edits)
    return {"status": "success", "saved_count": len(req.links_by_l5)}

class ResetLinksRequest(BaseModel):
    project_id: str

@router.post("/reset-links")
def reset_links(req: ResetLinksRequest):
    """
    Resets custom distribution links of the active version back to what was imported.
    """
    vstore.save_edits(req.project_id, "distribuicao", {})
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

class CurvasConfigRequest(BaseModel):
    configs: List[Dict[str, Any]]

@router.get("/{project_id}/curvas-config")
def get_curvas_config_endpoint(project_id: str):
    """Retorna as configurações atuais de prazos e insumos por etapa."""
    budget_items = {}
    if project_id in PROJECT_CACHE:
        budget_items = PROJECT_CACHE[project_id]["data"].get("budget_items", {})
    else:
        projs = scan_piemonte_projects()
        found = next((p for p in projs if p["id"] == project_id), None)
        if found and found.get("latest_file"):
            parsed = parse_excel_project(found["latest_file"]["path"])
            budget_items = parsed.get("budget_items", {})
    
    cfg = load_curvas_config(project_id, budget_items)
    return {"project_id": project_id, "configs": list(cfg.values())}

@router.post("/{project_id}/curvas-config")
def save_curvas_config_endpoint(project_id: str, req: CurvasConfigRequest):
    """Salva configurações por etapa."""
    save_curvas_config(project_id, req.configs)
    return {"status": "success", "message": "Configurações salvas com sucesso!"}

@router.get("/{project_id}/curvas-config/template")
def download_curvas_config_template(project_id: str):
    """Baixa a planilha modelo para preenchimento de prazos e lotes por etapa."""
    budget_items = {}
    if project_id in PROJECT_CACHE:
        budget_items = PROJECT_CACHE[project_id]["data"].get("budget_items", {})
    else:
        projs = scan_piemonte_projects()
        found = next((p for p in projs if p["id"] == project_id), None)
        if found and found.get("latest_file"):
            parsed = parse_excel_project(found["latest_file"]["path"])
            budget_items = parsed.get("budget_items", {})

    cfg = load_curvas_config(project_id, budget_items)
    excel_bytes = generate_curvas_config_excel(list(cfg.values()))
    
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Parametros_Curvas_{project_id}.xlsx"}
    )

@router.post("/{project_id}/curvas-config/upload")
async def upload_curvas_config(project_id: str, file: UploadFile = File(...)):
    """Faz upload da planilha Excel com configurações e salva no projeto."""
    content = await file.read()
    parsed_cfgs = parse_curvas_config_excel(content)
    if not parsed_cfgs:
        raise HTTPException(status_code=400, detail="Planilha vazia ou com formato inválido.")
    
    save_curvas_config(project_id, parsed_cfgs)
    return {"status": "success", "configs": list(parsed_cfgs.values()), "message": f"{len(parsed_cfgs)} etapas atualizadas!"}


# ==============================================================================
# Rotas Avançadas de Curvas de Competência, Financeiro e Realizado + Projeção
# ==============================================================================

class CurvasVinculoRequest(BaseModel):
    codigo_origem: str
    codigo_destino: Optional[str] = None
    remover: Optional[bool] = False


class CurvasVersaoRequest(BaseModel):
    nome: Optional[str] = None


def _get_project_data(project_id: str) -> Dict[str, Any]:
    """Recupera os dados completos da obra (cache em memória, banco ou scan)."""
    if project_id in PROJECT_CACHE:
        return PROJECT_CACHE[project_id]["data"]

    try:
        from ..database import load_project_from_db
        db_proj = load_project_from_db(project_id)
        if db_proj and db_proj.get("budget_items"):
            return db_proj
    except Exception:
        pass

    projs = scan_piemonte_projects()
    found = next((p for p in projs if p["id"] == project_id), None)
    if found and found.get("latest_file"):
        parsed = parse_excel_project(found["latest_file"]["path"])
        return parsed
    return {}


def _build_etapas_for_curvas(project_id: str, proj_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """
    Monta a lista de etapas nível 5 prontas para o motor de curvas financeiras.
    Integra Custo Projetado (se houver), ou Orçamento da EAP como base padrão.
    Aplica vínculos de códigos externos para etapas do cronograma.
    """
    budget_items = proj_data.get("budget_items", {})
    tasks = proj_data.get("tasks", {})
    links_by_l5 = proj_data.get("links_by_l5", {})
    proj_start = str(proj_data.get("start_date") or "2025-01-01")[:10]
    proj_end = str(proj_data.get("end_date") or "2026-12-31")[:10]

    curvas_dados = load_curvas_data(project_id)
    custo_proj_salvo = curvas_dados.get("custo_projetado") or {}
    cp_itens = custo_proj_salvo.get("itens") or {}
    vinculos = dict(curvas_dados.get("vinculos") or {})

    custos_etapas: Dict[str, Dict[str, float]] = {}
    projetado_fora = []
    total_fora = 0.0

    l5_codes_set = set(k for k, v in budget_items.items() if int(v.get("level") or 0) == 5)

    if cp_itens:
        for cod_origem, c_data in cp_itens.items():
            dest = vinculos.get(cod_origem, cod_origem)
            if dest in l5_codes_set:
                if dest not in custos_etapas:
                    custos_etapas[dest] = {"material": 0.0, "mao_de_obra": 0.0, "total": 0.0}
                custos_etapas[dest]["material"] += float(c_data.get("material") or 0.0)
                custos_etapas[dest]["mao_de_obra"] += float(c_data.get("mao_de_obra") or 0.0)
                custos_etapas[dest]["total"] += float(c_data.get("total") or 0.0)
            else:
                tot_item = float(c_data.get("total") or 0.0)
                projetado_fora.append({
                    "codigo": cod_origem,
                    "descricao": c_data.get("descricao", ""),
                    "total": tot_item
                })
                total_fora += tot_item

    etapas_out = []
    for cod, b_item in sorted(budget_items.items()):
        if int(b_item.get("level") or 0) != 5:
            continue

        l_tasks = links_by_l5.get(cod, [])
        t_starts = []
        t_ends = []
        pts_map: Dict[str, float] = {}

        for lk in l_tasks:
            t_id = str(lk.get("task_id") or lk.get("id"))
            t_data = tasks.get(t_id) or {}
            s_d = t_data.get("start")
            f_d = t_data.get("finish")
            if s_d:
                t_starts.append(str(s_d)[:10])
            if f_d:
                t_ends.append(str(f_d)[:10])

            for d_str, d_val in t_data.get("daily", {}).items():
                m_str = str(d_str)[:7]
                pts_map[m_str] = pts_map.get(m_str, 0.0) + float(d_val or 0.0)

        dt_ini = min(t_starts) if t_starts else proj_start
        dt_fim = max(t_ends) if t_ends else proj_end
        pontos_mensais = [{"data": f"{m}-01", "previsto": val} for m, val in sorted(pts_map.items())]

        if cod in custos_etapas:
            c_mat = round(custos_etapas[cod]["material"], 2)
            c_mo = round(custos_etapas[cod]["mao_de_obra"], 2)
            c_tot = round(custos_etapas[cod]["total"], 2)
        else:
            c_tot = float(b_item.get("total_price") or 0.0)
            c_mat = round(c_tot * 0.6, 2)
            c_mo = round(c_tot - c_mat, 2)

        etapas_out.append({
            "codigo_etapa": cod,
            "nome": b_item.get("description", ""),
            "nivel": 5,
            "data_inicio": dt_ini,
            "data_fim": dt_fim,
            "custo_material": c_mat,
            "custo_mao_obra": c_mo,
            "custo_total": c_tot,
            "pontos_mensais": pontos_mensais
        })

    return etapas_out, {
        "projetado_fora": projetado_fora,
        "total_fora": round(total_fora, 2),
        "tem_custo_projetado": bool(cp_itens),
        "total_custo_projetado": round(sum(e["custo_total"] for e in etapas_out) + total_fora, 2)
    }, curvas_dados


@router.get("/{project_id}/curvas-dados")
def get_curvas_dados_endpoint(project_id: str):
    """Retorna os dados consolidados das Curvas Físico-Financeiras, parâmetros e árvore analítica."""
    proj_data = _get_project_data(project_id)
    if not proj_data:
        raise HTTPException(status_code=404, detail=f"Obra '{project_id}' não encontrada.")

    etapas, cp_info, curvas_dados = _build_etapas_for_curvas(project_id, proj_data)
    stage_configs = load_curvas_config(project_id, proj_data.get("budget_items", {}))

    params_obra = {
        "dias_antecedencia_padrao": 10,
        "prazo_pagamento_padrao_dias": 28,
        "dia_corte_medicao_mo": 20,
        "dia_pagamento_mo": 5,
        "retencao_mo_ativa": False,
        "retencao_mo_percentual": 5.0,
        "data_fim_obra": str(proj_data.get("end_date") or "")[:10]
    }
    if "padrao" in stage_configs:
        pad = stage_configs["padrao"]
        params_obra["dias_antecedencia_padrao"] = pad.get("anticipation_days", 10)
        params_obra["prazo_pagamento_padrao_dias"] = int(pad.get("payment_terms", 28)) if str(pad.get("payment_terms", "")).isdigit() else 28
        params_obra["dia_pagamento_mo"] = pad.get("labor_payment_day", 5)

    resultado = calcular_curvas_financeiras(
        etapas=etapas,
        parametros_obra=params_obra,
        parametros_etapas=stage_configs,
        projetado_fora=cp_info["total_fora"]
    )

    b_items = proj_data.get("budget_items", {})
    niveis1_map = {}
    for cod, item in b_items.items():
        n1 = nivel1_do_codigo(cod)
        if n1:
            if n1 not in niveis1_map:
                desc = item.get("description", "") if int(item.get("level") or 0) == 1 else f"Nível {n1}"
                niveis1_map[n1] = {"codigo": n1, "nome": desc, "total": 0.0, "considerado": True}
            if int(item.get("level") or 0) == 5:
                niveis1_map[n1]["total"] += float(item.get("total_price") or 0.0)

    etapas_hierarquia = [
        {"codigo": cod, "nome": item.get("description", ""), "level": int(item.get("level") or 1)}
        for cod, item in sorted(b_items.items()) if int(item.get("level") or 1) in (1, 2, 3, 4)
    ]

    return {
        "ok": True,
        "project_id": project_id,
        "parametros_obra": params_obra,
        "stage_configs": list(stage_configs.values()),
        "custo_projetado_info": cp_info,
        "niveis1": sorted(list(niveis1_map.values()), key=lambda x: x["codigo"]),
        "etapasHierarquia": etapas_hierarquia,
        "vinculos": curvas_dados.get("vinculos", {}),
        "tem_incorrido": bool(curvas_dados.get("incorrido")),
        "tem_pagamentos": bool(curvas_dados.get("pagamentos")),
        **resultado
    }


@router.get("/{project_id}/curvas-realizado")
def get_curvas_realizado_endpoint(project_id: str, corte: Optional[str] = None):
    """Retorna os dados da curva de Realizado + Projeção calculada a partir do mês de corte."""
    proj_data = _get_project_data(project_id)
    if not proj_data:
        raise HTTPException(status_code=404, detail=f"Obra '{project_id}' não encontrada.")

    etapas, cp_info, curvas_dados = _build_etapas_for_curvas(project_id, proj_data)
    stage_configs = load_curvas_config(project_id, proj_data.get("budget_items", {}))

    corte_final = corte or datetime.date.today().strftime("%Y-%m")
    incorrido = curvas_dados.get("incorrido") or []
    if isinstance(incorrido, dict) and "itens" in incorrido:
        incorrido = incorrido["itens"]
    pagamentos = curvas_dados.get("pagamentos") or {}

    resultado = projetar_realizado(
        etapas=etapas,
        parametros_etapas=stage_configs,
        corte=corte_final,
        realizado=incorrido,
        pagamentos=pagamentos,
        projetado_fora=cp_info["total_fora"]
    )

    avisos = []
    if not pagamentos:
        avisos.append("Planilha de pagamentos (Conciliação Financeira) não carregada: o desembolso financeiro é estimado pelas regras de pagamento.")
    if not incorrido:
        avisos.append("Planilha de Incorrido (Análise do Realizado) não carregada: competência realizada está zerada.")
    if cp_info["total_fora"] > 0:
        avisos.append(f"R$ {cp_info['total_fora']:,.2f} do custo projetado está fora do cronograma (sem etapa nível 5 correspondente).")

    return {
        "ok": True,
        "project_id": project_id,
        "corte": corte_final,
        "avisos": avisos,
        **resultado
    }


@router.post("/{project_id}/curvas-importar-custo-projetado")
async def importar_custo_projetado(project_id: str, file: UploadFile = File(...)):
    """Faz upload da planilha de Custo Projetado e atualiza a base orçamentária do projeto."""
    content = await file.read()
    try:
        parsed = parse_custo_projetado_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao processar planilha de Custo Projetado: {e}")

    if not parsed.get("itens"):
        raise HTTPException(status_code=400, detail="Nenhum item válido encontrado na planilha.")

    save_custo_projetado_data(project_id, parsed)
    return {
        "status": "success",
        "message": f"Custo Projetado importado com sucesso! Total: R$ {parsed['total']:,.2f} em {len(parsed['itens'])} etapas.",
        "total": parsed["total"],
        "total_mat": parsed["total_mat"],
        "total_mo": parsed["total_mo"],
        "count": len(parsed["itens"])
    }


@router.post("/{project_id}/curvas-importar-incorrido")
async def importar_incorrido(project_id: str, file: UploadFile = File(...)):
    """Faz upload da planilha de Incorrido / Análise do Realizado."""
    content = await file.read()
    try:
        parsed = parse_incorrido_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao processar planilha de Incorrido: {e}")

    if not parsed:
        raise HTTPException(status_code=400, detail="Nenhum lançamento válido encontrado na planilha.")

    save_incorrido_data(project_id, parsed)
    total_val = round(sum(p.get("valor", 0.0) for p in parsed), 2)
    return {
        "status": "success",
        "message": f"Incorrido importado com sucesso! {len(parsed)} lançamentos (Total: R$ {total_val:,.2f}).",
        "count": len(parsed),
        "total": total_val
    }


@router.post("/{project_id}/curvas-importar-pagamentos")
async def importar_pagamentos(project_id: str, file: UploadFile = File(...)):
    """Faz upload da planilha de Conciliação Financeira / Pagamentos (Mega)."""
    content = await file.read()
    try:
        parsed = parse_conciliacao_financeira_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao processar planilha de Conciliação Financeira: {e}")

    if not parsed:
        raise HTTPException(status_code=400, detail="Nenhuma AP encontrada na planilha.")

    save_pagamentos_data(project_id, parsed)
    total_pago = sum(sum(p.get("pago", 0.0) for p in parcs) for parcs in parsed.values())
    return {
        "status": "success",
        "message": f"Conciliação Financeira importada com sucesso! {len(parsed)} APs conciliadas (Total Pago: R$ {total_pago:,.2f}).",
        "aps_count": len(parsed),
        "total_pago": round(total_pago, 2)
    }


@router.post("/{project_id}/curvas-vinculos")
def salvar_curvas_vinculo_endpoint(project_id: str, req: CurvasVinculoRequest):
    """Salva ou remove o vínculo manual entre código externo e etapa do cronograma."""
    vincs = save_curvas_vinculo_data(project_id, req.codigo_origem, req.codigo_destino, req.remover or False)
    return {"status": "success", "vinculos": vincs}


@router.get("/{project_id}/curvas-versoes")
def get_curvas_versoes_endpoint(project_id: str):
    """Lista as versões salvas das curvas."""
    return {"status": "success", "versoes": listar_versoes_curvas(project_id)}


@router.post("/{project_id}/curvas-versoes")
def post_curvas_versao_endpoint(project_id: str, req: CurvasVersaoRequest):
    """Salva uma versão congelada do cálculo atual das curvas."""
    proj_data = _get_project_data(project_id)
    etapas, cp_info, _ = _build_etapas_for_curvas(project_id, proj_data)
    stage_configs = load_curvas_config(project_id, proj_data.get("budget_items", {}))
    calc_res = calcular_curvas_financeiras(etapas=etapas, parametros_etapas=stage_configs)
    nova = salvar_versao_curvas(project_id, req.nome, calc_res)
    return {"status": "success", "versao": nova}


@router.delete("/{project_id}/curvas-versoes/{versao_id}")
def delete_curvas_versao_endpoint(project_id: str, versao_id: str):
    """Exclui uma versão salva."""
    excluir_versao_curvas(project_id, versao_id)
    return {"status": "success"}


@router.get("/{project_id}/curvas-templates/custo-projetado")
def download_template_custo_projetado(project_id: str):
    """Baixa o modelo Excel para preenchimento do Custo Projetado."""
    excel_bytes = generate_custo_projetado_template()
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Modelo_Custo_Projetado_{project_id}.xlsx"}
    )


@router.get("/{project_id}/curvas-templates/incorrido")
def download_template_incorrido(project_id: str):
    """Baixa o modelo Excel para preenchimento do Incorrido / Análise do Realizado."""
    excel_bytes = generate_incorrido_template()
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Modelo_Incorrido_Realizado_{project_id}.xlsx"}
    )


@router.get("/{project_id}/curvas-templates/conciliacao")
def download_template_conciliacao(project_id: str):
    """Baixa o modelo Excel para preenchimento da Conciliação Financeira (Mega)."""
    excel_bytes = generate_conciliacao_template()
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Modelo_Conciliacao_Financeira_{project_id}.xlsx"}
    )


