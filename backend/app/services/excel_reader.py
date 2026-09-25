import openpyxl
import datetime
import unicodedata
import os
import pickle
import hashlib
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache")

def get_cache_path(file_path: str) -> str:
    try:
        stat = os.stat(file_path)
        key_str = f"{os.path.normpath(file_path)}_{stat.st_size}_{stat.st_mtime}"
    except Exception:
        key_str = os.path.normpath(file_path)
    key_hash = hashlib.md5(key_str.encode("utf-8")).hexdigest()
    base_name = os.path.splitext(os.path.basename(file_path))[0][:20]
    safe_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-'))
    return os.path.join(CACHE_DIR, f"{safe_name}_{key_hash}.pkl")

def norm(text: str) -> str:
    if not text:
        return ""
    return unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8').lower()

def try_float(val, default=0.0) -> float:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).strip().replace(',', '.')
        return float(s) if s else default
    except (ValueError, TypeError):
        return default

def parse_date_cell(val) -> Optional[datetime.date]:
    if val is None:
        return None
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, (int, float)):
        if val > 30000:
            return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(val))
    if isinstance(val, str):
        val_s = val.strip()
        if not val_s or val_s == "-":
            return None
        if val_s.isdigit() and int(val_s) > 30000:
            return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(val_s))
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%Y/%m/%d"]:
            try:
                return datetime.datetime.strptime(val_s[:10], fmt).date()
            except Exception:
                pass
    return None

def try_pct(val, default=0.0) -> float:
    if val is None or val == "":
        return default
    if isinstance(val, (int, float)):
        f = float(val)
        return f / 100.0 if f > 1.0 else f
    try:
        s = str(val).strip().replace('%', '').replace(',', '.')
        f = float(s)
        return f / 100.0 if f > 1.0 else f
    except (ValueError, TypeError):
        return default

def get_sheet_by_keyword(wb, keyword: str):
    kw = norm(keyword)
    for s in wb.sheetnames:
        if kw in norm(s):
            return wb[s]
    return None

