import datetime
import openpyxl
from backend.app.services.replan_engine import run_replan_calculation
from backend.app.services.exporter import add_sheet_replanejado, export_replan_to_excel

def test_replanejado_metrics_and_view_modes():
    # Setup simple parsed_data
    budget_items = {
        "1": {"level": 1, "code": "1", "parent_code": None, "description": "Obra Teste", "total_price": 100000.0},
        "01": {"level": 2, "code": "01", "parent_code": "1", "description": "Estrutura", "total_price": 100000.0},
        "01.01.001": {
            "level": 5,
            "code": "01.01.001",
            "parent_code": "01",
            "description": "Alvenaria",
            "total_price": 100000.0,
            "accum_measured_pct": 0.50  # 50% medido
        }
    }

    # 2 tasks in schedule starting in the future
    start_d = datetime.date(2025, 11, 25)
    end_d = datetime.date(2025, 12, 10)
    daily = {start_d + datetime.timedelta(days=i): 1.0 for i in range(10)}

    tasks = {
        "Tarefa A": {
            "id": 1,
            "name": "Tarefa A",
            "duration": 5.0,
            "start": "2025-11-25",
            "finish": "2025-11-30",
            "daily": {start_d + datetime.timedelta(days=i): 1.0 for i in range(5)}
        },
        "Tarefa B": {
            "id": 2,
            "name": "Tarefa B",
            "duration": 5.0,
            "start": "2025-12-01",
            "finish": "2025-12-06",
            "daily": {start_d + datetime.timedelta(days=i+5): 1.0 for i in range(5)}
        }
    }

    links_by_l5 = {
        "01.01.001": [
            {"task_name": "Tarefa A", "duration": 5.0},
            {"task_name": "Tarefa B", "duration": 5.0}
        ]
    }

    parsed_data = {
        "project_name": "Obra Teste",
        "budget_items": budget_items,
        "tasks": tasks,
        "links_by_l5": links_by_l5,
        "item_measurements": {"01.01.001": 0.50},
        "item_monthly_measurements": {},
        "history_monthly": [],
        "cutoff_med_num": 1,
        "start_date": datetime.date(2025, 10, 21),
        "end_date": datetime.date(2026, 2, 20),
        "total_budget": 100000.0
    }

    res = run_replan_calculation(parsed_data, cutoff_med_num=1)
    tab_replan = res.get("tab_replanejado", [])
    assert len(tab_replan) > 0

    l5_row = next(r for r in tab_replan if r["code"] == "01.01.001")
    assert l5_row["saldo"] == 50000.0
    assert l5_row["saldo_pct"] == 50.0

    l6_rows = [r for r in tab_replan if r.get("parent_code") == "01.01.001" and r["level"] == 6]
    assert len(l6_rows) == 2

    for l6 in l6_rows:
        assert l6["future_weight_pct"] == 50.0  # 50% do saldo cada uma
        assert l6["allocated_saldo"] == 25000.0  # R$ 25.000 cada uma
        assert l6["allocated_saldo_pct_service"] == 25.0  # 25% do serviço cada uma
        assert l6["parent_budget"] == 100000.0

    # Test exporter with view_mode='pct_service'
    wb = openpyxl.Workbook()
    add_sheet_replanejado(wb, res, view_mode="pct_service")
    assert "Replanejado Saldo (% Serv)" in wb.sheetnames

    # Test export_replan_to_excel
    buf, filename = export_replan_to_excel(
        res,
        active_tab="replanejado",
        ff_rep_view_mode="pct_service"
    )
    assert buf is not None
    assert "Percentual_Servico" in filename

def test_custom_replan_weights_manual_percentage():
    budget_items = {
        "1": {"level": 1, "code": "1", "parent_code": None, "description": "Obra Teste", "total_price": 100000.0},
        "01": {"level": 2, "code": "01", "parent_code": "1", "description": "Estrutura", "total_price": 100000.0},
        "01.01.001": {
            "level": 5,
            "code": "01.01.001",
            "parent_code": "01",
            "description": "Alvenaria",
            "total_price": 100000.0,
            "accum_measured_pct": 0.50
        }
    }
    start_d = datetime.date(2025, 11, 25)
    tasks = {
        "Tarefa A": {
            "id": 1,
            "name": "Tarefa A",
            "duration": 5.0,
            "start": "2025-11-25",
            "finish": "2025-11-30",
            "daily": {start_d + datetime.timedelta(days=i): 1.0 for i in range(5)}
        },
        "Tarefa B": {
            "id": 2,
            "name": "Tarefa B",
            "duration": 5.0,
            "start": "2025-12-01",
            "finish": "2025-12-06",
            "daily": {start_d + datetime.timedelta(days=i+5): 1.0 for i in range(5)}
        }
    }
    parsed_data = {
        "project_name": "Obra Teste",
        "budget_items": budget_items,
        "tasks": tasks,
        "links_by_l5": {"01.01.001": [{"task_name": "Tarefa A", "duration": 5.0}, {"task_name": "Tarefa B", "duration": 5.0}]},
        "item_measurements": {"01.01.001": 0.50},
        "item_monthly_measurements": {},
        "history_monthly": [],
        "cutoff_med_num": 1,
        "start_date": datetime.date(2025, 10, 21),
        "end_date": datetime.date(2026, 2, 20),
        "total_budget": 100000.0
    }

    # Custom weights: Tarefa A = 70%, Tarefa B = 30%
    custom_weights = {
        "01.01.001": {
            "mode": "percentual",
            "weights": {"Tarefa A": 70.0, "Tarefa B": 30.0}
        }
    }

    res = run_replan_calculation(parsed_data, cutoff_med_num=1, custom_weights=custom_weights)
    tab_replan = res["tab_replanejado"]

    l5_row = next(r for r in tab_replan if r["code"] == "01.01.001")
    assert l5_row["has_custom_replan_weights"] is True
    assert l5_row["replan_weight_mode"] == "percentual"

    t_a = next(r for r in tab_replan if r.get("parent_code") == "01.01.001" and r["description"] == "Tarefa A")
    t_b = next(r for r in tab_replan if r.get("parent_code") == "01.01.001" and r["description"] == "Tarefa B")

    assert t_a["future_weight_pct"] == 70.0
    assert t_a["allocated_saldo"] == 35000.0  # 70% de 50.000
    assert t_a["allocated_saldo_pct_service"] == 35.0  # 35% de 100.000

    assert t_b["future_weight_pct"] == 30.0
    assert t_b["allocated_saldo"] == 15000.0  # 30% de 50.000
    assert t_b["allocated_saldo_pct_service"] == 15.0  # 15% de 100.000

