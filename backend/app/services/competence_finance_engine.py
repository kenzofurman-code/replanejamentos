"""
Motor de Cálculo para Curva de Competência (Contábil / Emissão de NF) e
Curva Financeira (Desembolso Efetivo / Fluxo de Caixa).

Regras de Negócio:
1. Curva de Competência:
   - Mão de Obra (MO): Medição do dia 21 do mês anterior ao dia 20 do mês atual.
     Nota fiscal emitida no mês atual da medição -> Competência no próprio mês do ciclo.
   - Material (MAT): A NF é emitida na entrega em obra do material.
     - Contínuo: Entrega com D dias de antecedência antes do período de execução.
     - Em Lotes: Se informado o número de lotes N, o material total é dividido em N entregas,
       sendo a 1ª entrega com D dias de antecedência ao início e as demais distribuídas
       ao longo da duração do serviço.
2. Curva Financeira (Desembolso):
   - Mão de Obra: Pagamento realizado até o dia 05 do mês subsequente ao de competência (+1 ciclo).
   - Material: Prazo de pagamento a partir da data de entrega/faturamento.
     - Padrão geral: 28 dias.
     - Flexível por etapa: configurável em até 6 parcelas (ex: 28, 35, 30/60, 30/60/90).
"""

import os
import io
import json
import datetime
import calendar
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

PROJECTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "projects"))


def parse_payment_terms(terms_str: Optional[str]) -> List[Tuple[int, float]]:
    """
    Converte string de condição de pagamento em lista de (dias, proporção).
    Exemplos:
      "28" -> [(28, 1.0)]
      "30/60" -> [(30, 0.5), (60, 0.5)]
      "30/60/90" -> [(30, 0.3333), (60, 0.3333), (90, 0.3334)]
      "30:50,60:50" -> [(30, 0.5), (60, 0.5)]
    """
    if not terms_str or not str(terms_str).strip():
        return [(28, 1.0)]
    
    clean = str(terms_str).strip().replace(" ", "")
    # Formato personalizado com dois pontos: 30:50,60:50
    if ":" in clean:
        parts = clean.split(",")
        res = []
        tot_pct = 0.0
        for p in parts:
            if ":" in p:
                d_str, pct_str = p.split(":", 1)
                try:
                    d = int(d_str)
                    pct = float(pct_str)
                    res.append((d, pct))
                    tot_pct += pct
                except ValueError:
                    continue
        if res and tot_pct > 0:
            return [(d, p / tot_pct) for d, p in res]
        return [(28, 1.0)]
    
    # Formato separado por barra ou vírgula: 30/60/90 ou 30,60,90
    sep = "/" if "/" in clean else ("," if "," in clean else None)
    if sep:
        parts = clean.split(sep)
        days_list = []
        for p in parts:
            try:
                days_list.append(int(p))
            except ValueError:
                continue
        if days_list:
            n = len(days_list)
            # Limita a 6 parcelas
            days_list = days_list[:6]
            n = len(days_list)
            weight = 1.0 / n
            return [(d, weight) for d in days_list]
    
    # Único número de dias
    try:
        d = int(clean)
        return [(max(0, d), 1.0)]
    except ValueError:
        return [(28, 1.0)]


