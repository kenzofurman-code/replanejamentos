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


def test_hierarchical_cascading_inheritance():
    from backend.app.services.competence_finance_engine import resolve_stage_config, compute_competence_and_cashflow

    budget_items = [
        {"level": 1, "code": "01", "description": "Obra"},
        {"level": 2, "code": "01.01", "description": "Estrutura", "parent_code": "01"},
        {"level": 3, "code": "01.01.01", "description": "Infraestrutura", "parent_code": "01.01"},
        {"level": 4, "code": "01.01.01.01", "description": "Fundações", "parent_code": "01.01.01"},
        {"level": 4, "code": "01.01.01.02", "description": "Blocos de Coroamento", "parent_code": "01.01.01"},
    ]

    # Configura apenas no Nível 2 (01.01) e personaliza uma das folhas (01.01.01.02)
    stage_configs = {
        "01.01": {
            "code": "01.01",
            "material_pct": 75.0,
            "labor_pct": 25.0,
            "anticipation_days": 25,
            "distribution_type": "continuo",
            "payment_terms": "30/60"
        },
        "01.01.01.02": {
            "code": "01.01.01.02",
            "material_pct": 50.0,
            "labor_pct": 50.0,
            "anticipation_days": 10,
            "distribution_type": "lotes",
            "num_batches": 3,
            "payment_terms": "14"
        }
    }

    # 1. 01.01.01 (Nível 3) deve herdar do Nível 2 (01.01)
    cfg_n3 = resolve_stage_config("01.01.01", budget_items, stage_configs)
    assert cfg_n3["material_pct"] == 75.0
    assert cfg_n3["labor_pct"] == 25.0
    assert cfg_n3["anticipation_days"] == 25
    assert cfg_n3["payment_terms"] == "30/60"
    assert "Herdado de 01.01" in cfg_n3.get("source", "")

    # 2. 01.01.01.01 (Nível 4) não tem config própria -> deve herdar de 01.01
    cfg_n4_1 = resolve_stage_config("01.01.01.01", budget_items, stage_configs)
    assert cfg_n4_1["material_pct"] == 75.0
    assert cfg_n4_1["payment_terms"] == "30/60"

    # 3. 01.01.01.02 (Nível 4) tem config própria -> deve respeitar seus valores personalizados
    cfg_n4_2 = resolve_stage_config("01.01.01.02", budget_items, stage_configs)
    assert cfg_n4_2["material_pct"] == 50.0
    assert cfg_n4_2["labor_pct"] == 50.0
    assert cfg_n4_2["anticipation_days"] == 10
    assert cfg_n4_2["distribution_type"] == "lotes"
    assert cfg_n4_2["num_batches"] == 3
    assert cfg_n4_2["payment_terms"] == "14"


def test_curvas_config_all_eap_levels_excel():
    from backend.app.services.competence_finance_engine import generate_curvas_config_excel, parse_curvas_config_excel

    configs = [
        {"level": 2, "code": "01.01", "description": "Estrutura", "material_pct": 70.0, "labor_pct": 30.0, "anticipation_days": 20, "distribution_type": "continuo", "payment_terms": "28", "source": "Personalizado"},
        {"level": 3, "code": "01.01.01", "description": "Infra", "material_pct": 70.0, "labor_pct": 30.0, "anticipation_days": 20, "distribution_type": "continuo", "payment_terms": "28", "source": "Herdado de 01.01"},
        {"level": 4, "code": "01.01.01.01", "description": "Estacas", "material_pct": 80.0, "labor_pct": 20.0, "anticipation_days": 10, "distribution_type": "lotes", "num_batches": 2, "payment_terms": "15", "source": "Personalizado"},
    ]

    raw_excel = generate_curvas_config_excel(configs)
    assert len(raw_excel) > 0

    parsed = parse_curvas_config_excel(raw_excel)
    assert "01.01" in parsed
    assert "01.01.01" in parsed
    assert "01.01.01.01" in parsed

    assert parsed["01.01.01.01"]["material_pct"] == 80.0
    assert parsed["01.01.01.01"]["distribution_type"] == "lotes"
    assert parsed["01.01.01.01"]["num_batches"] == 2
    assert parsed["01.01.01.01"]["payment_terms"] == "15"


