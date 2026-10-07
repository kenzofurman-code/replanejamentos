"""
Projeto em planilhas separadas (uma por tela de entrada).

Uma pasta de projeto neste formato contém:
    orcamento.xlsx     -> EAP níveis 1 a 5
    cronograma.xlsx    -> atividades (+ aba opcional 'Diario' com distribuição diária)
    distribuicao.xlsx  -> vínculos item nível 5 <-> atividade do cronograma
    medicao.xlsx       -> data de corte, histórico mensal e medições por item

Só orcamento.xlsx é obrigatório. A especificação das colunas está em docs/PLANILHAS.md.
parse_split_project() devolve exatamente o mesmo dicionário que parse_excel_project().
"""
import os
import datetime
from typing import Dict, List, Any, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill

from .excel_reader import norm, try_float, try_pct, parse_date_cell

FILES = {
    "orcamento": "orcamento.xlsx",
    "cronograma": "cronograma.xlsx",
    "distribuicao": "distribuicao.xlsx",
    "medicao": "medicao.xlsx",
}

COLUMNS = {
    "orcamento": ["Nível", "Código", "Código Pai", "Descrição", "Unidade", "Quantidade",
                  "Preço Unitário", "Preço Total", "Medição Acumulada (%)"],
    "cronograma": ["ID", "Nome da Atividade", "Duração (dias)", "Data Início", "Data Término",
                   "Predecessoras", "Lote Mãe", "Lote / Pavimento"],
    "cronograma_diario": ["ID", "Nome da Atividade", "Data", "Valor"],
    "distribuicao": ["Código Item (Nível 5)", "Nome da Atividade", "Duração Manual (dias)", "Valor Alocado (R$)"],
    "medicao_corte": ["Medição de Corte (Nº)", "Data de Corte"],
    "medicao_historico": ["Nº Medição", "Data", "Realizado Obra (%)"],
    "medicao_itens": ["Código Item", "Nº Medição", "Previsto (%)", "Realizado (%)"],
    "medicao_acumulado": ["Código Item", "Acumulado (%)"],
}

DEFAULT_START_DATE = datetime.date(2025, 10, 1)


def is_split_project(folder: str) -> bool:
    return os.path.isdir(folder) and os.path.exists(os.path.join(folder, FILES["orcamento"]))


def split_signature(folder: str) -> str:
    """Tamanho de cada arquivo presente; muda quando algum arquivo muda."""
    parts = []
    for name in FILES.values():
        p = os.path.join(folder, name)
        if os.path.exists(p):
            parts.append(f"{name}:{os.path.getsize(p)}")
    return "|".join(parts)


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def _rows(ws, expected: List[str]) -> List[Dict[str, Any]]:
    """Lê uma aba com cabeçalho na linha 1; devolve dicts indexados pelo nome normalizado da coluna."""
    it = ws.iter_rows(values_only=True)
    header = next(it, None)
    if not header:
        return []
    keys = [norm(str(h)).strip() if h is not None else "" for h in header]
    wanted = {norm(c).strip() for c in expected}
    missing = wanted - set(keys)
    if missing:
        raise ValueError(f"Aba '{ws.title}': colunas ausentes {sorted(missing)}")
    out = []
    for row in it:
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        out.append({k: (row[i] if i < len(row) else None) for i, k in enumerate(keys) if k})
    return out


def _col(row: Dict[str, Any], name: str):
    return row.get(norm(name).strip())


def _str(v) -> str:
    return str(v).strip() if v is not None else ""


def _sheet(wb, title: str):
    for s in wb.sheetnames:
        if norm(s) == norm(title):
            return wb[s]
    return None


def _workdays(s: datetime.date, f: datetime.date) -> Dict[datetime.date, float]:
    daily = {}
    cur = s
    while cur <= f:
        if cur.weekday() < 5:
            daily[cur] = 1.0
        cur += datetime.timedelta(days=1)
    return daily or {s: 1.0}