def test_custom_replan_weights_quantity_and_area():
    budget_items = {
        "1": {"level": 1, "code": "1", "parent_code": None, "description": "Obra Teste", "total_price": 100000.0},
        "01": {"level": 2, "code": "01", "parent_code": "1", "description": "Estrutura", "total_price": 100000.0},
        "01.01.001": {"level": 5, "code": "01.01.001", "parent_code": "01", "description": "Concreto", "total_price": 100000.0, "accum_measured_pct": 0.50}
    }
    start_d = datetime.date(2025, 11, 25)
    tasks = {
        "Pavimento 1": {"id": 1, "name": "Pavimento 1", "duration": 5.0, "start": "2025-11-25", "finish": "2025-11-30", "daily": {start_d + datetime.timedelta(days=i): 1.0 for i in range(5)}},
        "Pavimento 2": {"id": 2, "name": "Pavimento 2", "duration": 5.0, "start": "2025-12-01", "finish": "2025-12-06", "daily": {start_d + datetime.timedelta(days=i+5): 1.0 for i in range(5)}}
    }
    parsed_data = {
        "project_name": "Obra Teste",
        "budget_items": budget_items,
        "tasks": tasks,
        "links_by_l5": {"01.01.001": [{"task_name": "Pavimento 1", "duration": 5.0}, {"task_name": "Pavimento 2", "duration": 5.0}]},
        "item_measurements": {"01.01.001": 0.50},
        "item_monthly_measurements": {},
        "history_monthly": [],
        "cutoff_med_num": 1,
        "start_date": datetime.date(2025, 10, 21),
        "end_date": datetime.date(2026, 2, 20),
        "total_budget": 100000.0
    }

    # Quantidade: 2000 e 8000 (20% e 80%)
    custom_weights_qty = {
        "01.01.001": {
            "mode": "quantidade",
            "weights": {"Pavimento 1": 20.0, "Pavimento 2": 80.0},
            "inputs": {"Pavimento 1": 2000, "Pavimento 2": 8000}
        }
    }
    res_qty = run_replan_calculation(parsed_data, cutoff_med_num=1, custom_weights=custom_weights_qty)
    p1 = next(r for r in res_qty["tab_replanejado"] if r.get("description") == "Pavimento 1")
    p2 = next(r for r in res_qty["tab_replanejado"] if r.get("description") == "Pavimento 2")
    assert p1["future_weight_pct"] == 20.0
    assert p1["allocated_saldo"] == 10000.0
    assert p2["future_weight_pct"] == 80.0
    assert p2["allocated_saldo"] == 40000.0

    # Área: 100m² e 300m² (25% e 75%)
    custom_weights_area = {
        "01.01.001": {
            "mode": "area",
            "weights": {"Pavimento 1": 25.0, "Pavimento 2": 75.0},
            "inputs": {"Pavimento 1": 100, "Pavimento 2": 300}
        }
    }
    res_area = run_replan_calculation(parsed_data, cutoff_med_num=1, custom_weights=custom_weights_area)
    p1_a = next(r for r in res_area["tab_replanejado"] if r.get("description") == "Pavimento 1")
    p2_a = next(r for r in res_area["tab_replanejado"] if r.get("description") == "Pavimento 2")
    assert p1_a["future_weight_pct"] == 25.0
    assert p1_a["allocated_saldo"] == 12500.0
    assert p2_a["future_weight_pct"] == 75.0
    assert p2_a["allocated_saldo"] == 37500.0


def test_replan_request_pydantic_custom_weights():
    from backend.app.routers.replan import ReplanRequest

    # Test ReplanRequest with custom weights dictionary (mode, weights, inputs)
    req = ReplanRequest(
        project_id="test",
        custom_weights={
            "01.04.01.01.002": {
                "mode": "percentual",
                "weights": {
                    "ESTRUTURA - T1 - 15º Pav": 35.0,
                    "ESTRUTURA - T1 - 16º Pav": 35.0,
                    "ESTRUTURA - T1 - Ático": 20.0,
                    "ESTRUTURA - T1 - Barrilete": 5.0,
                    "ESTRUTURA - T1 - Cobertura": 5.0
                },
                "inputs": {}
            }
        }
    )
    assert req.custom_weights is not None
    assert "01.04.01.01.002" in req.custom_weights
    assert req.custom_weights["01.04.01.01.002"]["weights"]["ESTRUTURA - T1 - 15º Pav"] == 35.0