def parse_excel_project(file_path: str) -> Dict[str, Any]:
    """
    Parses a Piemonte Físico-Financeiro Excel spreadsheet in high-speed read_only mode.
    Supports BOTH:
      1. Standard Replanejamento Template (.xlsx with Level 1-5 + Level 6 links in Orçamento & Cronograma tab)
      2. Legacy Piemonte Monolithic Multi-Tab Spreadsheets (with persistent disk caching)
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = get_cache_path(file_path)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"[CACHE] Error loading {cache_path}: {e}")

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    
    # 1. Parse Orçamento
    ws_orc = get_sheet_by_keyword(wb, 'orcamento')
    if ws_orc is None:
        ws_orc = wb.active

    budget_items: Dict[str, Dict[str, Any]] = {}
    project_name = "Projeto"
    total_budget = 0.0
    l1_code = None
    links_by_l5: Dict[str, List[Dict[str, Any]]] = {}
    all_links: List[Dict[str, Any]] = []
    item_measurements: Dict[str, float] = {}

    # Check for columnar header row in ws_orc
    header_row_idx = None
    col_map = {}
    sample_rows = list(ws_orc.iter_rows(min_row=1, max_row=5, values_only=True))
    for r_idx, r in enumerate(sample_rows, start=1):
        norm_cells = [norm(str(c)) if c is not None else "" for c in r]
        if any("nivel" in c or "level" in c for c in norm_cells) and any("descri" in c for c in norm_cells):
            header_row_idx = r_idx
            for c_idx, c_val in enumerate(norm_cells):
                if "nivel" in c_val or "level" in c_val:
                    col_map["level"] = c_idx
                elif "codig" in c_val or "code" in c_val or "wbs" in c_val or "edt" in c_val:
                    col_map["code"] = c_idx
                elif "descri" in c_val:
                    col_map["description"] = c_idx
                elif "unid" in c_val or "unit" in c_val or "und" in c_val:
                    col_map["unit"] = c_idx
                elif "quant" in c_val or "qtd" in c_val:
                    col_map["quantity"] = c_idx
                elif "unitari" in c_val or "p.u" in c_val or "pu" in c_val:
                    col_map["unit_price"] = c_idx
                elif "total" in c_val or "p.t" in c_val or "pt" in c_val or "preco" in c_val:
                    col_map["total_price"] = c_idx
                elif "medicao" in c_val or "medido" in c_val or "realiz" in c_val or "%" in c_val:
                    col_map["measured_pct"] = c_idx
                elif "durac" in c_val:
                    col_map["duration"] = c_idx
                elif "alocad" in c_val or "valor" in c_val:
                    col_map["allocated_val"] = c_idx
            break

    if header_row_idx is not None and "level" in col_map and "description" in col_map:
        # Standard Columnar / Template Mode
        current_l5 = None
        current_l1 = None
        current_l2 = None
        current_l3 = None
        current_l4 = None

        for row in ws_orc.iter_rows(min_row=header_row_idx + 1, values_only=True):
            lvl_val = row[col_map["level"]] if col_map.get("level") is not None and col_map["level"] < len(row) else None
            if lvl_val is None:
                continue
            try:
                lvl = int(lvl_val)
            except (ValueError, TypeError):
                continue

            desc_raw = row[col_map["description"]] if col_map.get("description") is not None and col_map["description"] < len(row) else ""
            desc = str(desc_raw or "").strip()
            # Clean leading indent characters like "↳" or bullet points
            if desc.startswith("↳"):
                desc = desc[1:].strip()
            elif desc.startswith("->"):
                desc = desc[2:].strip()

            code_raw = row[col_map["code"]] if col_map.get("code") is not None and col_map["code"] < len(row) else None
            code_str = str(code_raw).strip() if code_raw is not None and str(code_raw).strip() != "" else ""

            if lvl == 6:
                # Level 6 link directly under current Level 5 item!
                if current_l5 and desc:
                    dur_val = row[col_map["duration"]] if col_map.get("duration") is not None and col_map["duration"] < len(row) else None
                    val_val = row[col_map["allocated_val"]] if col_map.get("allocated_val") is not None and col_map["allocated_val"] < len(row) else None
                    link_obj = {
                        "wbs_code": current_l5,
                        "task_name": desc,
                        "duration": try_float(dur_val),
                        "allocated_val": try_float(val_val)
                    }
                    if current_l5 not in links_by_l5:
                        links_by_l5[current_l5] = []
                    links_by_l5[current_l5].append(link_obj)
                    all_links.append(link_obj)
                continue

            # Level 1 to 5 Budget items
            if not code_str:
                code_str = str(len(budget_items) + 1)

            parent_code = None
            if lvl == 1:
                current_l1 = code_str
                project_name = desc or "Projeto"
            elif lvl == 2:
                current_l2 = code_str
                parent_code = current_l1 or "1"
            elif lvl == 3:
                current_l3 = code_str
                parent_code = current_l2 or current_l1 or "1"
            elif lvl == 4:
                current_l4 = code_str
                parent_code = current_l3 or current_l2 or current_l1 or "1"
            elif lvl == 5:
                current_l5 = code_str
                parent_code = current_l4 or current_l3 or current_l2 or current_l1 or "1"

            und = row[col_map["unit"]] if col_map.get("unit") is not None and col_map["unit"] < len(row) else None
            qtd = row[col_map["quantity"]] if col_map.get("quantity") is not None and col_map["quantity"] < len(row) else None
            pu = row[col_map["unit_price"]] if col_map.get("unit_price") is not None and col_map["unit_price"] < len(row) else None
            pt = row[col_map["total_price"]] if col_map.get("total_price") is not None and col_map["total_price"] < len(row) else None
            p_total = try_float(pt)
            if lvl == 1 and p_total > 0:
                total_budget = p_total

            med_pct = 0.0
            if col_map.get("measured_pct") is not None and col_map["measured_pct"] < len(row):
                med_pct = try_pct(row[col_map["measured_pct"]])
                if med_pct > 0:
                    item_measurements[code_str] = med_pct

            budget_items[code_str] = {
                "code": code_str,
                "description": desc,
                "level": lvl,
                "parent_code": parent_code,
                "unit": str(und).strip() if und else None,
                "quantity": try_float(qtd),
                "unit_price": try_float(pu),
                "total_price": p_total,
                "accum_measured_pct": med_pct
            }
    else:
        # Legacy Piemonte format
        for row in ws_orc.iter_rows(values_only=True, min_row=4):
            code = row[6]
            desc = row[7]
            level = row[4]
            pt = row[11]
            und = row[8] if len(row) > 8 else None
            qtd = row[9] if len(row) > 9 else None
            pu = row[10] if len(row) > 10 else None

            if code is not None and level is not None:
                code_str = str(code).strip()
                lvl = int(level)
                parent_code = None
                if lvl == 1:
                    l1_code = code_str
                elif lvl == 2:
                    parent_code = l1_code or "1"
                elif lvl == 3:
                    parent_code = str(row[0]).strip() if (len(row) > 0 and row[0]) else (l1_code or "1")
                elif lvl == 4:
                    parent_code = str(row[1]).strip() if (len(row) > 1 and row[1]) else (str(row[0]).strip() if len(row) > 0 and row[0] else (l1_code or "1"))
                elif lvl == 5:
                    parent_code = str(row[2]).strip() if (len(row) > 2 and row[2]) else (str(row[1]).strip() if len(row) > 1 and row[1] else (l1_code or "1"))
                else:
                    parts = code_str.split('.')
                    parent_code = '.'.join(parts[:-1]) if len(parts) > 1 else (l1_code or "1")

                p_total = try_float(pt)
                if lvl == 1:
                    project_name = str(desc or "Projeto").strip()
                    total_budget = p_total

                budget_items[code_str] = {
                    "code": code_str,
                    "description": str(desc or "").strip(),
                    "level": lvl,
                    "parent_code": parent_code,
                    "unit": str(und).strip() if und else None,
                    "quantity": try_float(qtd),
                    "unit_price": try_float(pu),
                    "total_price": p_total,
                    "accum_measured_pct": 0.0
                }

    if total_budget <= 0.0:
        total_budget = sum(item["total_price"] for item in budget_items.values() if item["level"] == 5)

    # 2. Parse Cronograma
    ws_crono = get_sheet_by_keyword(wb, 'cronograma')
    tasks: Dict[str, Dict[str, Any]] = {}
    crono_dates: List[tuple] = []
    
    if ws_crono is not None:
        crono_sample = list(ws_crono.iter_rows(min_row=1, max_row=5, values_only=True))
        crono_col_map = {}
        crono_header_idx = None
        for r_idx, r in enumerate(crono_sample, start=1):
            norm_c = [norm(str(c)) if c is not None else "" for c in r]
            if any("ativid" in c or "nome" in c or "task" in c for c in norm_c):
                crono_header_idx = r_idx
                for c_idx, val in enumerate(norm_c):
                    if val in ["id", "cod", "num"]:
                        crono_col_map["id"] = c_idx
                    elif "edt" in val or "wbs" in val or "outline" in val:
                        crono_col_map["wbs"] = c_idx
                    elif "ativid" in val or "nome" in val or "task" in val or "descri" in val:
                        crono_col_map["name"] = c_idx
                    elif "durac" in val or "dias" in val:
                        crono_col_map["duration"] = c_idx
                    elif "inici" in val or "start" in val:
                        crono_col_map["start"] = c_idx
                    elif "termin" in val or "fim" in val or "finish" in val or "end" in val:
                        crono_col_map["finish"] = c_idx
                    elif "predec" in val or "pred" in val:
                        crono_col_map["predecessors"] = c_idx
                    elif "sucess" in val or "succ" in val:
                        crono_col_map["successors"] = c_idx
                    elif "lote mae" in val or "lote_mae" in val:
                        crono_col_map["lote_mae"] = c_idx
                    elif "lote" in val or "paviment" in val:
                        crono_col_map["lot"] = c_idx
                break

        if crono_header_idx is not None and "name" in crono_col_map:
            # Columnar Standard Cronograma Mode
            task_counter = 1
            for row in ws_crono.iter_rows(min_row=crono_header_idx + 1, values_only=True):
                name = row[crono_col_map["name"]] if crono_col_map.get("name") is not None and crono_col_map["name"] < len(row) else None
                if not name:
                    continue
                name_str = str(name).strip()
                t_id = str(row[crono_col_map["id"]]) if crono_col_map.get("id") is not None and crono_col_map["id"] < len(row) and row[crono_col_map["id"]] is not None else str(task_counter)
                dur = try_float(row[crono_col_map["duration"]]) if crono_col_map.get("duration") is not None and crono_col_map["duration"] < len(row) else 1.0
                start_val = row[crono_col_map["start"]] if crono_col_map.get("start") is not None and crono_col_map["start"] < len(row) else None
                finish_val = row[crono_col_map["finish"]] if crono_col_map.get("finish") is not None and crono_col_map["finish"] < len(row) else None
                preds_val = row[crono_col_map["predecessors"]] if crono_col_map.get("predecessors") is not None and crono_col_map["predecessors"] < len(row) else None

                s_d = parse_date_cell(start_val)
                f_d = parse_date_cell(finish_val)
                if not s_d:
                    s_d = datetime.date(2026, 10, 1)
                if not f_d:
                    f_d = s_d + datetime.timedelta(days=max(1, int(dur) - 1))

                preds_list = []
                if preds_val:
                    for p in str(preds_val).replace(';', ',').split(','):
                        p_clean = p.strip()
                        if p_clean:
                            preds_list.append(p_clean)

                daily_vals = {}
                cur = s_d
                while cur <= f_d:
                    if cur.weekday() < 5:
                        daily_vals[cur] = 1.0
                    cur += datetime.timedelta(days=1)
                if not daily_vals:
                    daily_vals[s_d] = 1.0

                task_key = name_str
                if task_key in tasks:
                    task_key = f"{name_str} (#{t_id})"

                tasks[task_key] = {
                    "id": t_id,
                    "name": name_str,
                    "duration": dur,
                    "start": s_d.strftime("%Y-%m-%d"),
                    "finish": f_d.strftime("%Y-%m-%d"),
                    "predecessors": preds_list,
                    "successors": [],
                    "lote_mae": str(row[crono_col_map["lote_mae"]]).strip() if crono_col_map.get("lote_mae") is not None and crono_col_map["lote_mae"] < len(row) and row[crono_col_map["lote_mae"]] else "Geral",
                    "lot": str(row[crono_col_map["lot"]]).strip() if crono_col_map.get("lot") is not None and crono_col_map["lot"] < len(row) and row[crono_col_map["lot"]] else "Geral",
                    "daily": daily_vals
                }
                task_counter += 1
        else:
            # Legacy Piemonte date-matrix format
            row6 = list(ws_crono.iter_rows(min_row=6, max_row=6, values_only=True))[0]
            for c_idx in range(2, len(row6)):
                val = row6[c_idx]
                if isinstance(val, datetime.datetime):
                    crono_dates.append((c_idx, val.date()))
                elif isinstance(val, datetime.date):
                    crono_dates.append((c_idx, val))

            task_counter = 1
            for row in ws_crono.iter_rows(min_row=8, values_only=True):
                name = row[0]
                dur = row[1]
                if not name:
                    continue
                name_str = str(name).strip()
                daily_vals: Dict[datetime.date, float] = {}
                for c_idx, dt in crono_dates:
                    if c_idx < len(row):
                        fval = try_float(row[c_idx])
                        if fval > 0:
                            daily_vals[dt] = fval
                task_key = name_str
                if task_key in tasks:
                    task_key = f"{name_str} (#{task_counter})"
                tasks[task_key] = {
                    "id": str(task_counter),
                    "name": name_str,
                    "duration": try_float(dur),
                    "daily": daily_vals
                }
                task_counter += 1

    # 3. Parse Distribuição (WBS to Tasks links - if separate sheet exists and links not already in ws_orc)
    ws_dist = get_sheet_by_keyword(wb, 'distribuicao')
    if ws_dist is not None:
        current_l5 = None
        for row in ws_dist.iter_rows(min_row=5, values_only=True):
            lvl = row[4] if len(row) > 4 else None
            code = row[6] if len(row) > 6 else None
            desc = row[7] if len(row) > 7 else None
            dur = row[9] if len(row) > 9 else None
            val = row[11] if len(row) > 11 else None
            if lvl == 5 and code:
                current_l5 = str(code).strip()
                if current_l5 not in links_by_l5:
                    links_by_l5[current_l5] = []
            elif lvl == 6 and desc and current_l5:
                link_obj = {
                    "wbs_code": current_l5,
                    "task_name": str(desc).strip(),
                    "duration": try_float(dur),
                    "allocated_val": try_float(val)
                }
                links_by_l5[current_l5].append(link_obj)
                all_links.append(link_obj)

    # 4. Parse Medição
    ws_med = get_sheet_by_keyword(wb, 'medicao')
    cutoff_med_num = 1
    cutoff_date = None
    item_measurements: Dict[str, float] = {}
    history_monthly: List[Dict[str, Any]] = []

    if ws_med is not None:
        r1 = list(ws_med.iter_rows(min_row=1, max_row=1, values_only=True))[0]
        r2 = list(ws_med.iter_rows(min_row=2, max_row=2, values_only=True))[0]
        r3 = list(ws_med.iter_rows(min_row=3, max_row=3, values_only=True))[0]
        r4 = list(ws_med.iter_rows(min_row=4, max_row=4, values_only=True))[0]
        r6 = list(ws_med.iter_rows(min_row=6, max_row=6, values_only=True))[0]
        
        if len(r2) > 11 and r2[11] is not None:
            try:
                cutoff_med_num = int(r2[11])
            except (ValueError, TypeError):
                cutoff_med_num = 1
                
        if len(r2) > 10 and isinstance(r2[10], (datetime.datetime, datetime.date)):
            cutoff_date = r2[10].date() if isinstance(r2[10], datetime.datetime) else r2[10]

        # Use module-level parse_date_cell

        has_previsto = any('PREVISTO' in str(h).upper() for h in r4[12:30] if h)
        item_monthly_measurements: Dict[str, Dict[int, Dict[str, float]]] = {}
        
        # Extract items accumulated realized % and monthly measurements
        for row in ws_med.iter_rows(min_row=6, values_only=True):
            code = row[3]
            if code is not None:
                code_str = str(code).strip()
                accum_r = try_float(row[11] if len(row) > 11 else 0.0)
                item_measurements[code_str] = accum_r
                if code_str in budget_items:
                    budget_items[code_str]["accum_measured_pct"] = accum_r

                # Extract monthly columns for this specific row
                item_monthly_measurements[code_str] = {}
                for c_idx in range(12, len(row)):
                    if c_idx < len(r4):
                        hdr = str(r4[c_idx]).strip().upper() if r4[c_idx] else ""
                        med_idx = ((c_idx - 12) // 2 + 1) if has_previsto else (c_idx - 12 + 1)
                        if med_idx not in item_monthly_measurements[code_str]:
                            item_monthly_measurements[code_str][med_idx] = {"previsto": 0.0, "realizado": 0.0}
                        val_raw = try_float(row[c_idx])
                        if hdr == 'PREVISTO':
                            item_monthly_measurements[code_str][med_idx]["previsto"] = val_raw
                        elif hdr == 'REALIZADO' or not has_previsto:
                            item_monthly_measurements[code_str][med_idx]["realizado"] = val_raw

        # Extract monthly history from row 6
        for c_idx in range(12, len(r6)):
            hdr = str(r4[c_idx]).strip().upper() if c_idx < len(r4) and r4[c_idx] else ""
            if ('REALIZADO' in hdr) or (not has_previsto and c_idx < len(r4)):
                med_idx = ((c_idx - 12) // 2 + 1) if has_previsto else (c_idx - 12 + 1)
                m_dt = None
                for rx in [r2, r3, r1]:
                    if c_idx < len(rx):
                        d_cand = parse_date_cell(rx[c_idx])
                        if d_cand:
                            m_dt = d_cand
                            break

                if not m_dt and cutoff_date and cutoff_med_num:
                    m_dt = cutoff_date - relativedelta(months=(cutoff_med_num - med_idx))

                val_pct = try_float(r6[c_idx])
                if m_dt and med_idx <= cutoff_med_num:
                    history_monthly.append({
                        "med_num": med_idx,
                        "date": m_dt.strftime("%Y-%m-%d"),
                        "pct": val_pct,
                        "value": val_pct * total_budget
                    })

    wb.close()

    # Determine start and end date of schedule based on real project start
    active_dates = [dt for t in tasks.values() for dt, v in t.get("daily", {}).items() if v > 0]
    med_start_date = None
    if history_monthly:
        try:
            med_start_date = datetime.date.fromisoformat(history_monthly[0]["date"][:10])
        except Exception:
            pass

    if med_start_date:
        min_date = med_start_date
    elif active_dates:
        min_date = min(active_dates)
    else:
        min_date = crono_dates[0][1] if crono_dates else datetime.date(2025, 10, 1)

    max_date = max(active_dates) if active_dates else (crono_dates[-1][1] if crono_dates else datetime.date(2029, 10, 1))

    result = {
        "project_name": project_name,
        "total_budget": total_budget,
        "start_date": min_date,
        "end_date": max_date,
        "cutoff_med_num": cutoff_med_num,
        "cutoff_date": cutoff_date,
        "budget_items": budget_items,
        "tasks": tasks,
        "links_by_l5": links_by_l5,
        "all_links": all_links,
        "item_measurements": item_measurements,
        "item_monthly_measurements": item_monthly_measurements if ws_med is not None else {},
        "history_monthly": history_monthly
    }

    try:
        with open(cache_path, "wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        print(f"[CACHE] Error writing {cache_path}: {e}")

    return result
