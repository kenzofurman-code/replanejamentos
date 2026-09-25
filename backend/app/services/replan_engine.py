import calendar
import datetime
import re
import unicodedata
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional, Tuple

def is_workday(d: datetime.date) -> bool:
    return d.weekday() < 5

def next_workday(d: datetime.date) -> datetime.date:
    cur = d
    while not is_workday(cur):
        cur += datetime.timedelta(days=1)
    return cur

def prev_workday(d: datetime.date) -> datetime.date:
    cur = d
    while not is_workday(cur):
        cur -= datetime.timedelta(days=1)
    return cur

def add_workdays(start_d: datetime.date, workdays: int) -> datetime.date:
    cur = start_d
    if workdays == 0:
        return next_workday(cur)
    step = 1 if workdays > 0 else -1
    remaining = abs(workdays)
    while remaining > 0:
        cur += datetime.timedelta(days=step)
        if is_workday(cur):
            remaining -= 1
    return cur

def calc_finish_date(start_d: datetime.date, duration_days: float) -> datetime.date:
    dur = max(1, int(round(duration_days)))
    cur = next_workday(start_d)
    if dur == 1:
        return cur
    return add_workdays(cur, dur - 1)

def calc_start_date(finish_d: datetime.date, duration_days: float) -> datetime.date:
    dur = max(1, int(round(duration_days)))
    cur = prev_workday(finish_d)
    if dur == 1:
        return cur
    return add_workdays(cur, -(dur - 1))

def calc_workdays_between(start_d: datetime.date, finish_d: datetime.date) -> float:
    if finish_d < start_d:
        return 1.0
    cur, count = start_d, 0
    while cur <= finish_d:
        if is_workday(cur):
            count += 1
        cur += datetime.timedelta(days=1)
    return float(max(1, count))

def build_daily_workdays(start_d: datetime.date, finish_d: datetime.date) -> Dict[datetime.date, float]:
    daily = {}
    cur = start_d
    while cur <= finish_d:
        if is_workday(cur):
            daily[cur] = 1.0
        cur += datetime.timedelta(days=1)
    if not daily:
        daily[start_d] = 1.0
    return daily

def parse_predecessor_item(pred_item: Any) -> Optional[Tuple[str, str, int]]:
    if not pred_item:
        return None
    s = str(pred_item).strip()
    if not s or s == "-":
        return None
    m = re.match(r'^(\d+)\s*(FS|SS|FF|SF)?\s*([+-]\s*\d+)?d?$', s, re.IGNORECASE)
    if m:
        p_id = m.group(1)
        rel_type = (m.group(2) or 'FS').upper()
        lag_str = m.group(3)
        lag = int(lag_str.replace(' ', '')) if lag_str else 0
        return (p_id, rel_type, lag)
    m2 = re.match(r'^(\d+)', s)
    if m2:
        return (m2.group(1), 'FS', 0)
    return None

def parse_predecessors_list(raw_preds: Any) -> List[Tuple[str, str, int]]:
    items = []
    if isinstance(raw_preds, list):
        for elem in raw_preds:
            if isinstance(elem, str) and (',' in elem or ';' in elem):
                subparts = re.split(r'[,;]', elem)
                for sp in subparts:
                    p = parse_predecessor_item(sp)
                    if p:
                        items.append(p)
            else:
                p = parse_predecessor_item(elem)
                if p:
                    items.append(p)
    elif isinstance(raw_preds, str):
        subparts = re.split(r'[,;]', raw_preds)
        for sp in subparts:
            p = parse_predecessor_item(sp)
            if p:
                items.append(p)
    return items

def propagate_schedule_dependencies(tasks: Dict[str, Any]) -> None:
    """
    Critical Path Method (CPM) Forward Pass and Dependency Propagation Engine.
    Enforces predecessor constraints (FS, SS, FF, SF + lags), pushes successor tasks forward,
    recalculates workdays, finish dates, daily work distribution, and summary task rollups.
    """
    tasks_by_id = {str(t.get("id")): t for t in tasks.values() if t.get("id")}
    
    # 1. Synchronize successors based on current predecessors
    succ_map: Dict[str, List[str]] = {t_id: [] for t_id in tasks_by_id}
    for t_id, t in tasks_by_id.items():
        preds = parse_predecessors_list(t.get("predecessors"))
        for p_id, rtype, lag in preds:
            if p_id in succ_map and t_id not in succ_map[p_id]:
                succ_map[p_id].append(t_id)
    
    for t_id, t in tasks_by_id.items():
        t["successors"] = list(succ_map.get(t_id, []))

    # 2. Iterative CPM forward pass relaxation
    changed = True
    passes = 0
    max_passes = min(100, max(15, len(tasks_by_id)))

    while changed and passes < max_passes:
        changed = False
        passes += 1
        for t_id, t in tasks_by_id.items():
            if t.get("is_summary"):
                continue

            preds = parse_predecessors_list(t.get("predecessors"))
            if not preds:
                continue

            t_start_str = t.get("start")
            t_finish_str = t.get("finish")
            if not t_start_str or t_start_str == "-":
                continue

            try:
                t_start = datetime.date.fromisoformat(str(t_start_str)[:10])
            except Exception:
                continue

            dur = try_float(t.get("duration"), default=1.0)
            if dur <= 0:
                if t_finish_str and t_finish_str != "-":
                    try:
                        dur = calc_workdays_between(t_start, datetime.date.fromisoformat(str(t_finish_str)[:10]))
                    except Exception:
                        dur = 1.0
                else:
                    dur = 1.0
            t["duration"] = dur

            cur_req = t_start
            for p_id, rtype, lag in preds:
                p_task = tasks_by_id.get(p_id)
                if not p_task:
                    continue
                pF_str = p_task.get("finish")
                pS_str = p_task.get("start")
                if not pF_str or not pS_str or pF_str == "-" or pS_str == "-":
                    continue
                try:
                    pF = datetime.date.fromisoformat(str(pF_str)[:10])
                    pS = datetime.date.fromisoformat(str(pS_str)[:10])
                except Exception:
                    continue

                if rtype == "FS":
                    req = add_workdays(pF, 1 + lag)
                elif rtype == "SS":
                    req = add_workdays(pS, lag)
                elif rtype == "FF":
                    target_finish = add_workdays(pF, lag)
                    req = calc_start_date(target_finish, dur)
                elif rtype == "SF":
                    target_finish = add_workdays(pS, lag)
                    req = calc_start_date(target_finish, dur)
                else:
                    req = add_workdays(pF, 1 + lag)

                if req > cur_req:
                    cur_req = req

            if cur_req > t_start:
                t["start"] = cur_req.strftime("%Y-%m-%d")
                new_f = calc_finish_date(cur_req, dur)
                t["finish"] = new_f.strftime("%Y-%m-%d")
                t["daily"] = build_daily_workdays(cur_req, new_f)
                changed = True

    # 3. Rollup summary tasks from deepest outline_level to root
    summaries = [t for t in tasks_by_id.values() if t.get("is_summary")]
    summaries.sort(key=lambda x: int(x.get("outline_level") or 1), reverse=True)

    for s_task in summaries:
        s_id = str(s_task.get("id"))
        s_outline = str(s_task.get("outline") or "")
        children = [
            c for c in tasks_by_id.values()
            if str(c.get("parent_id")) == s_id or
            (s_outline and c.get("outline") and c["outline"].startswith(s_outline + "."))
        ]
        if children:
            valid_starts = []
            valid_finishes = []
            for c in children:
                if c.get("start") and c["start"] != "-":
                    try:
                        valid_starts.append(datetime.date.fromisoformat(str(c["start"])[:10]))
                    except Exception:
                        pass
                if c.get("finish") and c["finish"] != "-":
                    try:
                        valid_finishes.append(datetime.date.fromisoformat(str(c["finish"])[:10]))
                    except Exception:
                        pass
            if valid_starts and valid_finishes:
                min_s = min(valid_starts)
                max_f = max(valid_finishes)
                s_task["start"] = min_s.strftime("%Y-%m-%d")
                s_task["finish"] = max_f.strftime("%Y-%m-%d")
                s_task["duration"] = calc_workdays_between(min_s, max_f)
                s_task["daily"] = build_daily_workdays(min_s, max_f)