def _read_orcamento(path: str):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = _rows(wb.worksheets[0], COLUMNS["orcamento"])
    finally:
        wb.close()

    budget_items: Dict[str, Dict[str, Any]] = {}
    item_measurements: Dict[str, float] = {}
    project_name = "Projeto"
    total_budget = 0.0
    stack: Dict[int, str] = {}

    for r in rows:
        try:
            lvl = int(_col(r, "Nível"))
        except (TypeError, ValueError):
            continue
        code = _str(_col(r, "Código")) or str(len(budget_items) + 1)
        parent = _str(_col(r, "Código Pai")) or None
        if parent is None and lvl > 1:
            parent = next((stack[l] for l in range(lvl - 1, 0, -1) if l in stack), "1")
        stack[lvl] = code
        for deeper in [l for l in stack if l > lvl]:
            del stack[deeper]

        desc = _str(_col(r, "Descrição"))
        pt = try_float(_col(r, "Preço Total"))
        med = try_pct(_col(r, "Medição Acumulada (%)"))
        if lvl == 1:
            project_name = desc or "Projeto"
            if pt > 0:
                total_budget = pt
        if med > 0:
            item_measurements[code] = med
        und = _col(r, "Unidade")
        budget_items[code] = {
            "code": code,
            "description": desc,
            "level": lvl,
            "parent_code": parent,
            "unit": _str(und) or None,
            "quantity": try_float(_col(r, "Quantidade")),
            "unit_price": try_float(_col(r, "Preço Unitário")),
            "total_price": pt,
            "accum_measured_pct": med,
        }

    if total_budget <= 0.0:
        total_budget = sum(i["total_price"] for i in budget_items.values() if i["level"] == 5)
    return project_name, total_budget, budget_items, item_measurements