def get_default_stage_configs(budget_items: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Gera configurações padrão para todas as etapas (nível 2 da EAP) presentes no orçamento.
    """
    configs: Dict[str, Dict[str, Any]] = {}
    
    # Localiza itens de nível 2
    for code, item in budget_items.items():
        if item.get("level") == 2:
            desc = item.get("description", "")
            configs[code] = {
                "code": code,
                "description": desc,
                "material_pct": 60.0,
                "labor_pct": 40.0,
                "anticipation_days": 15,
                "distribution_type": "continuo",
                "num_batches": None,
                "payment_terms": "28",
                "labor_payment_day": 5
            }
            
    # Se não houver itens de nível 2 específicos, cria uma etapa genérica
    if not configs:
        configs["padrao"] = {
            "code": "padrao",
            "description": "Padrão da Obra",
            "material_pct": 60.0,
            "labor_pct": 40.0,
            "anticipation_days": 15,
            "distribution_type": "continuo",
            "num_batches": None,
            "payment_terms": "28",
            "labor_payment_day": 5
        }
        
    return configs


def _find_stage_ancestor(code: str, budget_items: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Retorna o código do ancestral de Nível 2 de um item."""
    curr = code
    while curr:
        item = budget_items.get(curr)
        if not item:
            break
        if item.get("level") == 2:
            return curr
        curr = item.get("parent_code")
    return None


def _find_cycle_for_date(target_date: datetime.date, cycles: List[Dict[str, Any]]) -> int:
    """Localiza o número do ciclo cujo intervalo [start, end] contém target_date."""
    if not cycles:
        return 1
    if target_date <= cycles[0]["start"]:
        return cycles[0]["num"]
    for c in cycles:
        if c["start"] <= target_date <= c["end"]:
            return c["num"]
    if target_date >= cycles[-1]["end"]:
        return cycles[-1]["num"]
    return cycles[0]["num"]


def extend_cycles_if_needed(
    cycles: List[Dict[str, Any]], 
    max_date: datetime.date, 
    cycle_start_day: int = 21,
    cycle_end_day: int = 20
) -> List[Dict[str, Any]]:
    """Garante que a lista de ciclos cubra até max_date para fluxo financeiro futuro."""
    if not cycles:
        return cycles
    
    last_cycle = cycles[-1]
    if last_cycle["end"] >= max_date:
        return cycles
    
    new_cycles = list(cycles)
    curr_end_month = datetime.date(last_cycle["end"].year, last_cycle["end"].month, 1) + relativedelta(months=1)
    next_num = last_cycle["num"] + 1
    
    while True:
        m_year = curr_end_month.year
        m_month = curr_end_month.month
        
        if cycle_start_day <= 1:
            c_start = datetime.date(m_year, m_month, 1)
            last_d = calendar.monthrange(m_year, m_month)[1]
            c_end = datetime.date(m_year, m_month, last_d)
        else:
            prev_m = curr_end_month - relativedelta(months=1)
            last_d_prev = calendar.monthrange(prev_m.year, prev_m.month)[1]
            c_start = datetime.date(prev_m.year, prev_m.month, min(cycle_start_day, last_d_prev))
            last_d_curr = calendar.monthrange(m_year, m_month)[1]
            c_end = datetime.date(m_year, m_month, min(cycle_end_day, last_d_curr))
            
        month_label = c_end.strftime("%b/%y").capitalize()
        new_cycles.append({
            "num": next_num,
            "name": f"Mês {next_num}",
            "period_label": month_label,
            "full_label": f"Mês {next_num} ({month_label})",
            "start": c_start,
            "end": c_end,
            "is_past": False
        })
        
        if c_end >= max_date or next_num >= last_cycle["num"] + 12:
            break
            
        next_num += 1
        curr_end_month += relativedelta(months=1)
        
    return new_cycles


def _to_date(val: Any) -> datetime.date:
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, str):
        parts = val.strip().split("-")
        if len(parts) == 3:
            try:
                return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                pass
    return datetime.date(2025, 1, 1)