def test_fisico_diario_and_date_helpers():
    from backend.app.services.competence_finance_engine import (
        somar_dias_iso, diferenca_dias, mes_competencia_mo, data_pagamento_mo,
        somar_um_ano_iso, fisico_diario
    )

    # Date helpers
    assert somar_dias_iso("2026-03-20", 5) == "2026-03-25"
    assert somar_dias_iso("2026-03-20", -5) == "2026-03-15"
    assert diferenca_dias("2026-01-01", "2026-01-10") == 9
    assert mes_competencia_mo("2026-03-20", 20) == "2026-03"
    assert mes_competencia_mo("2026-03-21", 20) == "2026-04"
    assert data_pagamento_mo("2026-03", 5) == "2026-04-05"
    assert somar_um_ano_iso("2024-02-29") == "2025-02-28"

    # Físico diário com pontos mensais
    pontos = [
        {"data": "2026-01-01", "previsto": 0.4},
        {"data": "2026-02-01", "previsto": 0.6}
    ]
    dias = fisico_diario("2026-01-01", "2026-02-28", pontos)
    assert len(dias) == 31 + 28
    assert abs(sum(d["peso"] for d in dias) - 1.0) < 0.0001


def test_material_and_labor_advanced_flows():
    from backend.app.services.competence_finance_engine import (
        material_com_fluxos, mao_de_obra_com_fluxos
    )

    # Test Material: Proporcional com antecedência de 10 dias e prazo de 28 dias
    mat_res = material_com_fluxos(
        custo=10000.0,
        data_inicio="2026-02-01",
        data_fim="2026-02-28",
        dias_antecedencia=10,
        tipo_pagamento="DIAS",
        prazo_dias=28
    )
    assert len(mat_res["eventos"]) > 0
    assert len(mat_res["fluxos"]) > 0
    # Chegada antes da execução (em Jan/26) e pagamento em Fev/26
    ev = mat_res["eventos"][0]
    assert ev["mesCompetencia"] == "2026-01"
    assert ev["mesFinanceiro"] == "2026-02"
    assert abs(sum(e["valor"] for e in mat_res["eventos"]) - 10000.0) < 1.0

    # Test Mão de Obra com Retenção Técnica de 5%
    mo_res = mao_de_obra_com_fluxos(
        custo=20000.0,
        data_inicio="2026-03-01",
        data_fim="2026-03-31",
        dia_corte_mo=20,
        dia_pagamento_mo=5,
        retencao_percentual=5.0,
        data_liberacao_retencao="2027-03-31"
    )
    assert len(mo_res["eventos"]) >= 2
    # Deve ter eventos de retenção no financeiro de 2027-03 somando 5% de 20.000 = 1000.0
    ret_evs = [e for e in mo_res["eventos"] if e.get("retencao")]
    assert len(ret_evs) > 0
    assert all(e["mesFinanceiro"] == "2027-03" for e in ret_evs)
    assert abs(sum(e["valor"] for e in ret_evs) - 1000.0) < 0.1


def test_projetar_realizado_alerts_and_balance():
    from backend.app.services.competence_finance_engine import projetar_realizado

    etapas = [
        {
            "codigo_etapa": "01.01.001",
            "nome": "Estrutura Concreto",
            "custo_material": 60000.0,
            "custo_mao_obra": 40000.0,
            "custo_total": 100000.0,
            "data_inicio": "2026-01-01",
            "data_fim": "2026-04-30",
            "pontos_mensais": [
                {"data": "2026-01-01", "previsto": 0.25},
                {"data": "2026-02-01", "previsto": 0.25},
                {"data": "2026-03-01", "previsto": 0.25},
                {"data": "2026-04-01", "previsto": 0.25},
            ]
        },
        {
            "codigo_etapa": "01.01.002",
            "nome": "Alvenaria",
            "custo_material": 30000.0,
            "custo_mao_obra": 20000.0,
            "custo_total": 50000.0,
            "data_inicio": "2026-01-01",
            "data_fim": "2026-01-31",
            "pontos_mensais": [
                {"data": "2026-01-01", "previsto": 1.0}
            ]
        }
    ]

    # Incorrido com saldo excedente em Alvenaria (R$ 55.000 > R$ 50.000)
    realizado = [
        {"codigo_etapa": "01.01.001", "data": "2026-01-15", "valor": 20000.0, "tipo": "MATERIAL", "ap": 101},
        {"codigo_etapa": "01.01.002", "data": "2026-01-20", "valor": 55000.0, "tipo": "MATERIAL", "ap": 102}
    ]

    # Pagamentos
    pagamentos = {
        "101": [{"parcela": "1", "vencimento": "2026-01-28", "valor": 20000.0, "pago": 15000.0, "saldo": 5000.0}]
    }

    proj = projetar_realizado(
        etapas=etapas,
        corte="2026-01",
        realizado=realizado,
        pagamentos=pagamentos
    )

    kpis = proj["kpis"]
    assert kpis["realizadoAteCorte"] == 75000.0
    assert kpis["realizadoFinanceiroAteCorte"] == 15000.0
    assert kpis["abertoVencido"] == 5000.0
    assert kpis["excedente"] == 5000.0  # Alvenaria estourou 5000

    alvenaria_res = next(r for r in proj["etapas"] if r["codigo_etapa"] == "01.01.002")
    assert alvenaria_res["alerta"] == "excedente"




