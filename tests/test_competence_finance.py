import datetime
import pytest
from backend.app.services.competence_finance_engine import (
    parse_payment_terms,
    get_default_stage_configs,
    compute_competence_and_cashflow
)

def test_parse_payment_terms():
    assert parse_payment_terms("28") == [(28, 1.0)]
    assert parse_payment_terms(None) == [(28, 1.0)]
    assert parse_payment_terms("   ") == [(28, 1.0)]
    
    # 2 parcelas
    terms_2 = parse_payment_terms("30/60")
    assert len(terms_2) == 2
    assert terms_2[0] == (30, 0.5)
    assert terms_2[1] == (60, 0.5)
    
    # 3 parcelas
    terms_3 = parse_payment_terms("30, 60, 90")
    assert len(terms_3) == 3
    assert terms_3[0][0] == 30
    assert terms_3[1][0] == 60
    assert terms_3[2][0] == 90
    assert abs(sum(p[1] for p in terms_3) - 1.0) < 0.001

    # Personalizado com porcentagem: 30:40,60:60
    terms_custom = parse_payment_terms("30:40,60:60")
    assert len(terms_custom) == 2
    assert terms_custom[0] == (30, 0.4)
    assert terms_custom[1] == (60, 0.6)

def test_compute_competence_and_cashflow_basic():
    # Simulação básica com 1 item de nível 1, 1 de nível 2 e 1 de nível 5
    budget_items = {
        "1": {"level": 1, "code": "1", "parent_code": None, "description": "Obra Teste", "total_price": 100000.0},
        "01.01": {"level": 2, "code": "01.01", "parent_code": "1", "description": "Estrutura", "total_price": 100000.0},
        "01.01.001": {"level": 5, "code": "01.01.001", "parent_code": "01.01", "description": "Concreto", "total_price": 100000.0}
    }
    
    # Ciclos de teste: Mês 1 (21/out a 20/nov), Mês 2 (21/nov a 20/dez), Mês 3 (21/dez a 20/jan)
    cycles = [
        {
            "num": 1,
            "name": "Mês 1",
            "period_label": "Nov/25",
            "full_label": "Mês 1 (Nov/25)",
            "start": datetime.date(2025, 10, 21),
            "end": datetime.date(2025, 11, 20),
            "is_past": False
        },
        {
            "num": 2,
            "name": "Mês 2",
            "period_label": "Dez/25",
            "full_label": "Mês 2 (Dez/25)",
            "start": datetime.date(2025, 11, 21),
            "end": datetime.date(2025, 12, 20),
            "is_past": False
        },
        {
            "num": 3,
            "name": "Mês 3",
            "period_label": "Jan/26",
            "full_label": "Mês 3 (Jan/26)",
            "start": datetime.date(2025, 12, 21),
            "end": datetime.date(2026, 1, 20),
            "is_past": False
        }
    ]
    
    # tab_ff_replan_rows com R$ 10.000 no Mês 2
    tab_ff_replan_rows = [
        {
            "level": 1,
            "code": "1",
            "description": "Obra Teste",
            "cycle_vals": {"1": 0.0, "2": 10000.0, "3": 0.0}
        },
        {
            "level": 2,
            "code": "01.01",
            "description": "Estrutura",
            "cycle_vals": {"1": 0.0, "2": 10000.0, "3": 0.0}
        },
        {
            "level": 5,
            "code": "01.01.001",
            "description": "Concreto",
            "cycle_vals": {"1": 0.0, "2": 10000.0, "3": 0.0}
        }
    ]
    
    # Configuração: 60% Material (R$ 6.000) e 40% MO (R$ 4.000)
    # Antecedência: 15 dias -> cai no Mês 1 (entrega antes de 21/nov)
    # Pagamento Material: 28 dias -> cai no Mês 2
    # Pagamento MO: Mês 3 (dia 5 do mês seguinte ao Mês 2)
    stage_configs = {
        "01.01": {
            "code": "01.01",
            "description": "Estrutura",
            "material_pct": 60.0,
            "labor_pct": 40.0,
            "anticipation_days": 15,
            "distribution_type": "continuo",
            "num_batches": None,
            "payment_terms": "28",
            "labor_payment_day": 5
        }
    }
    
    res = compute_competence_and_cashflow(
        budget_items=budget_items,
        tab_ff_replan_rows=tab_ff_replan_rows,
        cycles=cycles,
        total_proj_budget=100000.0,
        stage_configs=stage_configs
    )
    
    assert "tab_competencia" in res
    assert "tab_financeiro" in res
    assert "s_curves_comparison" in res
    
    root_comp = next(r for r in res["tab_competencia"] if r["level"] == 1)
    root_fin = next(r for r in res["tab_financeiro"] if r["level"] == 1)
    
    # Competência:
    # Material antecipado 15 dias: entrega em 21/11 - 15d = 06/11 (Mês 1) -> R$ 6.000 no Mês 1
    # MO: medida no Mês 2 -> R$ 4.000 no Mês 2
    assert root_comp["cycle_mat_vals"]["1"] == 6000.0
    assert root_comp["cycle_mo_vals"]["2"] == 4000.0
    assert root_comp["total"] == 10000.0
    
    # Financeiro:
    # MO do Mês 2 paga no Mês 3 -> R$ 4.000 no Mês 3
    assert root_fin["cycle_mo_vals"]["3"] == 4000.0
    assert root_fin["total"] == 10000.0