def norm(text: str) -> str:
    if not text:
        return ""
    return unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8').lower().strip()

def try_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def wbs_sort_key(code: Any, item: Optional[Dict[str, Any]] = None):
    # Level 1 always first
    if item and item.get("level") == 1:
        return (-1, [0])
    code_str = str(code).strip()
    if code_str == "1":
        return (-1, [0])
    parts = []
    for p in code_str.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(p)
    return (0, parts)


def generate_cycles(
    start_date: datetime.date,
    end_date: datetime.date,
    cycle_start_day: int = 21,
    cycle_end_day: int = 20,
    cutoff_med_num: int = 11,
    max_months: int = 60
) -> List[Dict[str, Any]]:
    # Rule: strictly 1 month - 1 day
    if cycle_start_day <= 1:
        cycle_start_day = 1
        cycle_end_day = 31
    else:
        cycle_end_day = cycle_start_day - 1

    cycles = []
    curr_end_month = datetime.date(start_date.year, start_date.month, 1)

    for i in range(1, max_months + 1):
        m_end_year = curr_end_month.year
        m_end_month = curr_end_month.month

        if cycle_start_day == 1:
            c_start = datetime.date(m_end_year, m_end_month, 1)
            last_day = calendar.monthrange(m_end_year, m_end_month)[1]
            c_end = datetime.date(m_end_year, m_end_month, last_day)
        else:
            prev_m = curr_end_month - relativedelta(months=1)
            last_day_prev = calendar.monthrange(prev_m.year, prev_m.month)[1]
            c_start = datetime.date(prev_m.year, prev_m.month, min(cycle_start_day, last_day_prev))
            last_day_curr = calendar.monthrange(m_end_year, m_end_month)[1]
            c_end = datetime.date(m_end_year, m_end_month, min(cycle_end_day, last_day_curr))

        month_label = c_end.strftime("%b/%y").capitalize()
        cycles.append({
            "num": i,
            "name": f"Mês {i}",
            "period_label": month_label,
            "full_label": f"Mês {i} ({month_label})",
            "start": c_start,
            "end": c_end,
            "is_past": (i <= cutoff_med_num)
        })

        if c_end >= end_date and i >= cutoff_med_num + 3:
            break

        curr_end_month += relativedelta(months=1)

    return cycles