def compute_competence_and_cashflow(
    budget_items: Dict[str, Dict[str, Any]],
    tab_ff_replan_rows: List[Dict[str, Any]],
    cycles: List[Dict[str, Any]],
    total_proj_budget: float,
    stage_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    cycle_start_day: int = 21,
    cycle_end_day: int = 20
) -> Dict[str, Any]:
    """
    Executa os cálculos das abas Competência e Financeiro.
    """
    # 0. Normaliza cycles para garantir que start e end sejam datetime.date
    norm_cycles = []
    for c in cycles:
        c_copy = dict(c)
        c_copy["start"] = _to_date(c.get("start"))
        c_copy["end"] = _to_date(c.get("end"))
        norm_cycles.append(c_copy)
    cycles = norm_cycles

    # 1. Configurações por etapa
    default_configs = get_default_stage_configs(budget_items)

    effective_configs: Dict[str, Dict[str, Any]] = {}
    for st_code, st_cfg in default_configs.items():
        user_cfg = (stage_configs or {}).get(st_code, {})
        effective_configs[st_code] = {
            "code": st_code,
            "description": user_cfg.get("description") or st_cfg["description"],
            "material_pct": float(user_cfg.get("material_pct", st_cfg["material_pct"])),
            "labor_pct": float(user_cfg.get("labor_pct", st_cfg["labor_pct"])),
            "anticipation_days": int(user_cfg.get("anticipation_days", st_cfg["anticipation_days"])),
            "distribution_type": user_cfg.get("distribution_type", st_cfg["distribution_type"]),
            "num_batches": int(user_cfg["num_batches"]) if user_cfg.get("num_batches") else None,
            "payment_terms": str(user_cfg.get("payment_terms") or st_cfg["payment_terms"]).strip(),
            "labor_payment_day": int(user_cfg.get("labor_payment_day", st_cfg["labor_payment_day"]))
        }
        # Garantir normalização da soma de material e mão de obra
        mat_pct = effective_configs[st_code]["material_pct"]
        effective_configs[st_code]["labor_pct"] = max(0.0, 100.0 - mat_pct)

    # 2. Localizar linhas de nível 5 da tab_ff_replan_rows
    l5_rows = {r["code"]: r for r in tab_ff_replan_rows if r.get("level") == 5}
    
    # 3. Mapear para cada L5: valores mensais de replanejamento (R$)
    # e determinar ciclos ativos
    l5_planned_by_cycle: Dict[str, Dict[int, float]] = {}
    for code, row in l5_rows.items():
        vals: Dict[int, float] = {}
        for c in cycles:
            c_num = c["num"]
            val = float(row.get("cycle_vals", {}).get(str(c_num), 0.0))
            vals[c_num] = val
        l5_planned_by_cycle[code] = vals

    # 4. Estimar data máxima futura para extensão dos ciclos se necessário
    # Máximo prazo de entrega + condição de pgto pode adicionar até ~120 dias
    max_project_date = cycles[-1]["end"] + datetime.timedelta(days=120)
    extended_cycles = extend_cycles_if_needed(cycles, max_project_date, cycle_start_day, cycle_end_day)

    # Dicionário de busca rápida de ciclos por data
    cycle_by_num = {c["num"]: c for c in extended_cycles}

    # 5. Calcular para cada L5:
    # - comp_mat[c_num], comp_mo[c_num]
    # - fin_mat[c_num], fin_mo[c_num]
    l5_comp_mat: Dict[str, Dict[int, float]] = {c: {cy["num"]: 0.0 for cy in extended_cycles} for c in l5_rows}
    l5_comp_mo: Dict[str, Dict[int, float]] = {c: {cy["num"]: 0.0 for cy in extended_cycles} for c in l5_rows}
    l5_fin_mat: Dict[str, Dict[int, float]] = {c: {cy["num"]: 0.0 for cy in extended_cycles} for c in l5_rows}
    l5_fin_mo: Dict[str, Dict[int, float]] = {c: {cy["num"]: 0.0 for cy in extended_cycles} for c in l5_rows}

    for code, row in l5_rows.items():
        st_ancestor = _find_stage_ancestor(code, budget_items)
        cfg = effective_configs.get(st_ancestor) or effective_configs.get("padrao") or list(effective_configs.values())[0]
        
        mat_pct = cfg["material_pct"] / 100.0
        mo_pct = cfg["labor_pct"] / 100.0
        anticip_days = cfg["anticipation_days"]
        num_batches = cfg["num_batches"]
        pmt_terms = parse_payment_terms(cfg["payment_terms"])

        planned_cycles = l5_planned_by_cycle.get(code, {})
        active_cycles = [c_num for c_num, val in planned_cycles.items() if val > 0.0]

        # A. MÃO DE OBRA:
        # Competência no próprio ciclo da medição (dia 20)
        # Desembolso Financeiro no ciclo seguinte (pago até dia 5 do mês subsequente)
        for c_num, val in planned_cycles.items():
            if val > 0.0:
                mo_val = val * mo_pct
                l5_comp_mo[code][c_num] += mo_val
                
                # Desembolso financeiro de MO no ciclo c_num + 1
                fin_c_num = c_num + 1
                if fin_c_num in l5_fin_mo[code]:
                    l5_fin_mo[code][fin_c_num] += mo_val
                elif extended_cycles:
                    l5_fin_mo[code][extended_cycles[-1]["num"]] += mo_val

        # B. MATERIAL:
        total_mat_val = sum(val * mat_pct for val in planned_cycles.values())
        
        if total_mat_val > 0.0:
            if num_batches and num_batches > 1 and active_cycles:
                # Distribuição em Lotes
                first_c = min(active_cycles)
                last_c = max(active_cycles)
                batch_val = total_mat_val / float(num_batches)
                
                # A 1ª entrega ocorre 'anticip_days' antes do início do primeiro ciclo ativo
                c_start_date = cycle_by_num[first_c]["start"]
                first_delivery_date = c_start_date - datetime.timedelta(days=anticip_days)
                
                # Entregas subsequentes distribuídas ao longo dos ciclos
                span_cycles = max(1, last_c - first_c)
                step = span_cycles / float(max(1, num_batches - 1)) if num_batches > 1 else 0
                
                for b_idx in range(num_batches):
                    if b_idx == 0:
                        deliv_date = first_delivery_date
                    else:
                        target_c_num = min(last_c, int(round(first_c + b_idx * step)))
                        target_start = cycle_by_num[target_c_num]["start"]
                        deliv_date = target_start - datetime.timedelta(days=anticip_days)
                    
                    # Localiza ciclo da entrega para Competência (NF)
                    deliv_c_num = _find_cycle_for_date(deliv_date, extended_cycles)
                    l5_comp_mat[code][deliv_c_num] += batch_val
                    
                    # Financeiro para cada parcela do lote
                    for p_days, p_ratio in pmt_terms:
                        due_date = deliv_date + datetime.timedelta(days=p_days)
                        due_c_num = _find_cycle_for_date(due_date, extended_cycles)
                        l5_fin_mat[code][due_c_num] += (batch_val * p_ratio)
            else:
                # Distribuição Contínua (mês a mês conforme execução)
                for c_num, val in planned_cycles.items():
                    if val > 0.0:
                        mat_val = val * mat_pct
                        c_obj = cycle_by_num[c_num]
                        # Material chega 'anticip_days' antes do início do ciclo
                        deliv_date = c_obj["start"] - datetime.timedelta(days=anticip_days)
                        deliv_c_num = _find_cycle_for_date(deliv_date, extended_cycles)
                        l5_comp_mat[code][deliv_c_num] += mat_val
                        
                        # Financeiro para cada parcela da entrega
                        for p_days, p_ratio in pmt_terms:
                            due_date = deliv_date + datetime.timedelta(days=p_days)
                            due_c_num = _find_cycle_for_date(due_date, extended_cycles)
                            l5_fin_mat[code][due_c_num] += (mat_val * p_ratio)

    # 6. Montagem das árvores completas (Níveis 1 a 5) para Competência e Financeiro
    # Helper para montar a árvore completa com rollup
    def _build_tree(
        data_mat: Dict[str, Dict[int, float]],
        data_mo: Dict[str, Dict[int, float]]
    ) -> List[Dict[str, Any]]:
        # Inicializa nós de todos os itens do orçamento
        tree: Dict[str, Dict[str, Any]] = {}
        for code, item in budget_items.items():
            lvl = item.get("level", 5)
            b = item.get("total_price", 0.0)
            tree[code] = {
                "level": lvl,
                "code": code,
                "parent_code": item.get("parent_code"),
                "description": item.get("description", ""),
                "budget": b,
                "cycle_vals": {cy["num"]: 0.0 for cy in extended_cycles},
                "cycle_mat_vals": {cy["num"]: 0.0 for cy in extended_cycles},
                "cycle_mo_vals": {cy["num"]: 0.0 for cy in extended_cycles},
            }
        
        # Preenche os nós folha (Nível 5)
        for code in l5_rows:
            if code in tree:
                for cy in extended_cycles:
                    c_num = cy["num"]
                    m_val = data_mat[code].get(c_num, 0.0)
                    mo_val = data_mo[code].get(c_num, 0.0)
                    tot = m_val + mo_val
                    tree[code]["cycle_mat_vals"][c_num] = m_val
                    tree[code]["cycle_mo_vals"][c_num] = mo_val
                    tree[code]["cycle_vals"][c_num] = tot

        # Rollup para Níveis 4, 3, 2, 1
        for lvl in [4, 3, 2, 1]:
            for p in [it for it in tree.values() if it["level"] == lvl]:
                children = [c for c in tree.values() if c["parent_code"] == p["code"]]
                if children:
                    if p["budget"] <= 0.0:
                        p["budget"] = sum(ch["budget"] for ch in children)
                    for cy in extended_cycles:
                        c_num = cy["num"]
                        p["cycle_mat_vals"][c_num] = sum(ch["cycle_mat_vals"][c_num] for ch in children)
                        p["cycle_mo_vals"][c_num] = sum(ch["cycle_mo_vals"][c_num] for ch in children)
                        p["cycle_vals"][c_num] = sum(ch["cycle_vals"][c_num] for ch in children)

        # Monta a lista ordenada respeitando WBS
        def _wbs_key(code: str):
            parts = code.split(".")
            res = []
            for p in parts:
                try:
                    res.append(int(p))
                except ValueError:
                    res.append(p)
            return res

        rows_out = []
        for code in sorted(tree.keys(), key=_wbs_key):
            node = tree[code]
            c_vals_str = {str(k): round(v, 2) for k, v in node["cycle_vals"].items()}
            c_mat_str = {str(k): round(v, 2) for k, v in node["cycle_mat_vals"].items()}
            c_mo_str = {str(k): round(v, 2) for k, v in node["cycle_mo_vals"].items()}
            c_pcts_str = {
                str(k): round((v / total_proj_budget) * 100.0, 3) if total_proj_budget > 0 else 0.0
                for k, v in node["cycle_vals"].items()
            }
            tot_val = round(sum(node["cycle_vals"].values()), 2)
            tot_mat = round(sum(node["cycle_mat_vals"].values()), 2)
            tot_mo = round(sum(node["cycle_mo_vals"].values()), 2)
            tot_pct = round((tot_val / total_proj_budget) * 100.0, 2) if total_proj_budget > 0 else 0.0

            rows_out.append({
                "level": node["level"],
                "code": node["code"],
                "parent_code": node["parent_code"],
                "description": node["description"],
                "budget": round(node["budget"], 2),
                "budget_pct": round((node["budget"] / total_proj_budget) * 100.0, 2) if total_proj_budget > 0 else 0.0,
                "cycle_vals": c_vals_str,
                "cycle_mat_vals": c_mat_str,
                "cycle_mo_vals": c_mo_str,
                "cycle_pcts": c_pcts_str,
                "total": tot_val,
                "total_mat": tot_mat,
                "total_mo": tot_mo,
                "total_pct": tot_pct
            })
        return rows_out

    tab_competencia_rows = _build_tree(l5_comp_mat, l5_comp_mo)
    tab_financeiro_rows = _build_tree(l5_fin_mat, l5_fin_mo)

    # 7. Curvas S Totais para gráficos
    # Root Level 1 (Obra inteira)
    root_comp = next((r for r in tab_competencia_rows if r["level"] == 1), None)
    root_fin = next((r for r in tab_financeiro_rows if r["level"] == 1), None)

    comp_month_vals = [float(root_comp["cycle_vals"].get(str(c["num"]), 0.0)) if root_comp else 0.0 for c in extended_cycles]
    fin_month_vals = [float(root_fin["cycle_vals"].get(str(c["num"]), 0.0)) if root_fin else 0.0 for c in extended_cycles]

    comp_accum_vals = []
    c_acc = 0.0
    for v in comp_month_vals:
        c_acc += v
        comp_accum_vals.append(round(c_acc, 2))

    fin_accum_vals = []
    f_acc = 0.0
    for v in fin_month_vals:
        f_acc += v
        fin_accum_vals.append(round(f_acc, 2))

    comp_accum_pcts = [round((v / total_proj_budget) * 100.0, 2) if total_proj_budget > 0 else 0.0 for v in comp_accum_vals]
    fin_accum_pcts = [round((v / total_proj_budget) * 100.0, 2) if total_proj_budget > 0 else 0.0 for v in fin_accum_vals]

    # Formatar ciclos estendidos para retorno serializável
    cycles_formatted = [
        {
            "num": c["num"],
            "name": c["name"],
            "period_label": c["period_label"],
            "full_label": c["full_label"],
            "start": c["start"].strftime("%Y-%m-%d") if isinstance(c["start"], (datetime.date, datetime.datetime)) else str(c["start"]),
            "end": c["end"].strftime("%Y-%m-%d") if isinstance(c["end"], (datetime.date, datetime.datetime)) else str(c["end"]),
            "is_past": c.get("is_past", False)
        }
        for c in extended_cycles
    ]

    return {
        "tab_competencia": tab_competencia_rows,
        "tab_financeiro": tab_financeiro_rows,
        "stage_configs": list(effective_configs.values()),
        "extended_cycles": cycles_formatted,
        "s_curves_comparison": {
            "labels": [c["period_label"] for c in extended_cycles],
            "full_labels": [c["full_label"] for c in extended_cycles],
            "comp_month_vals": [round(v, 2) for v in comp_month_vals],
            "comp_accum_vals": comp_accum_vals,
            "comp_accum_pcts": comp_accum_pcts,
            "fin_month_vals": [round(v, 2) for v in fin_month_vals],
            "fin_accum_vals": fin_accum_vals,
            "fin_accum_pcts": fin_accum_pcts,
        }
    }