def test_compute_competence_batches():
    budget_items = {
        "1": {"level": 1, "code": "1", "parent_code": None, "description": "Obra Lotes", "total_price": 50000.0},
        "01.07": {"level": 2, "code": "01.07", "parent_code": "1", "description": "Revestimentos", "total_price": 50000.0},
        "01.07.001": {"level": 5, "code": "01.07.001", "parent_code": "01.07", "description": "Porcelanato", "total_price": 50000.0}
    }
    cycles = [
        {"num": 1, "name": "Mês 1", "period_label": "Out/25", "full_label": "Mês 1 (Out/25)", "start": datetime.date(2025, 9, 21), "end": datetime.date(2025, 10, 20), "is_past": False},
        {"num": 2, "name": "Mês 2", "period_label": "Nov/25", "full_label": "Mês 2 (Nov/25)", "start": datetime.date(2025, 10, 21), "end": datetime.date(2025, 11, 20), "is_past": False},
        {"num": 3, "name": "Mês 3", "period_label": "Dez/25", "full_label": "Mês 3 (Dez/25)", "start": datetime.date(2025, 11, 21), "end": datetime.date(2025, 12, 20), "is_past": False},
        {"num": 4, "name": "Mês 4", "period_label": "Jan/26", "full_label": "Mês 4 (Jan/26)", "start": datetime.date(2025, 12, 21), "end": datetime.date(2026, 1, 20), "is_past": False},
        {"num": 5, "name": "Mês 5", "period_label": "Fev/26", "full_label": "Mês 5 (Fev/26)", "start": datetime.date(2026, 1, 21), "end": datetime.date(2026, 2, 20), "is_past": False},
    ]
    tab_ff_replan_rows = [
        {"level": 1, "code": "1", "cycle_vals": {"1": 10000.0, "2": 10000.0, "3": 10000.0, "4": 10000.0, "5": 10000.0}},
        {"level": 2, "code": "01.07", "cycle_vals": {"1": 10000.0, "2": 10000.0, "3": 10000.0, "4": 10000.0, "5": 10000.0}},
        {"level": 5, "code": "01.07.001", "cycle_vals": {"1": 10000.0, "2": 10000.0, "3": 10000.0, "4": 10000.0, "5": 10000.0}},
    ]
    # 50.000 total: 60% Material = 30.000. Em 5 lotes de 6.000 cada.
    stage_configs = {
        "01.07": {
            "code": "01.07",
            "material_pct": 60.0,
            "labor_pct": 40.0,
            "anticipation_days": 15,
            "distribution_type": "lotes",
            "num_batches": 5,
            "payment_terms": "28",
            "labor_payment_day": 5
        }
    }
    res = compute_competence_and_cashflow(
        budget_items=budget_items,
        tab_ff_replan_rows=tab_ff_replan_rows,
        cycles=cycles,
        total_proj_budget=50000.0,
        stage_configs=stage_configs
    )
    root_comp = next(r for r in res["tab_competencia"] if r["level"] == 1)
    # Total de material = 30.000
    assert root_comp["total_mat"] == 30000.0
    # Total geral = 50.000
    assert root_comp["total"] == 50000.0

def test_curvas_config_excel_roundtrip():
    from backend.app.services.competence_finance_engine import generate_curvas_config_excel, parse_curvas_config_excel
    configs = [
        {
            "code": "01.03",
            "description": "INFRAESTRUTURA",
            "material_pct": 70.0,
            "labor_pct": 30.0,
            "anticipation_days": 20,
            "distribution_type": "continuo",
            "num_batches": None,
            "payment_terms": "28"
        },
        {
            "code": "01.07",
            "description": "REVESTIMENTOS",
            "material_pct": 55.0,
            "labor_pct": 45.0,
            "anticipation_days": 30,
            "distribution_type": "lotes",
            "num_batches": 4,
            "payment_terms": "30/60/90"
        }
    ]
    excel_bytes = generate_curvas_config_excel(configs)
    assert len(excel_bytes) > 0

    parsed = parse_curvas_config_excel(excel_bytes)
    assert "01.03" in parsed
    assert parsed["01.03"]["material_pct"] == 70.0
    assert parsed["01.03"]["anticipation_days"] == 20
    assert parsed["01.03"]["payment_terms"] == "28"

    assert "01.07" in parsed
    assert parsed["01.07"]["material_pct"] == 55.0
    assert parsed["01.07"]["distribution_type"] == "lotes"
    assert parsed["01.07"]["num_batches"] == 4
    assert parsed["01.07"]["payment_terms"] == "30/60/90"

def test_export_competencia_financeiro():
    from backend.app.services.exporter import export_replan_to_excel
    replan_result = {
        "project_name": "Obra Teste",
        "cutoff_med_num": 1,
        "total_budget": 100000.0,
        "cycles": [{"num": 1, "period_label": "Out/25"}],
        "extended_cycles": [{"num": 1, "period_label": "Out/25"}],
        "tab_competencia": [
            {"level": 1, "code": "1", "description": "Obra", "budget": 100000.0, "cycle_vals": {"1": 10000.0}}
        ],
        "tab_financeiro": [
            {"level": 1, "code": "1", "description": "Obra", "budget": 100000.0, "cycle_vals": {"1": 10000.0}}
        ]
    }
    # Testar exportação da aba de competência
    buf, fname = export_replan_to_excel(replan_result, export_target="current", active_tab="competencia")
    assert fname.startswith("OBRA_TESTE_Curva_Competencia")
    assert len(buf.getvalue()) > 0

    # Testar exportação da aba financeira
    buf_fin, fname_fin = export_replan_to_excel(replan_result, export_target="current", active_tab="financeiro")
    assert fname_fin.startswith("OBRA_TESTE_Curva_Financeira")
    assert len(buf_fin.getvalue()) > 0