def _read_cronograma(path: str) -> Dict[str, Dict[str, Any]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = _rows(wb.worksheets[0], COLUMNS["cronograma"])
        ws_d = _sheet(wb, "Diario")
        daily_rows = _rows(ws_d, COLUMNS["cronograma_diario"]) if ws_d is not None else []
    finally:
        wb.close()

    daily_by_id: Dict[str, Dict[datetime.date, float]] = {}
    for r in daily_rows:
        t_id = _str(_col(r, "ID"))
        dt = parse_date_cell(_col(r, "Data"))
        val = try_float(_col(r, "Valor"))
        if t_id and dt and val > 0:
            daily_by_id.setdefault(t_id, {})[dt] = val

    tasks: Dict[str, Dict[str, Any]] = {}
    for idx, r in enumerate(rows, start=1):
        name = _str(_col(r, "Nome da Atividade"))
        if not name:
            continue
        t_id = _str(_col(r, "ID")) or str(idx)
        dur_raw = _col(r, "Duração (dias)")
        dur = try_float(dur_raw)
        daily = daily_by_id.get(t_id)
        s_d = parse_date_cell(_col(r, "Data Início"))
        f_d = parse_date_cell(_col(r, "Data Término"))
        if daily:
            s_d = s_d or min(daily)
            f_d = f_d or max(daily)
        elif not s_d and not f_d:
            daily = {}  # atividade sem datas: fica fora da distribuição
        else:
            s_d = s_d or datetime.date(2026, 10, 1)
            f_d = f_d or s_d + datetime.timedelta(days=max(1, int(dur or 1) - 1))
            daily = _workdays(s_d, f_d)

        preds = [p.strip() for p in _str(_col(r, "Predecessoras")).replace(";", ",").split(",") if p.strip()]
        key = name if name not in tasks else f"{name} (#{t_id})"
        tasks[key] = {
            "id": t_id,
            "name": name,
            "duration": dur if dur_raw not in (None, "") else 1.0,
            "start": s_d.strftime("%Y-%m-%d") if s_d else None,
            "finish": f_d.strftime("%Y-%m-%d") if f_d else None,
            "predecessors": preds,
            "successors": [],
            # Vazio = o motor deriva o lote a partir do nome da atividade
            "lote_mae": _str(_col(r, "Lote Mãe")) or None,
            "lot": _str(_col(r, "Lote / Pavimento")) or None,
            "daily": daily,
        }
    return tasks


def _read_distribuicao(path: str):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = _rows(wb.worksheets[0], COLUMNS["distribuicao"])
    finally:
        wb.close()
    links_by_l5: Dict[str, List[Dict[str, Any]]] = {}
    all_links: List[Dict[str, Any]] = []
    for r in rows:
        code = _str(_col(r, "Código Item (Nível 5)"))
        name = _str(_col(r, "Nome da Atividade"))
        if not code or not name:
            continue
        link = {
            "wbs_code": code,
            "task_name": name,
            "duration": try_float(_col(r, "Duração Manual (dias)")),
            "allocated_val": try_float(_col(r, "Valor Alocado (R$)")),
        }
        links_by_l5.setdefault(code, []).append(link)
        all_links.append(link)
    return links_by_l5, all_links


def _read_medicao(path: str, total_budget: float):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        def sheet_rows(title, cols):
            ws = _sheet(wb, title)
            return _rows(ws, cols) if ws is not None else []
        corte = sheet_rows("Corte", COLUMNS["medicao_corte"])
        hist = sheet_rows("Historico", COLUMNS["medicao_historico"])
        itens = sheet_rows("Itens", COLUMNS["medicao_itens"])
        acum = sheet_rows("Acumulado", COLUMNS["medicao_acumulado"])
    finally:
        wb.close()

    cutoff_med_num = 1
    cutoff_date = None
    if corte:
        try:
            cutoff_med_num = int(try_float(_col(corte[0], "Medição de Corte (Nº)"), 1))
        except (TypeError, ValueError):
            cutoff_med_num = 1
        cutoff_date = parse_date_cell(_col(corte[0], "Data de Corte"))

    item_monthly: Dict[str, Dict[int, Dict[str, float]]] = {}
    for r in itens:
        code = _str(_col(r, "Código Item"))
        n = int(try_float(_col(r, "Nº Medição")))
        if not code or n <= 0:
            continue
        item_monthly.setdefault(code, {})[n] = {
            "previsto": try_float(_col(r, "Previsto (%)")),
            "realizado": try_float(_col(r, "Realizado (%)")),
        }

    item_measurements = {}
    for r in acum:
        code = _str(_col(r, "Código Item"))
        if code:
            item_measurements[code] = try_float(_col(r, "Acumulado (%)"))

    history_monthly = []
    for r in hist:
        n = int(try_float(_col(r, "Nº Medição")))
        dt = parse_date_cell(_col(r, "Data"))
        pct = try_float(_col(r, "Realizado Obra (%)"))
        if n > 0 and dt and n <= cutoff_med_num:
            history_monthly.append({"med_num": n, "date": dt.strftime("%Y-%m-%d"),
                                    "pct": pct, "value": pct * total_budget})
    history_monthly.sort(key=lambda h: h["med_num"])
    return cutoff_med_num, cutoff_date, item_monthly, item_measurements, history_monthly


def parse_split_project(folder: str) -> Dict[str, Any]:
    p = {k: os.path.join(folder, v) for k, v in FILES.items()}
    project_name, total_budget, budget_items, item_measurements = _read_orcamento(p["orcamento"])

    tasks = _read_cronograma(p["cronograma"]) if os.path.exists(p["cronograma"]) else {}
    links_by_l5, all_links = _read_distribuicao(p["distribuicao"]) if os.path.exists(p["distribuicao"]) else ({}, [])

    cutoff_med_num, cutoff_date, item_monthly, history_monthly = 1, None, {}, []
    if os.path.exists(p["medicao"]):
        cutoff_med_num, cutoff_date, item_monthly, med_acum, history_monthly = _read_medicao(p["medicao"], total_budget)
        # Mesmo comportamento do leitor original: a aba de medição substitui o acumulado do orçamento.
        item_measurements = med_acum
        for code, v in med_acum.items():
            if code in budget_items:
                budget_items[code]["accum_measured_pct"] = v

    active = [dt for t in tasks.values() for dt, v in t["daily"].items() if v > 0]
    if history_monthly:
        start_date = datetime.date.fromisoformat(history_monthly[0]["date"])
    elif active:
        start_date = min(active)
    else:
        start_date = DEFAULT_START_DATE
    end_date = max(active) if active else datetime.date(2029, 10, 1)

    return {
        "project_name": project_name,
        "total_budget": total_budget,
        "start_date": start_date,
        "end_date": end_date,
        "cutoff_med_num": cutoff_med_num,
        "cutoff_date": cutoff_date,
        "budget_items": budget_items,
        "tasks": tasks,
        "links_by_l5": links_by_l5,
        "all_links": all_links,
        "item_measurements": item_measurements,
        "item_monthly_measurements": item_monthly,
        "history_monthly": history_monthly,
    }


# ---------------------------------------------------------------------------
# Escrita (extração única da planilha gigante e geração dos modelos)
# ---------------------------------------------------------------------------

_HEADER_FILL = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
_HEADER_FONT = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")


def _new_sheet(wb, title: str, headers: List[str], first: bool = False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.append(headers)
    for i, _ in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i)
        c.fill = _HEADER_FILL
        c.font = _HEADER_FONT
        ws.column_dimensions[c.column_letter].width = 45 if "Descri" in headers[i - 1] or "Nome" in headers[i - 1] else 18
    ws.freeze_panes = "A2"
    return ws


def _is_uniform(task: Dict[str, Any]) -> bool:
    daily = task.get("daily") or {}
    if not daily or not task.get("start") or not task.get("finish"):
        return False
    s = datetime.date.fromisoformat(task["start"][:10])
    f = datetime.date.fromisoformat(task["finish"][:10])
    return daily == _workdays(s, f)


def write_split_files(parsed: Dict[str, Any], folder: str) -> List[str]:
    os.makedirs(folder, exist_ok=True)
    written = []

    # Orçamento
    wb = openpyxl.Workbook()
    ws = _new_sheet(wb, "Orçamento", COLUMNS["orcamento"], first=True)
    for it in parsed["budget_items"].values():
        ws.append([it["level"], it["code"], it.get("parent_code"), it["description"], it.get("unit"),
                   it.get("quantity") or None, it.get("unit_price") or None, it["total_price"],
                   it.get("accum_measured_pct") or None])
    wb.save(os.path.join(folder, FILES["orcamento"]))
    written.append(FILES["orcamento"])

    # Cronograma
    tasks = parsed.get("tasks") or {}
    if tasks:
        wb = openpyxl.Workbook()
        ws = _new_sheet(wb, "Cronograma", COLUMNS["cronograma"], first=True)
        ws_d = None
        for t in tasks.values():
            daily = t.get("daily") or {}
            ws.append([t.get("id"), t["name"], t.get("duration"),
                       t.get("start") or (min(daily).isoformat() if daily else None),
                       t.get("finish") or (max(daily).isoformat() if daily else None),
                       "; ".join(t.get("predecessors") or []), t.get("lote_mae"), t.get("lot")])
            if daily and not _is_uniform(t):
                if ws_d is None:
                    ws_d = _new_sheet(wb, "Diario", COLUMNS["cronograma_diario"])
                for dt in sorted(daily):
                    ws_d.append([t.get("id"), t["name"], dt, daily[dt]])
        wb.save(os.path.join(folder, FILES["cronograma"]))
        written.append(FILES["cronograma"])

    # Distribuição
    links = parsed.get("all_links") or []
    if links:
        wb = openpyxl.Workbook()
        ws = _new_sheet(wb, "Distribuição", COLUMNS["distribuicao"], first=True)
        for l in links:
            ws.append([l["wbs_code"], l["task_name"], l.get("duration") or None, l.get("allocated_val") or None])
        wb.save(os.path.join(folder, FILES["distribuicao"]))
        written.append(FILES["distribuicao"])

    # Medição
    if parsed.get("history_monthly") or parsed.get("item_monthly_measurements") or parsed.get("item_measurements"):
        wb = openpyxl.Workbook()
        ws = _new_sheet(wb, "Corte", COLUMNS["medicao_corte"], first=True)
        ws.append([parsed.get("cutoff_med_num"), parsed.get("cutoff_date")])
        ws = _new_sheet(wb, "Historico", COLUMNS["medicao_historico"])
        for h in parsed.get("history_monthly") or []:
            ws.append([h["med_num"], datetime.date.fromisoformat(h["date"][:10]), h["pct"]])
        ws = _new_sheet(wb, "Itens", COLUMNS["medicao_itens"])
        for code, months in (parsed.get("item_monthly_measurements") or {}).items():
            for n in sorted(months):
                m = months[n]
                if m.get("previsto") or m.get("realizado"):
                    ws.append([code, n, m.get("previsto", 0.0), m.get("realizado", 0.0)])
        ws = _new_sheet(wb, "Acumulado", COLUMNS["medicao_acumulado"])
        for code, v in (parsed.get("item_measurements") or {}).items():
            ws.append([code, v])
        wb.save(os.path.join(folder, FILES["medicao"]))
        written.append(FILES["medicao"])

    return written


# ---------------------------------------------------------------------------
# Planilha única da "Nova Obra": as mesmas abas dos 4 arquivos, num só Excel
# ---------------------------------------------------------------------------

COMBINED_SHEETS = {
    "orcamento": [("Orçamento", "Orçamento")],
    "cronograma": [("Cronograma", "Cronograma"), ("Diario", "Cronograma Diario")],
    "distribuicao": [("Distribuição", "Distribuição")],
    "medicao": [("Corte", "Medição Corte"), ("Historico", "Medição Historico"),
                ("Itens", "Medição Itens"), ("Acumulado", "Medição Acumulado")],
}

_INSTRUCTIONS = [
    "Modelo da obra completa. Cada aba corresponde a uma tela do sistema; o cabeçalho fica na linha 1.",
    "Obrigatória: Orçamento. As demais podem ficar vazias e ser importadas depois, como versões em cada tela.",
    "Orçamento: níveis 1 a 5 da EAP. Código Pai é opcional (deduzido pelo nível).",
    "Cronograma: ID único, datas de início/término e predecessoras (ex.: 4FS, 2SS+3d, '12FS; 11SS+5d').",
    "Distribuição: uma linha por vínculo entre o código do item nível 5 e o nome exato da atividade do cronograma.",
    "Medição Corte: nº e data da medição atual. Histórico: realizado mensal da obra. Itens: % do mês de cada item. "
    "Acumulado: % acumulado de cada item.",
    "Percentuais podem ser fração (0,85) ou número (85).",
]


def _copy_sheet(src_ws, dst_wb, title: str, first: bool):
    rows = src_ws.iter_rows(values_only=True)
    header = next(rows, None) or ()
    ws = _new_sheet(dst_wb, title, [h for h in header if h is not None], first=first)
    for r in rows:
        ws.append(list(r))


def write_combined_workbook(parsed: Dict[str, Any], path: str):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        write_split_files(parsed, tmp)
        out = openpyxl.Workbook()
        first = True
        for domain, sheets in COMBINED_SHEETS.items():
            src = os.path.join(tmp, FILES[domain])
            wb = openpyxl.load_workbook(src) if os.path.exists(src) else None
            for split_title, combined_title in sheets:
                ws = _sheet(wb, split_title) if wb else None
                if ws is not None:
                    _copy_sheet(ws, out, combined_title, first)
                elif split_title != "Diario":
                    # Aba vazia só com cabeçalho, para o usuário preencher
                    key = {"Corte": "medicao_corte", "Historico": "medicao_historico", "Itens": "medicao_itens",
                           "Acumulado": "medicao_acumulado"}.get(split_title, domain)
                    _new_sheet(out, combined_title, COLUMNS[key], first=first)
                else:
                    continue
                first = False
        ws = out.create_sheet("Instruções")
        for line in _INSTRUCTIONS:
            ws.append([line])
        ws.column_dimensions["A"].width = 120
        out.save(path)


def is_combined_workbook(path: str) -> bool:
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        ws = _sheet(wb, "Orçamento")
        if ws is None:
            return False
        header = [norm(str(h)).strip() for h in next(ws.iter_rows(max_row=1, values_only=True)) if h is not None]
        return all(norm(c) in header for c in ("Nível", "Código", "Descrição", "Preço Total"))
    except Exception:
        return False
    finally:
        wb.close()


def _has_data(ws) -> bool:
    if ws is None:
        return False
    return any(any(v not in (None, "") for v in r) for r in ws.iter_rows(min_row=2, values_only=True))


def split_combined_workbook(path: str, folder: str) -> List[str]:
    os.makedirs(folder, exist_ok=True)
    src = openpyxl.load_workbook(path, read_only=True, data_only=True)
    written = []
    try:
        for domain, sheets in COMBINED_SHEETS.items():
            present = [(s, c) for s, c in sheets if _has_data(_sheet(src, c))]
            if not present:
                continue
            out = openpyxl.Workbook()
            for i, (split_title, combined_title) in enumerate(present):
                _copy_sheet(_sheet(src, combined_title), out, split_title, first=(i == 0))
            out.save(os.path.join(folder, FILES[domain]))
            written.append(FILES[domain])
    finally:
        src.close()
    return written
