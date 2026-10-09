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
from typing import Dict, List, Any, Optional, Tuple, Union
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


def _eap_sort_key(code: str) -> list:
    parts = str(code).strip().split(".")
    res = []
    for p in parts:
        if p.isdigit():
            res.append(int(p))
        else:
            res.append(p)
    return res


def get_default_stage_configs(budget_items: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Gera configurações padrão para todos os itens da EAP do orçamento (nível >= 2),
    ordenados hierarquicamente pela chave natural da EAP.
    """
    configs: Dict[str, Dict[str, Any]] = {}
    
    # Ordena os itens da EAP
    sorted_items = sorted(
        budget_items.values(),
        key=lambda it: _eap_sort_key(it.get("code", ""))
    ) if budget_items else []

    for item in sorted_items:
        lvl = int(item.get("level") or 0)
        if lvl >= 2:
            code = str(item.get("code", "")).strip()
            if not code:
                continue
            desc = str(item.get("description", "")).strip()
            p_code = str(item.get("parent_code") or "").strip()
            if not p_code and "." in code:
                p_code = code.rsplit(".", 1)[0]

            configs[code] = {
                "code": code,
                "description": desc,
                "level": lvl,
                "parent_code": p_code,
                "material_pct": 60.0,
                "labor_pct": 40.0,
                "anticipation_days": 15,
                "distribution_type": "continuo",
                "num_batches": None,
                "payment_terms": "28",
                "labor_payment_day": 5,
                "is_custom": False,
                "source": "Padrão da Obra",
                "inherited_from": "padrao"
            }

    # Se não houver itens de nível >= 2, cria uma etapa genérica
    if not configs:
        configs["padrao"] = {
            "code": "padrao",
            "description": "Padrão da Obra",
            "level": 2,
            "parent_code": "",
            "material_pct": 60.0,
            "labor_pct": 40.0,
            "anticipation_days": 15,
            "distribution_type": "continuo",
            "num_batches": None,
            "payment_terms": "28",
            "labor_payment_day": 5,
            "is_custom": False,
            "source": "Padrão da Obra",
            "inherited_from": None
        }

    return configs


def resolve_stage_config(
    code: str, 
    budget_items: Union[Dict[str, Dict[str, Any]], List[Dict[str, Any]]], 
    effective_configs: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Encontra a configuração efetiva para um item de qualquer nível (ex: nível 5 ou 6),
    obedecendo a herança: item específico -> pai -> avô -> ... -> nível 2 -> padrão.
    Suporta budget_items tanto como dict {code: item} quanto list [{code, ...}].
    """
    if isinstance(budget_items, list):
        items_dict = {str(it.get("code", "")).strip(): it for it in budget_items if isinstance(it, dict)}
    elif isinstance(budget_items, dict):
        items_dict = budget_items
    else:
        items_dict = {}

    curr = str(code).strip()
    while curr:
        cfg = effective_configs.get(curr)
        if cfg and (cfg.get("is_custom") or cfg.get("material_pct") is not None):
            res = dict(cfg)
            if curr != code:
                res["source"] = f"Herdado de {curr}"
            return res
        item = items_dict.get(curr)
        if not item:
            if "." in curr:
                curr = curr.rsplit(".", 1)[0]
                continue
            break
        curr = str(item.get("parent_code") or "").strip()
        if not curr and "." in str(item.get("code", "")):
            curr = item["code"].rsplit(".", 1)[0]

    fallback = effective_configs.get("padrao")
    if fallback:
        res = dict(fallback)
        if not res.get("source"):
            res["source"] = "Padrão da Obra"
        return res

    return {
        "code": "padrao",
        "description": "Padrão da Obra",
        "level": 2,
        "material_pct": 60.0,
        "labor_pct": 40.0,
        "anticipation_days": 15,
        "distribution_type": "continuo",
        "num_batches": None,
        "payment_terms": "28",
        "labor_payment_day": 5,
        "source": "Padrão da Obra"
    }



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
            "description": user_cfg.get("description") or st_cfg.get("description", ""),
            "level": int(user_cfg.get("level") or st_cfg.get("level") or (len(st_code.split(".")) if st_code != "padrao" else 2)),
            "parent_code": user_cfg.get("parent_code") or st_cfg.get("parent_code"),
            "material_pct": float(user_cfg.get("material_pct", st_cfg["material_pct"])),
            "labor_pct": float(user_cfg.get("labor_pct", st_cfg["labor_pct"])),
            "anticipation_days": int(user_cfg.get("anticipation_days", st_cfg["anticipation_days"])),
            "distribution_type": user_cfg.get("distribution_type", st_cfg["distribution_type"]),
            "num_batches": int(user_cfg["num_batches"]) if user_cfg.get("num_batches") else None,
            "payment_terms": str(user_cfg.get("payment_terms") or st_cfg["payment_terms"]).strip(),
            "labor_payment_day": int(user_cfg.get("labor_payment_day", st_cfg["labor_payment_day"])),
            "is_custom": bool(user_cfg.get("is_custom", False)),
            "source": user_cfg.get("source") or ("Personalizado" if user_cfg.get("is_custom") else "Padrão da Obra"),
            "inherited_from": user_cfg.get("inherited_from")
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
        cfg = resolve_stage_config(code, budget_items, effective_configs)
        
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
    """
    Carrega configurações salvas da obra e propaga herança para toda a árvore da EAP.
    Se um nível pai (ex: Nível 2) tiver configuração personalizada, todos os filhos
    herdam automaticamente, a menos que um nível filho tenha sua própria configuração.
    """
    all_configs = get_default_stage_configs(budget_items)
    saved = {}

    # 1. Tenta carregar do banco de dados PostgreSQL primeiro
    try:
        from ..database import get_curvas_config_db
        db_cfg = get_curvas_config_db(project_id)
        if db_cfg:
            saved = db_cfg
    except Exception:
        pass

    # 2. Se não houver no banco, tenta carregar do arquivo curvas_config.json
    if not saved:
        path = _config_file_path(project_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, dict):
                        saved = raw
                    elif isinstance(raw, list):
                        saved = {str(c.get("code", "")).strip(): c for c in raw if c.get("code")}
            except Exception as e:
                print(f"Erro ao carregar curvas_config.json de {project_id}: {e}")

    # 3. Aplica as configurações explicitamente salvas
    for code, s_cfg in saved.items():
        c_clean = str(code).strip()
        if not c_clean:
            continue
        if c_clean in all_configs:
            all_configs[c_clean].update(s_cfg)
            all_configs[c_clean]["is_custom"] = bool(s_cfg.get("is_custom", True))
            all_configs[c_clean]["source"] = "Personalizado" if all_configs[c_clean]["is_custom"] else s_cfg.get("source", "Personalizado")
            all_configs[c_clean]["inherited_from"] = None
        else:
            all_configs[c_clean] = dict(s_cfg)
            all_configs[c_clean]["is_custom"] = True
            all_configs[c_clean]["source"] = "Personalizado"
            all_configs[c_clean]["inherited_from"] = None

    # 4. Propagação em cascata da herança para nós que não foram customizados
    sorted_codes = sorted(
        [k for k in all_configs if k != "padrao"],
        key=lambda c: (all_configs[c].get("level", 2), _eap_sort_key(c))
    )

    for code in sorted_codes:
        cfg = all_configs[code]
        if cfg.get("is_custom"):
            continue

        p_code = cfg.get("parent_code")
        if not p_code and "." in code:
            p_code = code.rsplit(".", 1)[0]

        ancestor_cfg = None
        curr = p_code
        while curr:
            if curr in all_configs and all_configs[curr].get("is_custom"):
                ancestor_cfg = all_configs[curr]
                break
            item = budget_items.get(curr)
            if item and item.get("parent_code"):
                curr = str(item.get("parent_code")).strip()
            elif "." in curr:
                curr = curr.rsplit(".", 1)[0]
            else:
                break

        if ancestor_cfg:
            cfg["material_pct"] = float(ancestor_cfg["material_pct"])
            cfg["labor_pct"] = float(ancestor_cfg["labor_pct"])
            cfg["anticipation_days"] = int(ancestor_cfg["anticipation_days"])
            cfg["distribution_type"] = ancestor_cfg["distribution_type"]
            cfg["num_batches"] = ancestor_cfg["num_batches"]
            cfg["payment_terms"] = ancestor_cfg["payment_terms"]
            cfg["labor_payment_day"] = ancestor_cfg.get("labor_payment_day", 5)
            cfg["is_custom"] = False
            cfg["source"] = f"Herdado de {ancestor_cfg['code']}"
            cfg["inherited_from"] = ancestor_cfg["code"]
        else:
            cfg["is_custom"] = False
            cfg["source"] = "Padrão da Obra"
            cfg["inherited_from"] = "padrao"

    return all_configs


def save_curvas_config(project_id: str, configs: Any) -> None:
    """Salva configurações da obra no curvas_config.json e no banco de dados."""
    if isinstance(configs, list):
        cfg_dict = {}
        for c in configs:
            code = str(c.get("code", "")).strip()
            if code:
                cfg_dict[code] = c
    else:
        cfg_dict = dict(configs)

    # 1. Salva no arquivo JSON
    path = _config_file_path(project_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg_dict, f, ensure_ascii=False, indent=2)

    # 2. Salva no PostgreSQL
    try:
        from ..database import save_curvas_config_db
        save_curvas_config_db(project_id, cfg_dict)
    except Exception as e:
        print(f"[DB] Notice saving curvas_config for {project_id}: {e}")


def generate_curvas_config_excel(configs: List[Dict[str, Any]]) -> bytes:
    """Gera uma planilha Excel para download com toda a árvore da EAP e colunas de configuração."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Parametros_Curvas"

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    
    fill_l2 = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    font_l2 = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
    
    fill_l3 = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    font_l3 = Font(name="Segoe UI", size=9, bold=True, color="1E293B")
    
    font_default = Font(name="Segoe UI", size=9, color="334155")

    border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    headers = [
        "Nível",
        "Código da Etapa",
        "Descrição da Etapa",
        "Material (%)",
        "Mão de Obra (%)",
        "Dias Antecedência Material",
        "Distribuição Material",
        "Número de Lotes",
        "Condição Pagamento Material",
        "Status / Origem"
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_idx, cfg in enumerate(configs, start=2):
        lvl = int(cfg.get("level") or 2)
        desc_indent = ("    " * max(0, lvl - 2)) + str(cfg.get("description", ""))

        c_lvl = ws.cell(row=row_idx, column=1, value=lvl)
        c_code = ws.cell(row=row_idx, column=2, value=str(cfg.get("code", "")))
        c_desc = ws.cell(row=row_idx, column=3, value=desc_indent)
        c_mat = ws.cell(row=row_idx, column=4, value=float(cfg.get("material_pct", 60.0)))
        c_mo = ws.cell(row=row_idx, column=5, value=float(cfg.get("labor_pct", 40.0)))
        c_ant = ws.cell(row=row_idx, column=6, value=int(cfg.get("anticipation_days", 15)))
        c_dist = ws.cell(row=row_idx, column=7, value=str(cfg.get("distribution_type", "continuo")))
        c_lot = ws.cell(row=row_idx, column=8, value=int(cfg["num_batches"]) if cfg.get("num_batches") else "")
        c_pgt = ws.cell(row=row_idx, column=9, value=str(cfg.get("payment_terms", "28")))
        c_src = ws.cell(row=row_idx, column=10, value=str(cfg.get("source", "Padrão da Obra")))

        row_fill = fill_l2 if lvl == 2 else (fill_l3 if lvl == 3 else None)
        row_font = font_l2 if lvl == 2 else (font_l3 if lvl == 3 else font_default)

        for col_idx in range(1, 11):
            c = ws.cell(row=row_idx, column=col_idx)
            c.border = border
            if row_fill:
                c.fill = row_fill
            if row_font:
                c.font = row_font

        c_lvl.alignment = Alignment(horizontal="center", vertical="center")
        c_code.alignment = Alignment(horizontal="left", vertical="center")
        c_desc.alignment = Alignment(horizontal="left", vertical="center")
        c_mat.alignment = Alignment(horizontal="right", vertical="center")
        c_mo.alignment = Alignment(horizontal="right", vertical="center")
        c_ant.alignment = Alignment(horizontal="center", vertical="center")
        c_dist.alignment = Alignment(horizontal="center", vertical="center")
        c_lot.alignment = Alignment(horizontal="center", vertical="center")
        c_pgt.alignment = Alignment(horizontal="center", vertical="center")
        c_src.alignment = Alignment(horizontal="left", vertical="center")

    col_widths = [10, 18, 48, 14, 16, 26, 22, 16, 28, 24]
    for idx, width in enumerate(col_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws.column_dimensions[col_letter].width = width

    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_curvas_config_excel(file_content: bytes) -> Dict[str, Dict[str, Any]]:
    """Lê a planilha Excel enviada pelo usuário e extrai as configurações de qualquer nível da EAP."""
    wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        return {}

    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
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
        # Remove recuos visuais da descrição
        desc = desc.strip()

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
        if idx_dist is not None and r[idx_dist] is not None:
            dt_str = str(r[idx_dist]).strip().lower()
            if "lote" in dt_str:
                dist_type = "lotes"

        num_batches = None
        if dist_type == "lotes":
            try:
                num_batches = int(r[idx_lotes]) if idx_lotes is not None and r[idx_lotes] is not None else 5
            except (ValueError, TypeError):
                num_batches = 5

        pgto = "28"
        if idx_pgto is not None and r[idx_pgto] is not None:
            pgto = str(r[idx_pgto]).strip()

        configs[code] = {
            "code": code,
            "description": desc,
            "material_pct": mat_pct,
            "labor_pct": mo_pct,
            "anticipation_days": ant_days,
            "distribution_type": dist_type,
            "num_batches": num_batches,
            "payment_terms": pgto,
            "labor_payment_day": 5,
            "is_custom": True,
            "source": "Personalizado"
        }

    return configs