def _config_file_path(project_id: str) -> str:
    proj_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(proj_dir, exist_ok=True)
    return os.path.join(proj_dir, "curvas_config.json")


def load_curvas_config(project_id: str, budget_items: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Carrega configuração salva da obra ou gera defaults se não existir."""
    defaults = get_default_stage_configs(budget_items)
    path = _config_file_path(project_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Mescla configurações salvas sobre defaults
            if isinstance(saved, dict):
                for k, v in saved.items():
                    if k in defaults:
                        defaults[k].update(v)
                    else:
                        defaults[k] = v
            elif isinstance(saved, list):
                for item in saved:
                    code = str(item.get("code", ""))
                    if code:
                        if code in defaults:
                            defaults[code].update(item)
                        else:
                            defaults[code] = item
        except Exception as e:
            print(f"Erro ao carregar curvas_config.json de {project_id}: {e}")
    return defaults


def save_curvas_config(project_id: str, configs: Any) -> None:
    """Salva configurações da obra no curvas_config.json."""
    path = _config_file_path(project_id)
    # Se configs for lista, converte para dict por code
    if isinstance(configs, list):
        cfg_dict = {}
        for c in configs:
            code = str(c.get("code", ""))
            if code:
                cfg_dict[code] = c
    else:
        cfg_dict = configs

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg_dict, f, ensure_ascii=False, indent=2)


def generate_curvas_config_excel(configs: List[Dict[str, Any]]) -> bytes:
    """Gera uma planilha Excel para download com as etapas e colunas de configuração."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Parametros_Curvas"

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    headers = [
        "Código da Etapa",
        "Descrição da Etapa",
        "Material (%)",
        "Mão de Obra (%)",
        "Dias Antecedência Material",
        "Distribuição Material",
        "Número de Lotes",
        "Condição Pagamento Material"
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_idx, cfg in enumerate(configs, start=2):
        ws.cell(row=row_idx, column=1, value=str(cfg.get("code", "")))
        ws.cell(row=row_idx, column=2, value=str(cfg.get("description", "")))
        ws.cell(row=row_idx, column=3, value=float(cfg.get("material_pct", 60.0)))
        ws.cell(row=row_idx, column=4, value=float(cfg.get("labor_pct", 40.0)))
        ws.cell(row=row_idx, column=5, value=int(cfg.get("anticipation_days", 15)))
        ws.cell(row=row_idx, column=6, value=str(cfg.get("distribution_type", "continuo")))
        ws.cell(row=row_idx, column=7, value=int(cfg["num_batches"]) if cfg.get("num_batches") else "")
        ws.cell(row=row_idx, column=8, value=str(cfg.get("payment_terms", "28")))

        for col_idx in range(1, 9):
            ws.cell(row=row_idx, column=col_idx).border = border

    # Largura das colunas
    col_widths = [16, 40, 14, 16, 26, 22, 16, 28]
    for idx, width in enumerate(col_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws.column_dimensions[col_letter].width = width

    ws.views.sheetView[0].showGridLines = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_curvas_config_excel(file_content: bytes) -> Dict[str, Dict[str, Any]]:
    """Lê a planilha Excel enviada pelo usuário e extrai as configurações por etapa."""
    wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        return {}

    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    # Encontra índices
    def _find_col(keywords: List[str]) -> Optional[int]:
        for idx, h in enumerate(header):
            if any(k in h for k in keywords):
                return idx
        return None

    idx_code = _find_col(["código", "codigo"])
    idx_desc = _find_col(["descrição", "descricao"])
    idx_mat = _find_col(["material"])
    idx_mo = _find_col(["mão de obra", "mao de obra", "mo"])
    idx_ant = _find_col(["antecedência", "antecedencia", "dias"])
    idx_dist = _find_col(["distribuição", "distribuicao"])
    idx_lotes = _find_col(["lotes", "lote"])
    idx_pgto = _find_col(["pagamento", "condição", "condicao"])

    configs: Dict[str, Dict[str, Any]] = {}
    for r in rows[1:]:
        if not r or all(c is None for c in r):
            continue
        code = str(r[idx_code]).strip() if idx_code is not None and r[idx_code] is not None else ""
        if not code:
            continue

        desc = str(r[idx_desc]).strip() if idx_desc is not None and r[idx_desc] is not None else ""
        
        try:
            mat_pct = float(r[idx_mat]) if idx_mat is not None and r[idx_mat] is not None else 60.0
            if mat_pct <= 1.0 and mat_pct > 0.0:
                mat_pct *= 100.0
        except (ValueError, TypeError):
            mat_pct = 60.0

        try:
            mo_pct = float(r[idx_mo]) if idx_mo is not None and r[idx_mo] is not None else (100.0 - mat_pct)
            if mo_pct <= 1.0 and mo_pct > 0.0:
                mo_pct *= 100.0
        except (ValueError, TypeError):
            mo_pct = max(0.0, 100.0 - mat_pct)

        try:
            ant_days = int(r[idx_ant]) if idx_ant is not None and r[idx_ant] is not None else 15
        except (ValueError, TypeError):
            ant_days = 15

        dist_type = "continuo"
        if idx_dist is not None and r[idx_dist]:
            dist_str = str(r[idx_dist]).lower().strip()
            if "lote" in dist_str:
                dist_type = "lotes"

        num_batches = None
        if idx_lotes is not None and r[idx_lotes]:
            try:
                num_batches = int(r[idx_lotes])
                if num_batches > 1:
                    dist_type = "lotes"
            except (ValueError, TypeError):
                pass

        pmt_terms = "28"
        if idx_pgto is not None and r[idx_pgto]:
            pmt_terms = str(r[idx_pgto]).strip()

        configs[code] = {
            "code": code,
            "description": desc,
            "material_pct": mat_pct,
            "labor_pct": mo_pct,
            "anticipation_days": ant_days,
            "distribution_type": dist_type,
            "num_batches": num_batches,
            "payment_terms": pmt_terms,
            "labor_payment_day": 5
        }

    return configs