def run_replan_calculation(
    parsed_data: Dict[str, Any],
    cycle_start_day: int = 21,
    cycle_end_day: int = 20,
    cutoff_med_num: Optional[int] = None,
    custom_measurements: Optional[Dict[str, float]] = None,
    custom_measurements_l5: Optional[Dict[str, float]] = None,
    custom_measurements_l6: Optional[Dict[str, Dict[str, float]]] = None,
    custom_monthly_medicao: Optional[Dict[str, Dict[str, float]]] = None,
    custom_monthly_medicao_l6: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
    custom_weights: Optional[Dict[str, float]] = None,
    schedule_tasks_override: Optional[Dict[str, Any]] = None,
    custom_schedule_overrides: Optional[Dict[str, Any]] = None,
    custom_links_by_l5: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> Dict[str, Any]:
    budget_items = parsed_data["budget_items"]
    raw_tasks = schedule_tasks_override if schedule_tasks_override is not None else parsed_data["tasks"]
    tasks = dict(raw_tasks)

    # Apply custom schedule overrides if provided (from Gantt drag or Task Drawer)
    if custom_schedule_overrides:
        tasks_by_id = {str(t_info.get("id")): (k, t_info) for k, t_info in tasks.items() if t_info.get("id")}
        tasks_by_norm_key = {norm(k): (k, t_info) for k, t_info in tasks.items()}
        tasks_by_norm_name = {norm(t_info.get("name") or ""): (k, t_info) for k, t_info in tasks.items() if t_info.get("name")}

        for ovr_key, ovr_data in custom_schedule_overrides.items():
            if not isinstance(ovr_data, dict):
                continue
            matched = None
            orig_k = None
            ovr_id = str(ovr_data.get("id") or ovr_key)
            if ovr_id in tasks_by_id:
                orig_k, matched = tasks_by_id[ovr_id]
            elif ovr_key in tasks:
                orig_k, matched = ovr_key, tasks[ovr_key]
            elif norm(ovr_key) in tasks_by_norm_key:
                orig_k, matched = tasks_by_norm_key[norm(ovr_key)]
            elif norm(ovr_key) in tasks_by_norm_name:
                orig_k, matched = tasks_by_norm_name[norm(ovr_key)]
            elif ovr_data.get("name"):
                n_name = norm(ovr_data["name"])
                if n_name in tasks_by_norm_name:
                    orig_k, matched = tasks_by_norm_name[n_name]

            if matched and orig_k:
                t_clone = dict(matched)
                t_clone["daily"] = dict(matched.get("daily", {}))

                if "predecessors" in ovr_data and ovr_data["predecessors"] is not None:
                    t_clone["predecessors"] = ovr_data["predecessors"]

                new_dur = ovr_data.get("duration")
                new_start_str = ovr_data.get("start_date")
                new_end_str = ovr_data.get("end_date")

                if new_dur is not None:
                    try:
                        t_clone["duration"] = max(1.0, float(new_dur))
                    except (ValueError, TypeError):
                        pass

                new_start_d = None
                new_end_d = None
                if new_start_str and new_start_str != "-":
                    try:
                        new_start_d = datetime.date.fromisoformat(str(new_start_str)[:10])
                        t_clone["start"] = new_start_d.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                if new_end_str and new_end_str != "-":
                    try:
                        new_end_d = datetime.date.fromisoformat(str(new_end_str)[:10])
                        t_clone["finish"] = new_end_d.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                # If no start_date was provided, try existing daily dates
                if not new_start_d and t_clone.get("start") and t_clone["start"] != "-":
                    try:
                        new_start_d = datetime.date.fromisoformat(str(t_clone["start"])[:10])
                    except Exception:
                        pass
                if not new_start_d and t_clone.get("daily"):
                    sorted_dts = sorted(t_clone["daily"].keys())
                    new_start_d = sorted_dts[0]
                    t_clone["start"] = new_start_d.strftime("%Y-%m-%d")

                if new_start_d:
                    dur_days = float(t_clone.get("duration", 1.0))
                    if new_end_d and (new_dur is None or (ovr_data.get("end_date") and not ovr_data.get("duration"))):
                        t_clone["finish"] = new_end_d.strftime("%Y-%m-%d")
                        t_clone["duration"] = calc_workdays_between(new_start_d, new_end_d)
                    else:
                        new_end_d = calc_finish_date(new_start_d, dur_days)
                        t_clone["finish"] = new_end_d.strftime("%Y-%m-%d")
                        t_clone["duration"] = dur_days

                    t_clone["daily"] = build_daily_workdays(new_start_d, new_end_d)

                tasks[orig_k] = t_clone

    # Enforce Predecessor CPM Forward Pass Propagation
    propagate_schedule_dependencies(tasks)

    links_by_l5 = dict(parsed_data.get("links_by_l5", {}))
    if custom_links_by_l5:
        for l5_k, l_list in custom_links_by_l5.items():
            links_by_l5[l5_k] = l_list
    item_measurements = parsed_data.get("item_measurements", {})
    item_monthly_measurements = parsed_data.get("item_monthly_measurements", {})
    history_monthly = parsed_data.get("history_monthly", [])

    # Merge custom measurements
    c_l5 = dict(custom_measurements_l5 or custom_measurements or {})
    c_l6 = dict(custom_measurements_l6 or {})
    c_m5 = dict(custom_monthly_medicao or {})
    c_m6 = dict(custom_monthly_medicao_l6 or {})

    tasks_by_norm = {norm(t_info.get("name") or k): t_info for k, t_info in tasks.items()}

    def get_task_schedule_duration(t_name: str, default_l_dur: float = 0.0):
        matched_t = tasks.get(t_name) or tasks_by_norm.get(norm(t_name))
        if matched_t:
            dur = try_float(matched_t.get("duration"), default=0.0)
            if dur <= 0:
                dur = float(len([dt for dt, v in matched_t.get("daily", {}).items() if v > 0]))
            if dur <= 0:
                dur = try_float(default_l_dur, default=0.0)
            return dur, matched_t
        # If not found in schedule, duration MUST be 0.0
        return 0.0, None

    # Calculate effective measurements for each Level 5 code
    effective_l5_measurements: Dict[str, float] = {}
    effective_l5_sources: Dict[str, str] = {}

    for code, item in budget_items.items():
        if item["level"] != 5:
            continue
        linked = links_by_l5.get(code, [])
        l_durs = [get_task_schedule_duration(l["task_name"], l.get("duration"))[0] for l in linked]
        tot_d = sum(l_durs)

        if code in c_l6 and c_l6[code]:
            # Priority 1: Level 6 child tasks inputs -> weighted rollup
            l6_dict = c_l6[code]
            w_sum = 0.0
            for idx, l in enumerate(linked):
                t_name = l["task_name"]
                t_dur = l_durs[idx]
                t_val = float(l6_dict.get(t_name, 0.0))
                if t_val > 1.0:
                    t_val /= 100.0
                if tot_d > 0:
                    w_sum += t_val * (t_dur / tot_d)
            effective_l5_measurements[code] = min(1.0, max(0.0, w_sum))
            effective_l5_sources[code] = "l6"
        elif code in c_l5:
            # Priority 2: Direct Level 5 input
            v = float(c_l5[code])
            if v > 1.0:
                v /= 100.0
            effective_l5_measurements[code] = min(1.0, max(0.0, v))
            effective_l5_sources[code] = "l5"
        else:
            # Priority 3: Imported from Excel
            imp_v = item_measurements.get(code, item.get("accum_measured_pct", 0.0))
            if imp_v > 1.0:
                imp_v /= 100.0
            effective_l5_measurements[code] = min(1.0, max(0.0, imp_v))
            effective_l5_sources[code] = "imported"

    if cutoff_med_num is None:
        cutoff_med_num = parsed_data.get("cutoff_med_num", 11)

    start_date = parsed_data["start_date"]
    end_date = parsed_data["end_date"]

    active_starts = []
    active_ends = []
    for t_info in tasks.values():
        for dt, v in t_info.get("daily", {}).items():
            if v > 0:
                active_starts.append(dt)
                active_ends.append(dt)
        if t_info.get("start"):
            try:
                s_d = datetime.date.fromisoformat(str(t_info["start"])[:10])
                active_starts.append(s_d)
            except Exception:
                pass
        if t_info.get("finish"):
            try:
                f_d = datetime.date.fromisoformat(str(t_info["finish"])[:10])
                active_ends.append(f_d)
            except Exception:
                pass

    if not start_date:
        if active_starts:
            start_date = min(active_starts)
        else:
            start_date = datetime.date(2025, 10, 1)

    if active_ends:
        end_date = max(max(active_ends), end_date)

    cycles = generate_cycles(
        start_date=start_date,
        end_date=end_date,
        cycle_start_day=cycle_start_day,
        cycle_end_day=cycle_end_day,
        cutoff_med_num=cutoff_med_num
    )

    cutoff_cycle = cycles[min(cutoff_med_num - 1, len(cycles) - 1)]
    cutoff_date = cutoff_cycle["end"]

    past_cycles = [c for c in cycles if c["is_past"]]
    future_cycles = [c for c in cycles if not c["is_past"]]

    root_code = "1"
    root_item = budget_items.get(root_code) or list(budget_items.values())[0]
    total_proj_budget = root_item["total_price"] or sum(i["total_price"] for i in budget_items.values() if i["level"] == 5) or 1.0

    # 1. CRONOGRAMA
    def get_task_sort_key(item, default_idx):
        t_key, t_info = item
        raw_id = t_info.get("id")
        if raw_id is not None:
            digits = ''.join(c for c in str(raw_id) if c.isdigit())
            if digits:
                try:
                    return int(digits)
                except ValueError:
                    pass
        return default_idx

    task_list = list(tasks.items())
    task_list.sort(key=lambda it: get_task_sort_key(it, 999999))

    cronograma_tasks = []
    for idx, (t_key, t_info) in enumerate(task_list):
        daily_items = [(dt, val) for dt, val in t_info["daily"].items() if val > 0]
        daily_items.sort(key=lambda x: x[0])
        first_d = daily_items[0][0] if daily_items else None
        last_d = daily_items[-1][0] if daily_items else None

        t_name = t_info.get("name") or t_key

        # derive lote_mae and lot
        lote_mae = t_info.get("lote_mae")
        lot = t_info.get("lot")

        if not lote_mae or not lot:
            parts = t_name.split(" - ")
            if len(parts) >= 3:
                lote_mae = lote_mae or parts[1].strip()
                lot = lot or " - ".join(parts[2:]).strip()
            elif len(parts) == 2:
                lote_mae = lote_mae or parts[0].strip()
                lot = lot or parts[1].strip()
            else:
                lote_mae = lote_mae or "Geral"
                lot = lot or "Geral"

        task_id = str(t_info.get("id") or (idx + 1))
        preds = t_info.get("predecessors") or []
        succs = t_info.get("successors") or []

        s_str = t_info.get("start") or (first_d.strftime("%Y-%m-%d") if first_d else "-")
        f_str = t_info.get("finish") or (last_d.strftime("%Y-%m-%d") if last_d else "-")

        is_fut = False
        if f_str and f_str != "-":
            try:
                is_fut = (datetime.date.fromisoformat(f_str[:10]) > cutoff_date)
            except Exception:
                pass
        elif last_d:
            is_fut = (last_d > cutoff_date)

        cronograma_tasks.append({
            "id": task_id,
            "name": t_name,
            "duration": t_info.get("duration", len(daily_items) or 1),
            "start_date": s_str,
            "end_date": f_str,
            "predecessors": preds if isinstance(preds, list) else [str(preds)],
            "successors": succs if isinstance(succs, list) else [str(succs)],
            "lote_mae": lote_mae,
            "lot": lot,
            "is_summary": bool(t_info.get("is_summary", False)),
            "outline": str(t_info.get("outline") or t_info.get("wbs") or ""),
            "wbs": str(t_info.get("wbs") or t_info.get("outline") or ""),
            "outline_level": int(t_info.get("outline_level") or 1),
            "parent_id": str(t_info.get("parent_id")) if t_info.get("parent_id") is not None else None,
            "active_days": len(daily_items),
            "is_future": is_fut
        })

    # 2. ORÇAMENTO
    tab_orcamento_rows = []
    for code, item in sorted(budget_items.items(), key=lambda x: wbs_sort_key(x[0], x[1])):
        tab_orcamento_rows.append({
            "level": item["level"],
            "code": code,
            "description": item["description"],
            "parent_code": item.get("parent_code"),
            "unit": item.get("unit"),
            "quantity": item.get("quantity", 0.0),
            "unit_price": item.get("unit_price", 0.0),
            "total_price": item["total_price"],
            "pct_share": round((item["total_price"] / total_proj_budget) * 100, 3)
        })

    # 3. DISTRIBUIÇÃO (Nível 5 + Nível 6)
    tab_distribuicao_rows = []
    l5_baseline_cycles: Dict[str, Dict[int, float]] = {c: {cy["num"]: 0.0 for cy in cycles} for c in budget_items if budget_items[c]["level"] == 5}

    for code, item in sorted(budget_items.items(), key=lambda x: wbs_sort_key(x[0], x[1])):
        if item["level"] < 5:
            continue
            
        b_val = item["total_price"]
        linked = links_by_l5.get(code, [])
        
        # Calculate task durations based on schedule
        task_info_list = [get_task_schedule_duration(l["task_name"], l.get("duration")) for l in linked]
        durations = [ti[0] for ti in task_info_list]
        total_dur = sum(durations)
        
        l5_cycle_vals = {cy["num"]: 0.0 for cy in cycles}
        child_task_rows = []

        for idx, l in enumerate(linked):
            t_name = l["task_name"]
            t_dur, matched_t = task_info_list[idx]
            t_cycles = {cy["num"]: 0.0 for cy in cycles}

            if matched_t and total_dur > 0 and t_dur > 0:
                weight_pct = (t_dur / total_dur) * 100.0
                allocated_val = b_val * (weight_pct / 100.0)
                t = matched_t
                t_daily_total = sum(t["daily"].values()) or 1.0
                for cy in cycles:
                    if cy["num"] == 1:
                        cy_daily_sum = sum(val for dt, val in t["daily"].items() if dt <= cy["end"])
                    elif cy["num"] == len(cycles):
                        cy_daily_sum = sum(val for dt, val in t["daily"].items() if dt >= cy["start"])
                    else:
                        cy_daily_sum = sum(val for dt, val in t["daily"].items() if cy["start"] <= dt <= cy["end"])

                    if cy_daily_sum > 0:
                        cy_val = allocated_val * (cy_daily_sum / t_daily_total)
                        t_cycles[cy["num"]] = cy_val
                        l5_cycle_vals[cy["num"]] += cy_val
            else:
                # Task not in schedule or zero duration:
                # Duration = 0, Weight = 0, Allocated = 0, no distribution over time
                weight_pct = 0.0
                allocated_val = 0.0

            t_sum = sum(t_cycles.values())
            t_cycle_pcts = {
                cy["num"]: round((t_cycles[cy["num"]] / allocated_val) * 100.0, 2) if allocated_val > 0 else 0.0
                for cy in cycles
            }
            t_cycle_pcts_obra = {
                cy["num"]: round((t_cycles[cy["num"]] / total_proj_budget) * 100.0, 3)
                for cy in cycles
            }

            child_task_rows.append({
                "level": 6,
                "code": f"{code}.{idx+1:03d}",
                "parent_code": code,
                "link_index": idx,
                "task_id": str(matched_t.get("id")) if (matched_t and matched_t.get("id") is not None) else None,
                "description": t_name,
                "duration": t_dur,
                "weight_pct": round(weight_pct, 2),
                "allocated_val": allocated_val,
                "allocated_pct_obra": round((allocated_val / total_proj_budget) * 100.0, 3),
                "cycle_vals": {str(k): round(v, 2) for k, v in t_cycles.items()},
                "cycle_pcts": {str(k): v for k, v in t_cycle_pcts.items()},
                "cycle_pcts_obra": {str(k): v for k, v in t_cycle_pcts_obra.items()},
                "total": round(t_sum, 2),
                "total_pct": round((t_sum / allocated_val) * 100.0, 2) if allocated_val > 0 else 0.0,
                "total_pct_obra": round((t_sum / total_proj_budget) * 100.0, 3)
            })

        l5_baseline_cycles[code] = l5_cycle_vals
        l5_sum = sum(l5_cycle_vals.values())
        l5_cycle_pcts = {
            cy["num"]: round((l5_cycle_vals[cy["num"]] / b_val) * 100.0, 2) if b_val > 0 else 0.0
            for cy in cycles
        }
        l5_cycle_pcts_obra = {
            cy["num"]: round((l5_cycle_vals[cy["num"]] / total_proj_budget) * 100.0, 3)
            for cy in cycles
        }

        tab_distribuicao_rows.append({
            "level": 5,
            "code": code,
            "parent_code": item.get("parent_code"),
            "description": item["description"],
            "link_count": len(linked),
            "duration": total_dur,
            "weight_pct": 100.0 if total_dur > 0 else 0.0,
            "allocated_val": b_val if total_dur > 0 else 0.0,
            "allocated_pct_obra": round((b_val / total_proj_budget) * 100.0, 3) if total_dur > 0 else 0.0,
            "cycle_vals": {str(k): round(v, 2) for k, v in l5_cycle_vals.items()},
            "cycle_pcts": {str(k): v for k, v in l5_cycle_pcts.items()},
            "cycle_pcts_obra": {str(k): v for k, v in l5_cycle_pcts_obra.items()},
            "total": round(l5_sum, 2),
            "total_pct": round((l5_sum / b_val) * 100.0, 2) if b_val > 0 else 0.0,
            "total_pct_obra": round((l5_sum / total_proj_budget) * 100.0, 3)
        })
        tab_distribuicao_rows.extend(child_task_rows)

    # 4. FÍSICO-FINANCEIRO BASELINE
    tab_ff_baseline_rows = []
    ff_tree: Dict[str, Dict[str, Any]] = {}
    for code, item in budget_items.items():
        ff_tree[code] = {
            "level": item["level"],
            "code": code,
            "parent_code": item.get("parent_code"),
            "description": item["description"],
            "budget": item["total_price"],
            "cycle_vals": {cy["num"]: 0.0 for cy in cycles}
        }
    for code, c_vals in l5_baseline_cycles.items():
        if code in ff_tree:
            ff_tree[code]["cycle_vals"] = c_vals

    for lvl in [4, 3, 2, 1]:
        for p in [it for it in ff_tree.values() if it["level"] == lvl]:
            children = [c for c in ff_tree.values() if c["parent_code"] == p["code"]]
            if children:
                if p["budget"] <= 0.0:
                    p["budget"] = sum(ch["budget"] for ch in children)
                for cy in cycles:
                    p["cycle_vals"][cy["num"]] = sum(ch["cycle_vals"][cy["num"]] for ch in children)

    for code in sorted(ff_tree.keys(), key=lambda k: wbs_sort_key(k, ff_tree[k])):
        node = ff_tree[code]
        cycle_vals = {str(k): round(v, 2) for k, v in node["cycle_vals"].items()}
        cycle_pcts = {str(k): round((v / total_proj_budget) * 100.0, 3) for k, v in node["cycle_vals"].items()}
        total_val = round(sum(node["cycle_vals"].values()), 2)
        total_pct = round((total_val / total_proj_budget) * 100.0, 2)

        tab_ff_baseline_rows.append({
            "level": node["level"],
            "code": node["code"],
            "parent_code": node["parent_code"],
            "description": node["description"],
            "budget": node["budget"],
            "budget_pct": round((node["budget"] / total_proj_budget) * 100.0, 2),
            "cycle_vals": cycle_vals,
            "cycle_pcts": cycle_pcts,
            "total": total_val,
            "total_pct": total_pct
        })

    # 5. MEDIÇÃO (NÍVEL 5 COM SUPORTE A EXPANSÃO E APONTAMENTO EM NÍVEL 6)
    # Build Level 5 monthly measurements map for all cycles
    l5_monthly_map: Dict[str, Dict[int, float]] = {}
    l6_monthly_map: Dict[str, Dict[str, Dict[int, float]]] = {}

    for code, item in budget_items.items():
        if item["level"] != 5:
            continue
        linked = links_by_l5.get(code, [])
        task_info_list = [get_task_schedule_duration(l["task_name"], l.get("duration")) for l in linked]
        durations = [ti[0] for ti in task_info_list]
        tot_d = sum(durations)
        
        l5_monthly_map[code] = {}
        l6_monthly_map[code] = {l["task_name"]: {} for l in linked}

        for cy in cycles:
            c_num = cy["num"]
            # Check Level 6 monthly inputs first
            has_l6_month = False
            l6_w_sum = 0.0

            for idx, l in enumerate(linked):
                t_name = l["task_name"]
                t_dur = durations[idx]
                t_val = 0.0
                if code in c_m6 and t_name in c_m6[code] and str(c_num) in c_m6[code][t_name]:
                    has_l6_month = True
                    raw_val = float(c_m6[code][t_name][str(c_num)])
                    t_val = raw_val / 100.0 if raw_val > 1.0 else raw_val
                elif code in c_l6 and t_name in c_l6[code] and c_num == cutoff_med_num:
                    has_l6_month = True
                    raw_val = float(c_l6[code][t_name])
                    t_val = raw_val / 100.0 if raw_val > 1.0 else raw_val
                else:
                    # Check imported historical month for item
                    imp_m = item_monthly_measurements.get(code, {}).get(c_num, {})
                    r_val = imp_m.get("realizado", 0.0)
                    t_val = r_val / 100.0 if r_val > 1.0 else r_val

                l6_monthly_map[code][t_name][c_num] = max(0.0, min(1.0, t_val))
                if tot_d > 0 and t_dur > 0:
                    l6_w_sum += t_val * (t_dur / tot_d)

            if has_l6_month:
                l5_monthly_map[code][c_num] = max(0.0, min(1.0, l6_w_sum))
            elif code in c_m5 and str(c_num) in c_m5[code]:
                raw_v = float(c_m5[code][str(c_num)])
                l5_monthly_map[code][c_num] = max(0.0, min(1.0, raw_v / 100.0 if raw_v > 1.0 else raw_v))
            else:
                imp_m = item_monthly_measurements.get(code, {}).get(c_num, {})
                r_val = imp_m.get("realizado", 0.0)
                l5_monthly_map[code][c_num] = max(0.0, min(1.0, r_val / 100.0 if r_val > 1.0 else r_val))

    # Pre-build dictionary for all budget items in tab_medicao
    med_tree: Dict[str, Dict[str, Any]] = {}
    for code, item in budget_items.items():
        b_val = item["total_price"]
        lvl = item["level"]

        if lvl == 5:
            m_vals = l5_monthly_map.get(code, {})
            # Sum up to cutoff_med_num
            calc_accum_pct = sum(m_vals.get(m, 0.0) for m in range(1, cutoff_med_num + 1))
            if calc_accum_pct == 0.0 and code in c_l5:
                v = float(c_l5[code])
                calc_accum_pct = v / 100.0 if v > 1.0 else v
            elif calc_accum_pct == 0.0:
                imp_acc = item_measurements.get(code, item.get("accum_measured_pct", 0.0))
                calc_accum_pct = imp_acc / 100.0 if imp_acc > 1.0 else imp_acc

            accum_pct = min(1.0, max(0.0, calc_accum_pct))
            accum_val = b_val * accum_pct
            saldo = max(0.0, b_val - accum_val)

            # Build monthly columns list
            monthly_cols = []
            for cy in cycles:
                c_num = cy["num"]
                r_pct = m_vals.get(c_num, 0.0)
                p_pct = item_monthly_measurements.get(code, {}).get(c_num, {}).get("previsto", 0.0)
                monthly_cols.append({
                    "med_num": c_num,
                    "cycle_name": cy["name"],
                    "previsto_pct": round(p_pct * 100.0 if p_pct <= 1.0 else p_pct, 2),
                    "realizado_pct": round(r_pct * 100.0 if r_pct <= 1.0 else r_pct, 2),
                    "realizado_val": round(b_val * (r_pct if r_pct <= 1.0 else r_pct / 100.0), 2)
                })

            # Level 6 child tasks list
            tasks_l6_list = []
            linked = links_by_l5.get(code, [])
            task_info_list = [get_task_schedule_duration(l["task_name"], l.get("duration")) for l in linked]
            durations = [ti[0] for ti in task_info_list]
            tot_d = sum(durations)
            for idx, l in enumerate(linked):
                t_name = l["task_name"]
                t_dur = durations[idx]
                w_pct = round((t_dur / tot_d) * 100.0, 2) if (tot_d > 0 and t_dur > 0) else 0.0
                t_monthly = l6_monthly_map.get(code, {}).get(t_name, {})
                t_accum = sum(t_monthly.get(m, 0.0) for m in range(1, cutoff_med_num + 1))
                if t_accum == 0.0 and accum_pct > 0.0 and t_dur > 0:
                    t_accum = accum_pct

                tasks_l6_list.append({
                    "task_name": t_name,
                    "duration": t_dur,
                    "weight_pct": w_pct,
                    "measured_pct": round(t_accum * 100.0 if t_accum <= 1.0 else t_accum, 2) if t_dur > 0 else 0.0,
                    "monthly_measurements": {str(c_num): round(t_monthly.get(c_num, 0.0) * 100.0, 2) for c_num in range(1, len(cycles) + 1)}
                })

            effective_l5_measurements[code] = accum_pct
            med_tree[code] = {
                "level": 5,
                "code": code,
                "description": item["description"],
                "parent_code": item.get("parent_code"),
                "unit": item.get("unit"),
                "quantity": item.get("quantity", 0.0),
                "unit_price": item.get("unit_price", 0.0),
                "total_price": b_val,
                "accum_realizado_pct": round(accum_pct * 100.0, 2),
                "accum_realizado_val": round(accum_val, 2),
                "saldo": round(saldo, 2),
                "measured_source": effective_l5_sources.get(code, "imported"),
                "tasks_l6": tasks_l6_list,
                "monthly_measurements": monthly_cols,
                "monthly_map": {str(c["med_num"]): c["realizado_pct"] for c in monthly_cols}
            }
        else:
            med_tree[code] = {
                "level": lvl,
                "code": code,
                "description": item["description"],
                "parent_code": item.get("parent_code"),
                "unit": item.get("unit"),
                "quantity": item.get("quantity", 0.0),
                "unit_price": item.get("unit_price", 0.0),
                "total_price": b_val,
                "accum_realizado_pct": 0.0,
                "accum_realizado_val": 0.0,
                "saldo": b_val,
                "measured_source": "rollup",
                "tasks_l6": [],
                "monthly_measurements": [{
                    "med_num": cy["num"],
                    "cycle_name": cy["name"],
                    "previsto_pct": 0.0,
                    "realizado_pct": 0.0,
                    "realizado_val": 0.0
                } for cy in cycles],
                "monthly_map": {str(cy["num"]): 0.0 for cy in cycles}
            }

    # Rollup levels 4, 3, 2, 1 for med_tree
    for lvl in [4, 3, 2, 1]:
        for p in [it for it in med_tree.values() if it["level"] == lvl]:
            children = [c for c in med_tree.values() if c["parent_code"] == p["code"]]
            if children:
                if p["total_price"] <= 0.0:
                    p["total_price"] = sum(ch["total_price"] for ch in children)
                p_b = p["total_price"] or 1.0
                tot_real_val = sum(ch["accum_realizado_val"] for ch in children)
                p["accum_realizado_val"] = round(tot_real_val, 2)
                p["accum_realizado_pct"] = round((tot_real_val / p_b) * 100.0, 2)
                p["saldo"] = round(max(0.0, p["total_price"] - tot_real_val), 2)
                
                # Rollup monthly values
                for cy_idx in range(len(cycles)):
                    sum_m_val = sum(ch["monthly_measurements"][cy_idx]["realizado_val"] for ch in children)
                    p["monthly_measurements"][cy_idx]["realizado_val"] = round(sum_m_val, 2)
                    p_pct = round((sum_m_val / p_b) * 100.0, 2)
                    p["monthly_measurements"][cy_idx]["realizado_pct"] = p_pct
                    p["monthly_map"][str(cycles[cy_idx]["num"])] = p_pct

    tab_medicao_rows = [med_tree[k] for k in sorted(med_tree.keys(), key=lambda k: wbs_sort_key(k, med_tree[k]))]


    # 6. REPLANEJADO (SALDO NÍVEL 6)
    l5_rows: Dict[str, Dict[str, Any]] = {}
    l5_children: Dict[str, List[Dict[str, Any]]] = {}
    l5_replan_cycles: Dict[str, Dict[int, float]] = {c: {cy["num"]: 0.0 for cy in cycles} for c in budget_items if budget_items[c]["level"] == 5}

    total_measured_l5 = 0.0
    total_balance_l5 = 0.0

    # Pre-calculate global future intensity across cycles from active schedule tasks
    schedule_future_cycle_intensity: Dict[int, float] = {cy["num"]: 0.0 for cy in future_cycles}
    for t_info in tasks.values():
        t_daily = t_info.get("daily", {})
        for cy in future_cycles:
            c_sum = sum(v for dt, v in t_daily.items() if cy["start"] <= dt <= cy["end"] and dt > cutoff_date)
            schedule_future_cycle_intensity[cy["num"]] += c_sum

    total_schedule_future_intensity = sum(schedule_future_cycle_intensity.values())
    tasks_by_norm = {norm(t_info.get("name") or k): t_info for k, t_info in tasks.items()}

    for code, item in sorted(budget_items.items(), key=lambda x: wbs_sort_key(x[0], x[1])):
        if item["level"] < 5:
            continue

        b_val = item["total_price"]
        med_pct = effective_l5_measurements.get(code, item.get("accum_measured_pct", 0.0))
        med_val = b_val * med_pct
        saldo = max(0.0, b_val - med_val)

        total_measured_l5 += med_val
        total_balance_l5 += saldo

        l5_cycles = {cy["num"]: 0.0 for cy in cycles}

        # Exact measured values for past cycles from l5_monthly_map (Medição)
        m_vals = l5_monthly_map.get(code, {})
        sum_past_m = sum(m_vals.get(p_cy["num"], 0.0) for p_cy in past_cycles)
        if sum_past_m > 0:
            for p_cy in past_cycles:
                c_num = p_cy["num"]
                l5_cycles[c_num] = b_val * m_vals.get(c_num, 0.0)
        else:
            # Fallback if no monthly breakdown was present in the sheet for this item
            if past_cycles and med_val > 0:
                l5_cycles[past_cycles[-1]["num"]] = med_val

        linked = links_by_l5.get(code, [])
        valid_tasks = []
        for l in linked:
            t_name = l["task_name"]
            # check if task was already 100% measured in L6
            task_done = False
            if code in c_l6 and t_name in c_l6[code]:
                t_m = float(c_l6[code][t_name])
                if t_m > 1.0:
                    t_m /= 100.0
                if t_m >= 1.0:
                    task_done = True

            t_dur, matched_task = get_task_schedule_duration(t_name, l.get("duration"))

            if matched_task and not task_done and t_dur > 0:
                t = matched_task
                f_daily_sum = sum(v for dt, v in t["daily"].items() if dt > cutoff_date)
                valid_tasks.append({
                    "task": t,
                    "task_name": t.get("name") or t_name,
                    "weight": t_dur,
                    "future_daily_sum": f_daily_sum
                })

        active_future = [vt for vt in valid_tasks if vt["future_daily_sum"] > 0]
        child_replan_rows = []

        if active_future and saldo > 0:
            total_fut_w = sum(vt["weight"] for vt in active_future)
            for idx, vt in enumerate(active_future):
                w_pct = (vt["weight"] / total_fut_w) * 100.0
                task_saldo = saldo * (w_pct / 100.0)
                t = vt["task"]
                f_sum = vt["future_daily_sum"]

                t_rep_cycles = {cy["num"]: 0.0 for cy in cycles}
                for cy in future_cycles:
                    c_sum = sum(v for dt, v in t["daily"].items() if cy["start"] <= dt <= cy["end"] and dt > cutoff_date)
                    if c_sum > 0:
                        c_val = task_saldo * (c_sum / f_sum)
                        t_rep_cycles[cy["num"]] = c_val
                        l5_cycles[cy["num"]] += c_val

                child_replan_rows.append({
                    "level": 6,
                    "code": f"{code}.{idx+1:03d}",
                    "parent_code": code,
                    "description": vt["task_name"],
                    "future_weight_pct": round(w_pct, 2),
                    "allocated_saldo": round(task_saldo, 2),
                    "cycle_vals": {str(k): round(v, 2) for k, v in t_rep_cycles.items()},
                    "total": round(sum(t_rep_cycles.values()), 2)
                })
        elif valid_tasks and saldo > 0:
            chunk_cycles = future_cycles[:3] or future_cycles
            total_w = sum(vt["weight"] for vt in valid_tasks)
            for idx, vt in enumerate(valid_tasks):
                w_pct = (vt["weight"] / total_w) * 100.0
                task_saldo = saldo * (w_pct / 100.0)
                t_rep_cycles = {cy["num"]: 0.0 for cy in cycles}
                for cy in chunk_cycles:
                    c_val = task_saldo / len(chunk_cycles)
                    t_rep_cycles[cy["num"]] = c_val
                    l5_cycles[cy["num"]] += c_val

                child_replan_rows.append({
                    "level": 6,
                    "code": f"{code}.{idx+1:03d}",
                    "parent_code": code,
                    "description": vt["task_name"],
                    "future_weight_pct": round(w_pct, 2),
                    "allocated_saldo": round(task_saldo, 2),
                    "cycle_vals": {str(k): round(v, 2) for k, v in t_rep_cycles.items()},
                    "total": round(sum(t_rep_cycles.values()), 2)
                })
        elif saldo > 0:
            if total_schedule_future_intensity > 0:
                for cy in future_cycles:
                    w = schedule_future_cycle_intensity[cy["num"]] / total_schedule_future_intensity
                    l5_cycles[cy["num"]] += saldo * w
            else:
                chunk_cycles = future_cycles[:6] or future_cycles
                for cy in chunk_cycles:
                    l5_cycles[cy["num"]] += saldo / len(chunk_cycles)

        l5_replan_cycles[code] = l5_cycles

        l5_rows[code] = {
            "level": 5,
            "code": code,
            "parent_code": item.get("parent_code"),
            "description": item["description"],
            "budget": b_val,
            "med_val": round(med_val, 2),
            "med_pct": round(med_pct * 100, 2),
            "measured_pct": round(med_pct * 100, 2),
            "saldo": round(saldo, 2),
            "future_weight_pct": 100.0 if child_replan_rows else 0.0,
            "allocated_saldo": round(saldo, 2),
            "cycle_vals": {str(k): round(v, 2) for k, v in l5_cycles.items()},
            "total": round(sum(l5_cycles.values()), 2)
        }
        l5_children[code] = child_replan_rows

    # 7. FÍSICO-FINANCEIRO REPLANEJADO & CURVA S
    tab_ff_replan_rows = []
    ff_rep_tree: Dict[str, Dict[str, Any]] = {}
    for code, item in budget_items.items():
        ff_rep_tree[code] = {
            "level": item["level"],
            "code": code,
            "parent_code": item.get("parent_code"),
            "description": item["description"],
            "budget": item["total_price"],
            "med_val": 0.0,
            "saldo": 0.0,
            "cycle_vals": {cy["num"]: 0.0 for cy in cycles}
        }
    for code, c_vals in l5_replan_cycles.items():
        if code in ff_rep_tree:
            ff_rep_tree[code]["cycle_vals"] = c_vals
            med_pct = min(1.0, max(0.0, item_measurements.get(code, 0.0)))
            b = ff_rep_tree[code]["budget"]
            ff_rep_tree[code]["med_val"] = b * med_pct
            ff_rep_tree[code]["saldo"] = max(0.0, b - (b * med_pct))

    for lvl in [4, 3, 2, 1]:
        for p in [it for it in ff_rep_tree.values() if it["level"] == lvl]:
            children = [c for c in ff_rep_tree.values() if c["parent_code"] == p["code"]]
            if children:
                if p["budget"] <= 0.0:
                    p["budget"] = sum(ch["budget"] for ch in children)
                p["med_val"] = sum(ch["med_val"] for ch in children)
                p["saldo"] = sum(ch["saldo"] for ch in children)
                for cy in cycles:
                    p["cycle_vals"][cy["num"]] = sum(ch["cycle_vals"][cy["num"]] for ch in children)

    # Reconstruct tab_replanejado_rows with complete hierarchy (Levels 1 to 6)
    tab_replanejado_rows = []
    for code, item in sorted(budget_items.items(), key=lambda x: wbs_sort_key(x[0], x[1])):
        lvl = item["level"]
        if lvl < 5:
            node = ff_rep_tree[code]
            tab_replanejado_rows.append({
                "level": lvl,
                "code": code,
                "parent_code": node["parent_code"],
                "description": node["description"],
                "budget": round(node["budget"], 2),
                "med_val": round(node["med_val"], 2),
                "med_pct": round((node["med_val"] / node["budget"]) * 100, 2) if node["budget"] > 0 else 0.0,
                "measured_pct": round((node["med_val"] / node["budget"]) * 100, 2) if node["budget"] > 0 else 0.0,
                "saldo": round(node["saldo"], 2),
                "future_weight_pct": 100.0,
                "allocated_saldo": round(node["saldo"], 2),
                "cycle_vals": {str(k): round(v, 2) for k, v in node["cycle_vals"].items()},
                "total": round(sum(node["cycle_vals"].values()), 2)
            })
        elif lvl == 5:
            if code in l5_rows:
                tab_replanejado_rows.append(l5_rows[code])
                if code in l5_children:
                    tab_replanejado_rows.extend(l5_children[code])

    for code in sorted(ff_rep_tree.keys(), key=lambda k: wbs_sort_key(k, ff_rep_tree[k])):
        node = ff_rep_tree[code]
        cycle_vals = {str(k): round(v, 2) for k, v in node["cycle_vals"].items()}
        cycle_pcts = {str(k): round((v / total_proj_budget) * 100.0, 3) for k, v in node["cycle_vals"].items()}
        total_val = round(sum(node["cycle_vals"].values()), 2)
        total_pct = round((total_val / total_proj_budget) * 100.0, 2)

        tab_ff_replan_rows.append({
            "level": node["level"],
            "code": node["code"],
            "parent_code": node["parent_code"],
            "description": node["description"],
            "budget": node["budget"],
            "budget_pct": round((node["budget"] / total_proj_budget) * 100.0, 2),
            "med_val": round(node["med_val"], 2),
            "med_pct": round((node["med_val"] / node["budget"]) * 100, 2) if node["budget"] > 0 else 0.0,
            "saldo": round(node["saldo"], 2),
            "cycle_vals": cycle_vals,
            "cycle_pcts": cycle_pcts,
            "total": total_val,
            "total_pct": total_pct
        })

    # Curva S series
    root_rep = ff_rep_tree.get(root_code) or list(ff_rep_tree.values())[0]
    root_base = ff_tree.get(root_code) or list(ff_tree.values())[0]

    labels = [c["full_label"] for c in cycles]
    
    # Baseline
    base_month_vals = [root_base["cycle_vals"][c["num"]] for c in cycles]
    base_accum_pcts = []
    b_run = 0.0
    for v in base_month_vals:
        b_run += v
        base_accum_pcts.append((b_run / total_proj_budget) * 100.0)

    # Replan
    replan_month_vals = [root_rep["cycle_vals"][c["num"]] for c in cycles]
    replan_month_pcts = [(v / total_proj_budget) * 100.0 for v in replan_month_vals]
    replan_accum_vals = []
    replan_accum_pcts = []
    r_run = 0.0
    for v in replan_month_vals:
        r_run += v
        replan_accum_vals.append(r_run)
        replan_accum_pcts.append((r_run / total_proj_budget) * 100.0)

    # Realized
    realized_month_vals = []
    realized_accum_pcts = []
    m_run = 0.0
    for c in cycles:
        if c["is_past"]:
            v = root_rep["cycle_vals"][c["num"]]
            m_run += v
            realized_month_vals.append(v)
            realized_accum_pcts.append((m_run / total_proj_budget) * 100.0)
        else:
            realized_month_vals.append(None)
            realized_accum_pcts.append(None)

    return {
        "project_name": parsed_data["project_name"],
        "total_budget": total_proj_budget,
        "total_measured": total_measured_l5,
        "total_measured_pct": round((total_measured_l5 / total_proj_budget) * 100, 2),
        "total_balance": total_balance_l5,
        "total_balance_pct": round((total_balance_l5 / total_proj_budget) * 100, 2),
        "cutoff_med_num": cutoff_med_num,
        "cutoff_date": cutoff_date.strftime("%Y-%m-%d"),
        "cycle_config": {
            "start_day": cycle_start_day,
            "end_day": cycle_end_day
        },
        "cycles": [
            {
                "num": c["num"],
                "name": c["name"],
                "period_label": c["period_label"],
                "full_label": c["full_label"],
                "start": c["start"].strftime("%Y-%m-%d"),
                "end": c["end"].strftime("%Y-%m-%d"),
                "is_past": c["is_past"]
            }
            for c in cycles
        ],
        "s_curve": {
            "labels": labels,
            "baseline_accum_pcts": [round(p, 2) for p in base_accum_pcts],
            "realized_accum_pcts": [round(p, 2) if p is not None else None for p in realized_accum_pcts],
            "realized_month_vals": realized_month_vals,
            "replan_month_vals": replan_month_vals,
            "replan_month_pcts": [round(p, 2) for p in replan_month_pcts],
            "replan_accum_vals": replan_accum_vals,
            "replan_accum_pcts": [round(p, 2) for p in replan_accum_pcts]
        },
        # TABS DATA
        "tab_cronograma": {
            "tasks": cronograma_tasks,
            "total_tasks": len(cronograma_tasks),
            "lotes_mae": sorted(list({t["lote_mae"] for t in cronograma_tasks if t.get("lote_mae")})),
            "lots": sorted(list({t["lot"] for t in cronograma_tasks if t.get("lot")})),
            "project_start": start_date.strftime("%Y-%m-%d"),
            "project_end": end_date.strftime("%Y-%m-%d"),
            "versions": [
                {"id": "atual", "name": "Revisão Atual (Arquivo)", "active": True}
            ]
        },
        "tab_orcamento": tab_orcamento_rows,
        "tab_distribuicao": tab_distribuicao_rows,
        "tab_fisico_financeiro": tab_ff_baseline_rows,
        "tab_medicao": tab_medicao_rows,
        "tab_replanejado": tab_replanejado_rows,
        "tab_ff_replanejado": tab_ff_replan_rows,
        "tree_rows": tab_ff_replan_rows,
        "links_by_l5": links_by_l5,
        "has_custom_links": bool(custom_links_by_l5)
    }
