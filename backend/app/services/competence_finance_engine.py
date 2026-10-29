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


# ==============================================================================
# Funções Auxiliares de Datas & ISO (Compatibilidade com dadosprevision)
# ==============================================================================

def somar_dias_iso(data_iso: Optional[str], dias: int) -> Optional[str]:
    """Soma ou subtrai N dias de uma data ISO (YYYY-MM-DD)."""
    if not data_iso:
        return None
    try:
        parts = str(data_iso)[:10].split("-")
        dt = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        return (dt + datetime.timedelta(days=int(dias or 0))).isoformat()
    except Exception:
        return None


def diferenca_dias(data_ini: Optional[str], data_fim: Optional[str]) -> int:
    """Retorna a diferença em dias corridos entre data_fim e data_ini."""
    if not data_ini or not data_fim:
        return 0
    try:
        p1 = str(data_ini)[:10].split("-")
        p2 = str(data_fim)[:10].split("-")
        dt1 = datetime.date(int(p1[0]), int(p1[1]), int(p1[2]))
        dt2 = datetime.date(int(p2[0]), int(p2[1]), int(p2[2]))
        return (dt2 - dt1).days
    except Exception:
        return 0


def mes_ano_iso(data_iso: Optional[str]) -> str:
    """Extrai 'YYYY-MM' de uma data ISO."""
    return str(data_iso or "")[:7]


def proximo_mes_iso(mes_iso: Optional[str]) -> str:
    """Avança um mês no formato 'YYYY-MM'."""
    if not mes_iso or len(mes_iso) < 7:
        return str(mes_iso or "")
    try:
        y, m = int(mes_iso[:4]), int(mes_iso[5:7])
        if m == 12:
            return f"{y + 1}-01"
        return f"{y}-{m + 1:02d}"
    except Exception:
        return str(mes_iso)


def mes_anterior_iso(mes_iso: Optional[str]) -> str:
    """Recua um mês no formato 'YYYY-MM'."""
    if not mes_iso or len(mes_iso) < 7:
        return str(mes_iso or "")
    try:
        y, m = int(mes_iso[:4]), int(mes_iso[5:7])
        if m == 1:
            return f"{y - 1}-12"
        return f"{y}-{m - 1:02d}"
    except Exception:
        return str(mes_iso)


def ultimo_dia_do_mes(mes_iso: Optional[str]) -> int:
    """Retorna o último dia do mês (28..31)."""
    if not mes_iso or len(mes_iso) < 7:
        return 30
    try:
        y, m = int(mes_iso[:4]), int(mes_iso[5:7])
        return calendar.monthrange(y, m)[1]
    except Exception:
        return 30


def mes_competencia_mo(data_iso: Optional[str], dia_corte: int = 20) -> str:
    """
    Regra de Mão de Obra Piemonte:
    Serviços executados de 21/(M-1) a 20/M pertencem à competência M.
    Se data for > dia_corte, pertence ao mês seguinte (M+1).
    """
    if not data_iso:
        return ""
    try:
        parts = str(data_iso)[:10].split("-")
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if d <= dia_corte:
            return f"{y}-{m:02d}"
        if m == 12:
            return f"{y + 1}-01"
        return f"{y}-{m + 1:02d}"
    except Exception:
        return mes_ano_iso(data_iso)


def data_pagamento_mo(mes_competencia: str, dia: int = 5) -> str:
    """Data de pagamento da MO: dia `dia` do mês seguinte à competência."""
    mes_pag = proximo_mes_iso(mes_competencia)
    last_d = ultimo_dia_do_mes(mes_pag)
    d = min(max(1, int(dia or 5)), last_d)
    return f"{mes_pag}-{d:02d}"


def somar_um_ano_iso(data_iso: Optional[str]) -> Optional[str]:
    """Mesma data um ano depois (trata 29/02 para 28/02)."""
    if not data_iso:
        return None
    try:
        parts = str(data_iso)[:10].split("-")
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        mes_target = f"{y + 1}-{m:02d}"
        last_d = ultimo_dia_do_mes(mes_target)
        return f"{mes_target}-{min(d, last_d):02d}"
    except Exception:
        return None


def nivel1_do_codigo(codigo: Any) -> str:
    """Nível 1 do orçamento de um código estruturado ('01.03.05.02.002' -> '01' ou '1')."""
    if codigo is None:
        return ""
    s = str(codigo).strip().split(".")[0]
    return s.zfill(2) if s.isdigit() else s



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


def condicoes_pagamento(
    tipo_pagamento: str = "DIAS",
    prazo_dias: int = 28,
    parcelas_dias: Optional[List[int]] = None,
    parcelas_pct: Optional[List[float]] = None,
    payment_terms: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Condições de pagamento do material: prazo único ou parcelas.
    `parcelas_pct` (mesmo tamanho de `parcelas_dias`, normalizado para somar 100%) dá o peso de cada parcela;
    sem ele, parcelas iguais. Se payment_terms string for passada e não houver parcelas_dias, usa parse_payment_terms.
    """
    if tipo_pagamento == "PARCELADO" and parcelas_dias and len(parcelas_dias) > 0:
        n = len(parcelas_dias)
        pct = None
        if parcelas_pct and len(parcelas_pct) == n:
            pct = [max(0.0, float(p)) for p in parcelas_pct]
        soma = sum(pct) if pct else 0.0
        conds = []
        for i, d in enumerate(parcelas_dias):
            fracao = (pct[i] / soma) if (pct and soma > 0) else (1.0 / n)
            peso_desc = f", {round(fracao * 100)}%" if (pct and soma > 0) else ""
            conds.append({
                "dias": int(d),
                "fracao": fracao,
                "motivo": f"parcela {i + 1}/{n} ({int(d)} dias{peso_desc})"
            })
        return conds

    if payment_terms:
        parsed = parse_payment_terms(payment_terms)
        if len(parsed) > 1:
            n = len(parsed)
            conds = []
            for i, (d, fracao) in enumerate(parsed):
                peso_desc = f", {round(fracao * 100)}%"
                conds.append({
                    "dias": int(d),
                    "fracao": fracao,
                    "motivo": f"parcela {i + 1}/{n} ({int(d)} dias{peso_desc})"
                })
            return conds
        elif len(parsed) == 1:
            d = parsed[0][0]
            return [{"dias": d, "fracao": 1.0, "motivo": f"pagamento em {d} dias"}]

    d = int(prazo_dias if prazo_dias is not None else 28)
    return [{"dias": d, "fracao": 1.0, "motivo": f"pagamento em {d} dias"}]


def fisico_diario(
    data_inicio: str, 
    fim: str, 
    pontos_mensais: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Físico diário da etapa — base única das três curvas (Físico, Competência e Financeiro).
    O peso de cada mês do cronograma (`pontos_mensais[].previsto` ou `base`) é espalhado igualmente
    pelos dias daquele mês dentro da etapa; sem pontos, distribuição uniforme entre início e fim.
    Retorna lista de {'data': YYYY-MM-DD, 'peso': float} com Σ peso = 1.0.
    """
    dias = []
    pontos = []
    if isinstance(pontos_mensais, list):
        for p in pontos_mensais:
            m = str(p.get("data") or "")[:7]
            val = p.get("previsto")
            if val is None:
                val = p.get("base")
            try:
                peso = float(val or 0.0)
            except (ValueError, TypeError):
                peso = 0.0
            if peso > 0 and len(m) == 7 and m[4] == "-":
                pontos.append({"mes": m, "peso": peso})

    if pontos:
        for p in pontos:
            primeiro = f"{p['mes']}-01"
            ultimo = f"{p['mes']}-{ultimo_dia_do_mes(p['mes']):02d}"
            ini = max(data_inicio, primeiro) if data_inicio else primeiro
            f = min(fim, ultimo) if fim else ultimo
            if ini > f:
                ini, f = primeiro, ultimo
            n = diferenca_dias(ini, f) + 1
            if n <= 0:
                n = 1
            for i in range(n):
                dias.append({"data": somar_dias_iso(ini, i), "peso": p["peso"] / n})
    else:
        n = diferenca_dias(data_inicio, fim) + 1
        n = max(1, n)
        for i in range(n):
            dias.append({"data": somar_dias_iso(data_inicio, i), "peso": 1.0 / n})

    soma = sum(d["peso"] for d in dias) or 1.0
    return [{"data": d["data"], "peso": d["peso"] / soma} for d in dias]


def agregar_fluxos(brutos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fluxos { tipo, fis, comp, fin, valor, mComp, mFin } somados por chave e arredondados."""
    m = {}
    for f in brutos:
        val = float(f.get("valor") or 0.0)
        if val <= 0:
            continue
        k = f"{f.get('tipo')}|{f.get('fis')}|{f.get('comp')}|{f.get('fin')}|{f.get('mComp')}|{f.get('mFin')}"
        if k in m:
            m[k]["valor"] += val
        else:
            m[k] = dict(f)
    res = []
    for f in m.values():
        v = round(f["valor"], 2)
        if v > 0:
            f["valor"] = v
            res.append(f)
    return res


def material_com_fluxos(
    custo: float,
    data_inicio: str,
    data_fim: str,
    dias_antecedencia: int = 10,
    num_entregas: Optional[int] = None,
    tipo_pagamento: str = "DIAS",
    prazo_dias: int = 28,
    parcelas_dias: Optional[List[int]] = None,
    parcelas_pct: Optional[List[float]] = None,
    pontos_mensais: Optional[List[Dict[str, Any]]] = None,
    payment_terms: Optional[str] = None
) -> Dict[str, Any]:
    """
    Material:
    - Competência = data de chegada na obra.
      - Proporcional (padrão): cada dia físico chega `dias_antecedencia` antes; uma entrega por mês
        de chegada, no dia médio ponderado.
      - Lotes (`num_entregas` = N): período com físico dividido em N janelas de execução iguais; entrega k
        chega `dias_antecedencia` antes da janela k e carrega o peso físico daquela janela.
    - Financeiro: data de entrega + prazo (único ou parcelado).
    Retorna {'eventos': [...], 'fluxos': [...]}.
    """
    eventos = []
    brutos = []
    valor = float(custo or 0.0)
    if valor <= 0 or not data_inicio:
        return {"eventos": eventos, "fluxos": []}

    fim = data_fim if (data_fim and data_fim >= data_inicio) else data_inicio
    antecedencia = int(dias_antecedencia or 0)
    dias = fisico_diario(data_inicio, fim, pontos_mensais)
    condicoes = condicoes_pagamento(tipo_pagamento, prazo_dias, parcelas_dias, parcelas_pct, payment_terms)

    def _adicionar_entrega(data_entrega: str, por_fis: Dict[str, float], m_comp: str):
        mes_comp = mes_ano_iso(data_entrega)
        peso_entrega = sum(por_fis.values())
        for cond in condicoes:
            data_venc = somar_dias_iso(data_entrega, cond["dias"])
            mes_fin = mes_ano_iso(data_venc)
            eventos.append({
                "tipo": "MATERIAL",
                "dataEntrega": data_entrega,
                "dataVencimento": data_venc,
                "mesCompetencia": mes_comp,
                "mesFinanceiro": mes_fin,
                "valor": round(valor * peso_entrega * cond["fracao"], 2),
            })
            for fis, p in por_fis.items():
                brutos.append({
                    "tipo": "MATERIAL",
                    "fis": fis,
                    "comp": mes_comp,
                    "fin": mes_fin,
                    "valor": valor * p * cond["fracao"],
                    "mComp": m_comp,
                    "mFin": cond["motivo"]
                })

    if num_entregas and int(num_entregas) >= 1:
        N = int(num_entregas)
        com_fisico = sorted([d["data"] for d in dias if d["peso"] > 0])
        inicio_fisico = com_fisico[0] if com_fisico else data_inicio
        fim_fisico = com_fisico[-1] if com_fisico else fim
        T = diferenca_dias(inicio_fisico, fim_fisico) + 1

        def _inicio_periodo(k: int) -> int:
            return (k * T) // N

        lotes = [{} for _ in range(N)]
        for d in dias:
            i = min(T - 1, max(0, diferenca_dias(inicio_fisico, d["data"])))
            k = N - 1
            while k > 0 and _inicio_periodo(k) > i:
                k -= 1
            fis = mes_ano_iso(d["data"])
            lotes[k][fis] = lotes[k].get(fis, 0.0) + d["peso"]

        for k, por_fis in enumerate(lotes):
            if not any(p > 0 for p in por_fis.values()):
                continue
            chegada = somar_dias_iso(inicio_fisico, _inicio_periodo(k) - antecedencia)
            _adicionar_entrega(chegada, por_fis, f"entrega {k + 1} de {N} (chega {antecedencia} dias antes)")
        return {"eventos": eventos, "fluxos": agregar_fluxos(brutos)}

    # Proporcional: agrupa dias pelo mês de chegada
    por_mes_chegada = {}
    for d in dias:
        chegada = somar_dias_iso(d["data"], -antecedencia)
        mes = mes_ano_iso(chegada)
        if mes not in por_mes_chegada:
            por_mes_chegada[mes] = {"peso": 0.0, "offset": 0.0, "por_fis": {}}
        b = por_mes_chegada[mes]
        b["peso"] += d["peso"]
        b["offset"] += d["peso"] * diferenca_dias(data_inicio, chegada)
        fis = mes_ano_iso(d["data"])
        b["por_fis"][fis] = b["por_fis"].get(fis, 0.0) + d["peso"]

    for b in por_mes_chegada.values():
        if b["peso"] > 0:
            avg_offset = round(b["offset"] / b["peso"])
            data_deliv = somar_dias_iso(data_inicio, avg_offset)
            _adicionar_entrega(data_deliv, b["por_fis"], f"chega {antecedencia} dias antes da execução")

    return {"eventos": eventos, "fluxos": agregar_fluxos(brutos)}


def mao_de_obra_com_fluxos(
    custo: float,
    data_inicio: str,
    data_fim: str,
    dia_corte_mo: int = 20,
    dia_pagamento_mo: int = 5,
    retencao_percentual: float = 0.0,
    data_liberacao_retencao: Optional[str] = None,
    pontos_mensais: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Mão de Obra: segue o físico diário da etapa.
    - Competência: cada dia executado de 21/M-1 a 20/M cai no mês M (corte `dia_corte_mo`)
    - Financeiro: desembolso no dia `dia_pagamento_mo` de M+1
    - Retenção técnica: `retencao_percentual`% de cada medição só é paga em `data_liberacao_retencao` (1 ano após obra)
      (A competência não é reduzida!)
    Retorna {'eventos': [...], 'fluxos': [...]}.
    """
    eventos = []
    brutos = []
    valor = float(custo or 0.0)
    if valor <= 0 or not data_inicio:
        return {"eventos": eventos, "fluxos": []}

    fim = data_fim if (data_fim and data_fim >= data_inicio) else data_inicio
    por_competencia = {}
    for d in fisico_diario(data_inicio, fim, pontos_mensais):
        comp = mes_competencia_mo(d["data"], dia_corte_mo)
        fis = mes_ano_iso(d["data"])
        if comp not in por_competencia:
            por_competencia[comp] = {"valor": 0.0, "por_fis": {}}
        b = por_competencia[comp]
        b["valor"] += valor * d["peso"]
        b["por_fis"][fis] = b["por_fis"].get(fis, 0.0) + valor * d["peso"]

    fracao_retida = min(1.0, float(retencao_percentual) / 100.0) if (data_liberacao_retencao and float(retencao_percentual or 0) > 0) else 0.0

    for mes_comp, b in por_competencia.items():
        total = round(b["valor"], 2)
        retido = round(total * fracao_retida, 2)
        data_pag = data_pagamento_mo(mes_comp, dia_pagamento_mo)
        eventos.append({
            "tipo": "MAO_DE_OBRA",
            "mesCompetencia": mes_comp,
            "mesFinanceiro": mes_ano_iso(data_pag),
            "dataPagamento": data_pag,
            "valor": round(total - retido, 2),
        })
        if retido > 0:
            eventos.append({
                "tipo": "MAO_DE_OBRA",
                "mesCompetencia": mes_comp,
                "mesFinanceiro": mes_ano_iso(data_liberacao_retencao),
                "dataPagamento": data_liberacao_retencao,
                "valor": retido,
                "retencao": True,
            })
        for fis, v in b["por_fis"].items():
            m_comp = f"dias 1 a {dia_corte_mo}" if fis == mes_comp else f"dias {dia_corte_mo + 1} em diante (corte dia {dia_corte_mo})"
            data_pag_d = int(data_pag[8:10]) if len(data_pag) >= 10 else 5
            brutos.append({
                "tipo": "MAO_DE_OBRA",
                "fis": fis,
                "comp": mes_comp,
                "fin": mes_ano_iso(data_pag),
                "valor": v * (1.0 - fracao_retida),
                "mComp": m_comp,
                "mFin": f"pago dia {data_pag_d}"
            })
            if fracao_retida > 0:
                fmt_ret = f"{data_liberacao_retencao[8:10]}/{data_liberacao_retencao[5:7]}/{data_liberacao_retencao[:4]}" if len(data_liberacao_retencao) >= 10 else data_liberacao_retencao
                brutos.append({
                    "tipo": "MAO_DE_OBRA",
                    "fis": fis,
                    "comp": mes_comp,
                    "fin": mes_ano_iso(data_liberacao_retencao),
                    "valor": v * fracao_retida,
                    "mComp": m_comp,
                    "mFin": f"retenção {float(retencao_percentual)}% (liberada em {fmt_ret})"
                })

    return {"eventos": eventos, "fluxos": agregar_fluxos(brutos)}


def matriz_mensal(eventos: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """Por mês: [competência material, competência MO, financeiro material, financeiro MO] (planilha analítica)."""
    m = {}
    for ev in eventos:
        mat = (ev.get("tipo") == "MATERIAL")
        val = float(ev.get("valor") or 0.0)
        m_comp = ev.get("mesCompetencia")
        m_fin = ev.get("mesFinanceiro")
        if m_comp:
            if m_comp not in m:
                m[m_comp] = [0.0, 0.0, 0.0, 0.0]
            idx = 0 if mat else 1
            m[m_comp][idx] = round(m[m_comp][idx] + val, 2)
        if m_fin:
            if m_fin not in m:
                m[m_fin] = [0.0, 0.0, 0.0, 0.0]
            idx = 2 if mat else 3
            m[m_fin][idx] = round(m[m_fin][idx] + val, 2)
    return m



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


# ==============================================================================
# Motor Avançado: Cálculo de Curvas & Realizado + Projeção
# ==============================================================================

def definicao_para_tipo(def_val: Any) -> Optional[str]:
    """Classificação de insumos padrão: SE = mão de obra; MT, EQ e OU = material."""
    if not def_val:
        return None
    d = str(def_val).strip().upper()
    if d in ("SE", "SERVICO", "SERVIÇO", "MAO_DE_OBRA", "MÃO DE OBRA", "MO"):
        return "MAO_DE_OBRA"
    if d in ("MT", "EQ", "OU", "MAT", "MATERIAL", "EQUIPAMENTO", "OUTROS"):
        return "MATERIAL"
    return None


def classificador(empresa_insumos: Optional[Dict[str, str]] = None, obra_ajustes: Optional[Dict[str, str]] = None):
    """
    Retorna função classificadora com prioridade:
    1. Ajuste manual da obra (por descrição)
    2. Insumo da empresa (por código ou descrição)
    3. Heurística: começa com 'MO ' ou 'SERVIÇO' -> MAO_DE_OBRA; senão MATERIAL.
    """
    emp = empresa_insumos or {}
    obr = obra_ajustes or {}

    def _classificar(descricao: str, cod_insumo: Optional[str] = None) -> str:
        desc_norm = str(descricao or "").strip().upper()
        if desc_norm in obr:
            return obr[desc_norm]
        if cod_insumo and str(cod_insumo) in emp:
            return emp[str(cod_insumo)]
        if desc_norm in emp:
            return emp[desc_norm]
        if desc_norm.startswith("MO ") or "MÃO DE OBRA" in desc_norm or "MAO DE OBRA" in desc_norm or desc_norm.startswith("SE "):
            return "MAO_DE_OBRA"
        return "MATERIAL"

    return _classificar


def calcular_curvas_financeiras(
    etapas: List[Dict[str, Any]],
    parametros_obra: Optional[Dict[str, Any]] = None,
    parametros_etapas: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    niveis1_excluidos: Optional[List[str]] = None,
    vinculos: Optional[Dict[str, str]] = None,
    projetado_fora: float = 0.0
) -> Dict[str, Any]:
    """
    Motor Principal das Curvas Físico-Financeiras Avançadas.
    Integra Custo Projetado (Material x MO) com Cronograma Físico.
    Retorna kpis, meses, seriesMensal, etapas calculadas com fluxos, matriz_analitica e curvas S.
    """
    params_obra = dict(parametros_obra or {})
    dia_corte_mo = int(params_obra.get("dia_corte_medicao_mo") or 20)
    antecedencia_padrao = int(params_obra.get("dias_antecedencia_padrao") if params_obra.get("dias_antecedencia_padrao") is not None else 10)
    prazo_padrao = int(params_obra.get("prazo_pagamento_padrao_dias") if params_obra.get("prazo_pagamento_padrao_dias") is not None else 28)
    dia_pagamento_mo = int(params_obra.get("dia_pagamento_mo") or 5)

    excluidos_raw = niveis1_excluidos if niveis1_excluidos is not None else params_obra.get("niveis1_excluidos", [])
    excluidos_set = set(nivel1_do_codigo(x) for x in excluidos_raw)

    # Determina data fim da obra para retenção técnica
    data_fim_etapas = None
    for e in etapas:
        f = e.get("data_fim") or e.get("finish")
        if f and (not data_fim_etapas or str(f) > str(data_fim_etapas)):
            data_fim_etapas = str(f)[:10]

    data_fim_obra = params_obra.get("data_fim_obra") or data_fim_etapas or "2026-12-31"
    data_liberacao_retencao = somar_um_ano_iso(data_fim_obra)

    todos_eventos = []
    etapas_calculadas = []
    total_orcado_geral = 0.0
    total_material_geral = 0.0
    total_mo_geral = 0.0

    meses_set = set()

    # Prepara mapa de regras por etapa
    param_etapas_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(parametros_etapas, dict):
        param_etapas_map = parametros_etapas
    elif isinstance(parametros_etapas, list):
        for p in parametros_etapas:
            cod = p.get("codigo_etapa") or p.get("code")
            tipo = p.get("tipo", "MATERIAL")
            if cod:
                param_etapas_map[f"{cod}|{tipo}"] = p
                param_etapas_map[str(cod)] = p

    for etapa in etapas:
        cod = str(etapa.get("codigo_etapa") or etapa.get("code") or "").strip()
        n1 = nivel1_do_codigo(cod)
        if n1 in excluidos_set:
            continue

        c_mat = float(etapa.get("custo_material") or 0.0)
        c_mo = float(etapa.get("custo_mao_obra") or 0.0)
        c_tot = float(etapa.get("custo_total") or (c_mat + c_mo))
        if c_mat + c_mo == 0.0 and c_tot > 0:
            c_mat = round(c_tot * 0.6, 2)
            c_mo = round(c_tot - c_mat, 2)

        total_material_geral += c_mat
        total_mo_geral += c_mo
        total_orcado_geral += (c_mat + c_mo)

        # Resolução de regras
        regra_mat = param_etapas_map.get(f"{cod}|MATERIAL") or param_etapas_map.get(cod) or {}
        regra_mo = param_etapas_map.get(f"{cod}|MAO_DE_OBRA") or param_etapas_map.get(cod) or {}

        ant_mat = int(regra_mat.get("dias_antecedencia") if regra_mat.get("dias_antecedencia") is not None else (regra_mat.get("anticipation_days") if regra_mat.get("anticipation_days") is not None else antecedencia_padrao))
        praz_mat = int(regra_mat.get("prazo_dias") if regra_mat.get("prazo_dias") is not None else prazo_padrao)
        n_entregas = regra_mat.get("num_entregas") or regra_mat.get("num_batches")
        tipo_pag = regra_mat.get("tipo_pagamento") or ("PARCELADO" if regra_mat.get("parcelas_dias") else "DIAS")
        parcelas = regra_mat.get("parcelas_dias")
        parcelas_pct = regra_mat.get("parcelas_pct")

        if not parcelas and regra_mat.get("payment_terms"):
            terms = parse_payment_terms(regra_mat.get("payment_terms"))
            if len(terms) > 1:
                tipo_pag = "PARCELADO"
                parcelas = [t[0] for t in terms]
                parcelas_pct = [t[1] * 100 for t in terms]
            elif len(terms) == 1:
                praz_mat = terms[0][0]

        ret_ativa = bool(regra_mo.get("retencao_ativa", params_obra.get("retencao_mo_ativa", False)))
        ret_pct = float(regra_mo.get("retencao_percentual") if regra_mo.get("retencao_percentual") is not None else params_obra.get("retencao_mo_percentual", 5.0)) if ret_ativa else 0.0

        d_ini = str(etapa.get("data_inicio") or etapa.get("start") or "")[:10]
        d_fim = str(etapa.get("data_fim") or etapa.get("finish") or "")[:10]
        pts = etapa.get("pontos_mensais")

        # 1. Distribuir Material
        mat_res = material_com_fluxos(
            custo=c_mat,
            data_inicio=d_ini,
            data_fim=d_fim,
            dias_antecedencia=ant_mat,
            num_entregas=n_entregas,
            tipo_pagamento=tipo_pag,
            prazo_dias=praz_mat,
            parcelas_dias=parcelas,
            parcelas_pct=parcelas_pct,
            pontos_mensais=pts
        ) if c_mat > 0 else {"eventos": [], "fluxos": []}

        # 2. Distribuir Mão de Obra
        mo_res = mao_de_obra_com_fluxos(
            custo=c_mo,
            data_inicio=d_ini,
            data_fim=d_fim,
            dia_corte_mo=dia_corte_mo,
            dia_pagamento_mo=dia_pagamento_mo,
            retencao_percentual=ret_pct,
            data_liberacao_retencao=data_liberacao_retencao,
            pontos_mensais=pts
        ) if c_mo > 0 else {"eventos": [], "fluxos": []}

        et_eventos = mat_res["eventos"] + mo_res["eventos"]
        et_fluxos = mat_res["fluxos"] + mo_res["fluxos"]
        todos_eventos.extend(et_eventos)

        for ev in et_eventos:
            if ev.get("mesCompetencia"):
                meses_set.add(ev["mesCompetencia"])
            if ev.get("mesFinanceiro"):
                meses_set.add(ev["mesFinanceiro"])

        matriz = matriz_mensal(et_eventos)

        etapas_calculadas.append({
            "codigo_etapa": cod,
            "nome": etapa.get("nome") or etapa.get("descricao") or etapa.get("description", ""),
            "nivel": etapa.get("level") or etapa.get("nivel") or 5,
            "custo_material": c_mat,
            "custo_mao_obra": c_mo,
            "custo_total": round(c_mat + c_mo, 2),
            "data_inicio": d_ini,
            "data_fim": d_fim,
            "eventos": et_eventos,
            "fluxos": et_fluxos,
            "matriz_mensal": matriz
        })

    meses_sorted = sorted(list(meses_set))
    if not meses_sorted:
        meses_sorted = [datetime.date.today().strftime("%Y-%m")]

    series_mensal = []
    comp_acc = 0.0
    fin_acc = 0.0

    comp_month_map = {m: 0.0 for m in meses_sorted}
    comp_mat_month_map = {m: 0.0 for m in meses_sorted}
    comp_mo_month_map = {m: 0.0 for m in meses_sorted}
    fin_month_map = {m: 0.0 for m in meses_sorted}
    fin_mat_month_map = {m: 0.0 for m in meses_sorted}
    fin_mo_month_map = {m: 0.0 for m in meses_sorted}

    for ev in todos_eventos:
        m_comp = ev.get("mesCompetencia")
        m_fin = ev.get("mesFinanceiro")
        val = float(ev.get("valor") or 0.0)
        is_mat = (ev.get("tipo") == "MATERIAL")

        if m_comp and m_comp in comp_month_map:
            comp_month_map[m_comp] += val
            if is_mat:
                comp_mat_month_map[m_comp] += val
            else:
                comp_mo_month_map[m_comp] += val

        if m_fin and m_fin in fin_month_map:
            fin_month_map[m_fin] += val
            if is_mat:
                fin_mat_month_map[m_fin] += val
            else:
                fin_mo_month_map[m_fin] += val

    for m in meses_sorted:
        c_val = round(comp_month_map[m], 2)
        f_val = round(fin_month_map[m], 2)
        comp_acc += c_val
        fin_acc += f_val
        comp_acc_r = round(comp_acc, 2)
        fin_acc_r = round(fin_acc, 2)
        base = total_orcado_geral if total_orcado_geral > 0 else 1.0

        series_mensal.append({
            "mes": m,
            "competenciaMaterial": round(comp_mat_month_map[m], 2),
            "competenciaMaoDeObra": round(comp_mo_month_map[m], 2),
            "competenciaMensal": c_val,
            "competenciaAcumulada": comp_acc_r,
            "competenciaAcumuladaPct": round((comp_acc_r / base) * 100.0, 2),
            "financeiroMaterial": round(fin_mat_month_map[m], 2),
            "financeiroMaoDeObra": round(fin_mo_month_map[m], 2),
            "financeiroMensal": f_val,
            "financeiroAcumulado": fin_acc_r,
            "financeiroAcumuladoPct": round((fin_acc_r / base) * 100.0, 2),
        })

    return {
        "kpis": {
            "totalOrcado": round(total_orcado_geral, 2),
            "totalMaterial": round(total_material_geral, 2),
            "totalMaoDeObra": round(total_mo_geral, 2),
            "dataFimObraEtapas": data_fim_etapas,
            "dataLiberacaoRetencao": data_liberacao_retencao,
            "inicioProjecao": meses_sorted[0] if meses_sorted else ""
        },
        "meses": meses_sorted,
        "seriesMensal": series_mensal,
        "etapas": etapas_calculadas,
        "s_curves_comparison": {
            "labels": [f"{m[5:7]}/{m[2:4]}" for m in meses_sorted],
            "full_labels": [m for m in meses_sorted],
            "comp_month_vals": [s["competenciaMensal"] for s in series_mensal],
            "comp_accum_vals": [s["competenciaAcumulada"] for s in series_mensal],
            "comp_accum_pcts": [s["competenciaAcumuladaPct"] for s in series_mensal],
            "fin_month_vals": [s["financeiroMensal"] for s in series_mensal],
            "fin_accum_vals": [s["financeiroAcumulado"] for s in series_mensal],
            "fin_accum_pcts": [s["financeiroAcumuladoPct"] for s in series_mensal],
        }
    }


def projetar_realizado(
    etapas: List[Dict[str, Any]],
    parametros_obra: Optional[Dict[str, Any]] = None,
    parametros_etapas: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    corte: Optional[str] = None,
    realizado: Optional[List[Dict[str, Any]]] = None,
    pagamentos: Optional[Dict[Any, List[Dict[str, Any]]]] = None,
    projetado_fora: float = 0.0
) -> Dict[str, Any]:
    """
    Realizado + Projeção:
    - Até o corte (AAAA-MM): Competência = Apropriado/Incorrido por data documento.
      Financeiro = Pagos da Conciliação Financeira por vencimento (saldo em aberto vencido vai para o mês seguinte).
    - Pós-corte: Saldo de cada etapa (Custo Projetado − Incorrido) projetado pelo físico restante.
      - Se saldo < 0: Excedente (alerta vermelho, 0 projetado).
      - Se saldo > 0 e sem físico futuro: Pendente (alerta vermelho, 0 projetado).
      - Se saldo > 0 e com físico futuro: Projetado estritamente pelas regras no cronograma restante.
    """
    params_obra = dict(parametros_obra or {})
    teorica = calcular_curvas_financeiras(
        etapas=etapas,
        parametros_obra=params_obra,
        parametros_etapas=parametros_etapas,
        projetado_fora=projetado_fora
    )

    corte_str = corte or mes_anterior_iso(datetime.date.today().strftime("%Y-%m"))
    fim_corte = f"{corte_str}-{ultimo_dia_do_mes(corte_str):02d}"
    pos_corte = proximo_mes_iso(corte_str)
    inicio_pos = f"{pos_corte}-01"

    dia_pagamento_mo = int(params_obra.get("dia_pagamento_mo") or 5)
    prazo_padrao = int(params_obra.get("prazo_pagamento_padrao_dias") if params_obra.get("prazo_pagamento_padrao_dias") is not None else 28)
    data_liberacao_retencao = teorica["kpis"]["dataLiberacaoRetencao"]

    por_codigo = {str(e.get("codigo_etapa") or e.get("code")): e for e in etapas}
    pagamentos_map = pagamentos or {}

    meses_data: Dict[str, Dict[str, float]] = {}

    def _somar(mes: str, campo: str, val: float):
        if not mes:
            return
        if mes not in meses_data:
            meses_data[mes] = {"compMat": 0.0, "compMo": 0.0, "compFora": 0.0, "finMat": 0.0, "finMo": 0.0, "finFora": 0.0}
        meses_data[mes][campo] += val

    def _somar_comp(mes: str, tipo: str, fora: bool, val: float):
        _somar(mes, "compMat" if tipo == "MATERIAL" else "compMo", val)
        if fora:
            _somar(mes, "compFora", val)

    def _somar_fin(mes: str, tipo: str, fora: bool, val: float):
        _somar(mes, "finMat" if tipo == "MATERIAL" else "finMo", val)
        if fora:
            _somar(mes, "finFora", val)

    # 1. Realizado até o corte
    real_por_chave: Dict[str, float] = {}
    fora_do_cronograma = 0.0
    realizado_sem_pagamento = 0.0
    realizado_ate_corte = 0.0
    realizado_financeiro_ate_corte = 0.0
    aberto_vencido = 0.0

    for ap_key, parcelas in pagamentos_map.items():
        for p in parcelas:
            venc = str(p.get("vencimento") or "")[:10]
            if not venc or venc > fim_corte:
                continue
            realizado_financeiro_ate_corte += float(p.get("pago") or 0.0)
            aberto_vencido += float(p.get("saldo") or 0.0)

    tem_pagamentos = len(pagamentos_map) > 0
    mix_ap: Dict[str, Dict[str, float]] = {}

    def _mes_financeiro_real(mes_fin: str) -> str:
        return pos_corte if (tem_pagamentos and mes_fin <= corte_str) else mes_fin

    realizado_list = realizado or []
    for r in realizado_list:
        val = float(r.get("valor") or 0.0)
        dt = str(r.get("data") or fim_corte)[:10]
        if val <= 0 or dt > fim_corte:
            continue

        mes = mes_ano_iso(dt)
        cod = str(r.get("codigo_etapa") or "").strip()
        etapa = por_codigo.get(cod)
        fora = (etapa is None)
        tipo = r.get("tipo", "MATERIAL")
        chave = f"{cod}|{tipo}"
        realizado_ate_corte += val

        ap_id = r.get("ap")
        if ap_id is not None:
            mix = mix_ap.setdefault(str(ap_id), {})
            kmix = f"{tipo}|{1 if fora else 0}"
            mix[kmix] = mix.get(kmix, 0.0) + val

        _somar_comp(mes, tipo, fora, val)
        if fora:
            fora_do_cronograma += val
        else:
            real_por_chave[chave] = real_por_chave.get(chave, 0.0) + val

        parcelas = pagamentos_map.get(str(ap_id)) or pagamentos_map.get(ap_id) if ap_id is not None else None
        total_ap = sum(float(p.get("valor") or 0.0) for p in (parcelas or []))

        if total_ap > 0 and parcelas:
            for p in parcelas:
                p_val = float(p.get("valor") or 0.0)
                parte = (val * p_val) / total_ap
                p_venc = str(p.get("vencimento") or "")[:10]
                mes_v = mes_ano_iso(p_venc)
                p_saldo = float(p.get("saldo") or 0.0)
                aberto = (parte * min(1.0, max(0.0, p_saldo / p_val))) if (mes_v <= corte_str and p_val > 0) else 0.0
                if mes_v > corte_str and parte > 0:
                    _somar_fin(mes_v, tipo, fora, parte)
                if aberto > 0:
                    _somar_fin(pos_corte, tipo, fora, aberto)
            continue

        realizado_sem_pagamento += val
        if tipo == "MATERIAL":
            _somar_fin(_mes_financeiro_real(mes_ano_iso(somar_dias_iso(dt, prazo_padrao))), tipo, fora, val)
        else:
            _somar_fin(_mes_financeiro_real(mes_ano_iso(data_pagamento_mo(mes, dia_pagamento_mo))), tipo, fora, val)

    # Pago da conciliação por mês de vencimento, repartido pelo mix de apropriação
    for ap_key, parcelas in pagamentos_map.items():
        mix = mix_ap.get(str(ap_key))
        total_mix = sum(mix.values()) if mix else 0.0
        for p in parcelas:
            pago = float(p.get("pago") or 0.0)
            venc = str(p.get("vencimento") or "")[:10]
            if pago <= 0 or not venc or venc > fim_corte:
                continue
            mes_v = mes_ano_iso(venc)
            if total_mix > 0 and mix:
                for kmix, v in mix.items():
                    k_tipo, k_fora = kmix.split("|")
                    _somar_fin(mes_v, k_tipo, k_fora == "1", (pago * v) / total_mix)
            else:
                _somar_fin(mes_v, "MATERIAL", False, pago)

    # 2. Saldo por etapa e tipo
    def _tem_fisico_depois(e: Dict[str, Any]) -> bool:
        pts = e.get("pontos_mensais")
        if isinstance(pts, list) and pts:
            return any(mes_ano_iso(p.get("data")) > corte_str and float(p.get("previsto") if p.get("previsto") is not None else (p.get("base") or 0.0)) > 0 for p in pts)
        d_fim = e.get("data_fim") or e.get("finish") or e.get("data_inicio")
        return bool(d_fim and str(d_fim)[:10] > fim_corte)

    resumo = []
    clones = []

    for e in etapas:
        cod = str(e.get("codigo_etapa") or e.get("code") or "")
        custo_mat = float(e.get("custo_material") or 0.0)
        custo_mo = float(e.get("custo_mao_obra") or 0.0)
        futuro = _tem_fisico_depois(e)

        r = {
            "codigo_etapa": cod,
            "nome": e.get("nome") or e.get("descricao") or "",
            "projetado": round(custo_mat + custo_mo, 2),
            "realizado": 0.0,
            "saldoProjetado": 0.0,
            "excedente": 0.0,
            "pendente": 0.0,
            "alerta": None
        }

        real_mat = real_por_chave.get(f"{cod}|MATERIAL", 0.0)
        real_mo = real_por_chave.get(f"{cod}|MAO_DE_OBRA", 0.0)
        r["realizado"] = round(real_mat + real_mo, 2)
        saldo = round(r["projetado"] - r["realizado"], 2)

        a_projetar_mat = 0.0
        a_projetar_mo = 0.0

        if saldo < 0:
            r["excedente"] = round(-saldo, 2)
            r["alerta"] = "excedente"
        elif saldo > 0 and not futuro:
            r["pendente"] = saldo
            r["alerta"] = "pendente"
        elif saldo > 0:
            r["saldoProjetado"] = saldo
            falta_mat = max(0.0, custo_mat - real_mat)
            falta_mo = max(0.0, custo_mo - real_mo)
            peso_mat = falta_mat if (falta_mat + falta_mo > 0) else custo_mat
            peso_mo = falta_mo if (falta_mat + falta_mo > 0) else custo_mo
            tot_peso = peso_mat + peso_mo
            if tot_peso > 0:
                a_projetar_mat = (saldo * peso_mat) / tot_peso
                a_projetar_mo = saldo - a_projetar_mat
            else:
                a_projetar_mat = round(saldo * 0.6, 2)
                a_projetar_mo = saldo - a_projetar_mat

        if a_projetar_mat > 0 or a_projetar_mo > 0:
            clone_e = dict(e)
            clone_e["custo_material"] = a_projetar_mat
            clone_e["custo_mao_obra"] = a_projetar_mo
            clone_e["custo_total"] = a_projetar_mat + a_projetar_mo
            d_ini = clone_e.get("data_inicio")
            clone_e["data_inicio"] = max(str(d_ini)[:10], inicio_pos) if d_ini else inicio_pos
            pts = clone_e.get("pontos_mensais")
            if isinstance(pts, list):
                clone_e["pontos_mensais"] = [
                    (dict(p, previsto=0.0, base=0.0) if mes_ano_iso(p.get("data")) <= corte_str else dict(p))
                    for p in pts
                ]
            clones.append(clone_e)

        if r["projetado"] > 0 or r["realizado"] > 0:
            resumo.append(r)

    # 3. Executa Projeção Futura
    projecao = calcular_curvas_financeiras(
        etapas=clones,
        parametros_obra=params_obra,
        parametros_etapas=parametros_etapas
    )

    for et in projecao["etapas"]:
        for ev in et.get("eventos", []):
            m_comp = ev.get("mesCompetencia")
            m_fin = ev.get("mesFinanceiro")
            val = float(ev.get("valor") or 0.0)
            tipo = ev.get("tipo", "MATERIAL")
            m_comp_final = pos_corte if (m_comp and m_comp <= corte_str) else m_comp
            m_fin_final = pos_corte if (m_fin and m_fin <= corte_str) else m_fin
            _somar_comp(m_comp_final, tipo, False, val)
            _somar_fin(m_fin_final, tipo, False, val)

    # 4. Séries consolidadas
    teorica_por_mes = {s["mes"]: s for s in teorica["seriesMensal"]}
    todos_meses = sorted(list(set(list(meses_data.keys()) + list(teorica_por_mes.keys()))))

    vazio = {"compMat": 0.0, "compMo": 0.0, "compFora": 0.0, "finMat": 0.0, "finMo": 0.0, "finFora": 0.0}
    teorico_ate_corte = 0.0
    teorico_fin_ate_corte = 0.0

    series_mensal = []
    comp_acc = 0.0
    fin_acc = 0.0

    for m in todos_meses:
        v = meses_data.get(m, vazio)
        t = teorica_por_mes.get(m, {})
        if m <= corte_str:
            teorico_ate_corte += float(t.get("competenciaMensal") or 0.0)
            teorico_fin_ate_corte += float(t.get("financeiroMensal") or 0.0)

        c_mat = round(v["compMat"], 2)
        c_mo = round(v["compMo"], 2)
        c_tot = round(c_mat + c_mo, 2)
        f_mat = round(v["finMat"], 2)
        f_mo = round(v["finMo"], 2)
        f_tot = round(f_mat + f_mo, 2)

        comp_acc += c_tot
        fin_acc += f_tot

        series_mensal.append({
            "mes": m,
            "realizado": (m <= corte_str),
            "competenciaMaterial": c_mat,
            "competenciaMaoDeObra": c_mo,
            "competenciaForaCronograma": round(v["compFora"], 2),
            "competenciaMensal": c_tot,
            "competenciaAcumulada": round(comp_acc, 2),
            "financeiroMaterial": f_mat,
            "financeiroMaoDeObra": f_mo,
            "financeiroForaCronograma": round(v["finFora"], 2),
            "financeiroMensal": f_tot,
            "financeiroAcumulado": round(fin_acc, 2),
            "teoricoCompetenciaMaterial": t.get("competenciaMaterial", 0.0),
            "teoricoCompetenciaMaoDeObra": t.get("competenciaMaoDeObra", 0.0),
            "teoricoCompetenciaMensal": t.get("competenciaMensal", 0.0),
            "teoricoFinanceiroMaterial": t.get("financeiroMaterial", 0.0),
            "teoricoFinanceiroMaoDeObra": t.get("financeiroMaoDeObra", 0.0),
            "teoricoFinanceiroMensal": t.get("financeiroMensal", 0.0),
        })

    base_orc = teorica["kpis"]["totalOrcado"]
    custo_proj_total = round(base_orc + float(projetado_fora or 0.0), 2)
    desvio = round(realizado_ate_corte - teorico_ate_corte, 2)
    desvio_fin = round(realizado_financeiro_ate_corte - teorico_fin_ate_corte, 2)

    return {
        "corte": corte_str,
        "seriesMensal": series_mensal,
        "etapas": resumo,
        "kpis": {
            "base": base_orc,
            "custoProjetado": custo_proj_total,
            "foraProjetado": round(float(projetado_fora or 0.0), 2),
            "realizadoAteCorte": round(realizado_ate_corte, 2),
            "realizadoFinanceiroAteCorte": round(realizado_financeiro_ate_corte, 2),
            "teoricoAteCorte": round(teorico_ate_corte, 2),
            "teoricoFinanceiroAteCorte": round(teorico_fin_ate_corte, 2),
            "desvio": desvio,
            "desvioPct": round((desvio / base_orc) * 100.0, 2) if base_orc > 0 else 0.0,
            "desvioFinanceiro": desvio_fin,
            "desvioFinanceiroPct": round((desvio_fin / base_orc) * 100.0, 2) if base_orc > 0 else 0.0,
            "saldoCompetencia": round(custo_proj_total - realizado_ate_corte, 2),
            "saldoFinanceiro": round(custo_proj_total - realizado_financeiro_ate_corte, 2),
            "abertoVencido": round(aberto_vencido, 2),
            "saldoProjetado": round(sum(r["saldoProjetado"] for r in resumo), 2),
            "excedente": round(sum(r["excedente"] for r in resumo), 2),
            "pendente": round(sum(r["pendente"] for r in resumo), 2),
            "foraDoCronograma": round(fora_do_cronograma, 2),
            "custoFinalEstimado": custo_proj_total,
            "realizadoSemPagamento": round(realizado_sem_pagamento, 2),
            "inicioTeorico": teorica["kpis"]["inicioProjecao"],
            "dataLiberacaoRetencao": data_liberacao_retencao
        }
    }


# ==============================================================================
# Parsers de Arquivos Excel: Custo Projetado, Incorrido e Conciliação Financeira
# ==============================================================================

def _parse_num(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("R$", "").replace(" ", "")
    # Brasil: 1.234,56
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_custo_projetado_excel(file_content: bytes) -> Dict[str, Any]:
    """
    Lê a planilha de Custo Projetado (.xlsx) e separa os custos por etapa N5 e tipo (Material x MO).
    Retorna dicionário com 'itens' (por etapa N5), 'linhas' detalhadas, 'total', 'total_mat', 'total_mo'.
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        return {"itens": {}, "linhas": [], "total": 0.0, "total_mat": 0.0, "total_mo": 0.0}

    # Procura cabeçalho
    def _norm(s: Any) -> str:
        return str(s or "").strip().lower()

    header_idx = -1
    col_code = -1
    col_desc = -1
    col_val = -1
    col_tipo = -1

    for idx, r in enumerate(rows[:20]):
        row_str = [_norm(c) for c in r]
        for c_i, h in enumerate(row_str):
            if any(k in h for k in ["código", "codigo", "cod_estruturado", "etapa"]):
                col_code = c_i
            elif any(k in h for k in ["descrição", "descricao", "item"]):
                col_desc = c_i
            elif any(k in h for k in ["projetado", "custo", "valor", "orçamento"]):
                col_val = c_i
            elif any(k in h for k in ["definição", "definicao", "classe", "tipo"]):
                col_tipo = c_i
        if col_code >= 0 and col_val >= 0:
            header_idx = idx
            break

    if header_idx < 0:
        # Fallback para colunas 0, 1, 2
        col_code = 0
        col_desc = 1
        col_val = 2
        header_idx = 0

    por_etapa: Dict[str, Dict[str, Any]] = {}
    linhas_det = []
    tot_mat = 0.0
    tot_mo = 0.0

    for r in rows[header_idx + 1:]:
        if not r or all(c is None for c in r):
            continue
        raw_code = str(r[col_code] or "").strip()
        if not raw_code:
            continue
        # Limpa código estruturado (ex: '01.02.03.04.005 - Alvenaria' -> '01.02.03.04.005')
        cod = raw_code.split(" - ")[0].strip()
        desc = str(r[col_desc] or "").strip() if (col_desc >= 0 and col_desc < len(r) and r[col_desc] is not None) else ""
        val = _parse_num(r[col_val]) if (col_val < len(r)) else 0.0
        if val <= 0:
            continue

        raw_tipo = str(r[col_tipo] or "").strip() if (col_tipo >= 0 and col_tipo < len(r) and r[col_tipo] is not None) else ""
        tipo = definicao_para_tipo(raw_tipo)
        if not tipo:
            tipo = "MAO_DE_OBRA" if (desc.upper().startswith("MO ") or "MÃO DE OBRA" in desc.upper() or "MAO DE OBRA" in desc.upper()) else "MATERIAL"

        if cod not in por_etapa:
            por_etapa[cod] = {"codigo_etapa": cod, "descricao": desc, "material": 0.0, "mao_de_obra": 0.0, "total": 0.0}

        if tipo == "MAO_DE_OBRA":
            por_etapa[cod]["mao_de_obra"] += val
            tot_mo += val
        else:
            por_etapa[cod]["material"] += val
            tot_mat += val

        por_etapa[cod]["total"] += val
        linhas_det.append({
            "codigo_etapa": cod,
            "descricao": desc,
            "valor": round(val, 2),
            "tipo": tipo
        })

    for v in por_etapa.values():
        v["material"] = round(v["material"], 2)
        v["mao_de_obra"] = round(v["mao_de_obra"], 2)
        v["total"] = round(v["total"], 2)

    return {
        "itens": por_etapa,
        "linhas": linhas_det,
        "total": round(tot_mat + tot_mo, 2),
        "total_mat": round(tot_mat, 2),
        "total_mo": round(tot_mo, 2)
    }


def parse_incorrido_excel(file_content: bytes) -> List[Dict[str, Any]]:
    """
    Lê a planilha de Incorrido / Análise do Realizado (.xlsx).
    Retorna lista de {'codigo_etapa', 'data', 'valor', 'tipo', 'ap'}.
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        return []

    def _norm(s: Any) -> str:
        return str(s or "").strip().lower()

    col_code = -1
    col_data = -1
    col_val = -1
    col_ap = -1
    col_desc = -1
    header_idx = -1

    for idx, r in enumerate(rows[:20]):
        row_str = [_norm(c) for c in r]
        for c_i, h in enumerate(row_str):
            if any(k in h for k in ["código", "codigo", "cod_estruturado", "etapa"]):
                col_code = c_i
            elif any(k in h for k in ["data", "emissão", "emissao", "documento"]):
                col_data = c_i
            elif any(k in h for k in ["apropriação", "apropriacao", "valor", "líquido", "liquido"]):
                col_val = c_i
            elif any(k in h for k in ["ap", "título", "titulo", "documento"]):
                col_ap = c_i
            elif any(k in h for k in ["descrição", "descricao", "item"]):
                col_desc = c_i
        if col_code >= 0 and col_val >= 0:
            header_idx = idx
            break

    if header_idx < 0:
        col_code = 0
        col_data = 1
        col_val = 2
        header_idx = 0

    itens = []
    for r in rows[header_idx + 1:]:
        if not r or all(c is None for c in r):
            continue
        raw_code = str(r[col_code] or "").strip()
        if not raw_code:
            continue
        cod = raw_code.split(" - ")[0].strip()
        val = _parse_num(r[col_val]) if (col_val >= 0 and col_val < len(r)) else 0.0
        if val <= 0:
            continue

        dt_val = r[col_data] if (col_data >= 0 and col_data < len(r)) else None
        dt_str = None
        if isinstance(dt_val, (datetime.date, datetime.datetime)):
            dt_str = dt_val.strftime("%Y-%m-%d")
        elif dt_val:
            s_dt = str(dt_val).strip()
            if "/" in s_dt:
                parts = s_dt.split("/")
                if len(parts) == 3:
                    dt_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            elif "-" in s_dt and len(s_dt) >= 10:
                dt_str = s_dt[:10]

        ap_val = r[col_ap] if (col_ap >= 0 and col_ap < len(r) and r[col_ap] is not None) else None
        desc_val = str(r[col_desc] or "").strip().upper() if (col_desc >= 0 and col_desc < len(r) and r[col_desc] is not None) else ""
        tipo = "MAO_DE_OBRA" if (desc_val.startswith("MO ") or "MÃO DE OBRA" in desc_val or "MAO DE OBRA" in desc_val or "SERVIÇO" in desc_val) else "MATERIAL"

        itens.append({
            "codigo_etapa": cod,
            "data": dt_str or datetime.date.today().strftime("%Y-%m-%d"),
            "valor": round(val, 2),
            "tipo": tipo,
            "ap": str(ap_val) if ap_val is not None else None
        })

    return itens


def parse_conciliacao_financeira_excel(file_content: bytes) -> Dict[str, List[Dict[str, Any]]]:
    """
    Lê a planilha de Conciliação Financeira / Pagamentos (.xlsx) do Mega.
    Retorna dicionário agrupado por AP: { ap_id: [ { 'parcela', 'vencimento', 'valor', 'pago', 'saldo' } ] }.
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        return {}

    def _norm(s: Any) -> str:
        return str(s or "").strip().lower()

    col_ap = -1
    col_parc = -1
    col_venc = -1
    col_val = -1
    col_pago = -1
    col_saldo = -1
    col_cod = -1
    header_idx = -1

    for idx, r in enumerate(rows[:20]):
        row_str = [_norm(c) for c in r]
        for c_i, h in enumerate(row_str):
            if "ap" in h:
                col_ap = c_i
            elif "parcela" in h:
                col_parc = c_i
            elif "vencimento" in h:
                col_venc = c_i
            elif any(k in h for k in ["rateado", "valor"]):
                col_val = c_i
            elif any(k in h for k in ["pagamentos", "pago"]):
                col_pago = c_i
            elif any(k in h for k in ["saldo", "pagar"]):
                col_saldo = c_i
            elif any(k in h for k in ["estruturado", "etapa"]):
                col_cod = c_i
        if col_ap >= 0 and (col_pago >= 0 or col_saldo >= 0 or col_val >= 0):
            header_idx = idx
            break

    if header_idx < 0:
        return {}

    mapa_aps: Dict[str, List[Dict[str, Any]]] = {}

    for r in rows[header_idx + 1:]:
        if not r or all(c is None for c in r):
            continue
        raw_ap = r[col_ap] if col_ap < len(r) else None
        if raw_ap is None or not str(raw_ap).strip():
            continue
        ap_str = str(raw_ap).strip()

        venc_val = r[col_venc] if (col_venc >= 0 and col_venc < len(r)) else None
        venc_str = None
        if isinstance(venc_val, (datetime.date, datetime.datetime)):
            venc_str = venc_val.strftime("%Y-%m-%d")
        elif venc_val:
            s_v = str(venc_val).strip()
            if "/" in s_v:
                parts = s_v.split("/")
                if len(parts) == 3:
                    venc_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            elif "-" in s_v and len(s_v) >= 10:
                venc_str = s_v[:10]

        val = _parse_num(r[col_val]) if (col_val >= 0 and col_val < len(r)) else 0.0
        pago = _parse_num(r[col_pago]) if (col_pago >= 0 and col_pago < len(r)) else 0.0
        saldo = _parse_num(r[col_saldo]) if (col_saldo >= 0 and col_saldo < len(r)) else max(0.0, val - pago)

        parc = str(r[col_parc] or "1") if (col_parc >= 0 and col_parc < len(r) and r[col_parc] is not None) else "1"
        cod_est = str(r[col_cod] or "").split(" - ")[0].strip() if (col_cod >= 0 and col_cod < len(r) and r[col_cod] is not None) else None

        parcela_obj = {
            "parcela": parc,
            "vencimento": venc_str,
            "valor": round(val, 2),
            "pago": round(pago, 2),
            "saldo": round(saldo, 2),
            "cod_estruturado": cod_est
        }

        mapa_aps.setdefault(ap_str, []).append(parcela_obj)

    return mapa_aps


# ==============================================================================
# Persistência de Dados das Curvas (Config, Custo Projetado, Incorrido, Pagamentos)
# ==============================================================================

def load_curvas_data(project_id: str) -> Dict[str, Any]:
    """Carrega dados persistidos (Custo Projetado, Incorrido, Pagamentos, Vínculos, Versões)."""
    proj_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(proj_dir, exist_ok=True)

    dados: Dict[str, Any] = {
        "custo_projetado": None,
        "incorrido": None,
        "pagamentos": None,
        "vinculos": {},
        "versoes": []
    }

    # Tenta carregar do banco primeiro
    try:
        from ..database import get_domain_edits_db
        cp_db = get_domain_edits_db(project_id, "custo_projetado")
        if cp_db:
            dados["custo_projetado"] = cp_db
        inc_db = get_domain_edits_db(project_id, "incorrido")
        if inc_db:
            dados["incorrido"] = inc_db
        pag_db = get_domain_edits_db(project_id, "pagamentos")
        if pag_db:
            dados["pagamentos"] = pag_db
        vinc_db = get_domain_edits_db(project_id, "curvas_vinculos")
        if vinc_db:
            dados["vinculos"] = vinc_db
        vers_db = get_domain_edits_db(project_id, "curvas_versoes")
        if vers_db and isinstance(vers_db, list):
            dados["versoes"] = vers_db
    except Exception:
        pass

    # Fallback para arquivos locais em data/projects/<project_id>/
    for k in ["custo_projetado", "incorrido", "pagamentos", "vinculos", "versoes"]:
        if not dados[k]:
            f_path = os.path.join(proj_dir, f"{k}.json")
            if os.path.exists(f_path):
                try:
                    with open(f_path, "r", encoding="utf-8") as f:
                        dados[k] = json.load(f)
                except Exception:
                    pass

    return dados


def save_custo_projetado_data(project_id: str, data: Dict[str, Any]) -> None:
    proj_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(proj_dir, exist_ok=True)
    with open(os.path.join(proj_dir, "custo_projetado.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        from ..database import save_domain_edits_db
        save_domain_edits_db(project_id, "custo_projetado", "atual", data)
    except Exception:
        pass


def save_incorrido_data(project_id: str, data: List[Dict[str, Any]]) -> None:
    proj_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(proj_dir, exist_ok=True)
    with open(os.path.join(proj_dir, "incorrido.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        from ..database import save_domain_edits_db
        save_domain_edits_db(project_id, "incorrido", "atual", {"itens": data})
    except Exception:
        pass


def save_pagamentos_data(project_id: str, data: Dict[str, List[Dict[str, Any]]]) -> None:
    proj_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(proj_dir, exist_ok=True)
    with open(os.path.join(proj_dir, "pagamentos.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        from ..database import save_domain_edits_db
        save_domain_edits_db(project_id, "pagamentos", "atual", data)
    except Exception:
        pass


def save_curvas_vinculo_data(project_id: str, origem: str, destino: Optional[str] = None, remover: bool = False) -> Dict[str, str]:
    dados = load_curvas_data(project_id)
    vinculos = dict(dados.get("vinculos") or {})
    if remover:
        vinculos.pop(origem, None)
    elif destino:
        vinculos[origem] = destino

    proj_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(proj_dir, exist_ok=True)
    with open(os.path.join(proj_dir, "vinculos.json"), "w", encoding="utf-8") as f:
        json.dump(vinculos, f, ensure_ascii=False, indent=2)
    try:
        from ..database import save_domain_edits_db
        save_domain_edits_db(project_id, "curvas_vinculos", "atual", vinculos)
    except Exception:
        pass
    return vinculos


def salvar_versao_curvas(project_id: str, nome: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Salva uma versão congelada do cálculo das curvas."""
    dados = load_curvas_data(project_id)
    versoes = list(dados.get("versoes") or [])
    versao_id = f"v_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    nome_final = str(nome or "").strip() or f"Versão {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"

    nova_versao = {
        "id": versao_id,
        "nome": nome_final,
        "criado_em": datetime.datetime.now().isoformat(),
        "payload": payload or {}
    }
    versoes.insert(0, nova_versao)

    proj_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(proj_dir, exist_ok=True)
    with open(os.path.join(proj_dir, "versoes.json"), "w", encoding="utf-8") as f:
        json.dump(versoes, f, ensure_ascii=False, indent=2)
    try:
        from ..database import save_domain_edits_db
        save_domain_edits_db(project_id, "curvas_versoes", "atual", versoes)
    except Exception:
        pass
    return nova_versao


def listar_versoes_curvas(project_id: str) -> List[Dict[str, Any]]:
    """Lista as versões salvas das curvas da obra."""
    dados = load_curvas_data(project_id)
    return list(dados.get("versoes") or [])


def excluir_versao_curvas(project_id: str, versao_id: str) -> bool:
    """Exclui uma versão salva."""
    dados = load_curvas_data(project_id)
    versoes = [v for v in (dados.get("versoes") or []) if v.get("id") != versao_id]
    proj_dir = os.path.join(PROJECTS_DIR, project_id)
    with open(os.path.join(proj_dir, "versoes.json"), "w", encoding="utf-8") as f:
        json.dump(versoes, f, ensure_ascii=False, indent=2)
    try:
        from ..database import save_domain_edits_db
        save_domain_edits_db(project_id, "curvas_versoes", "atual", versoes)
    except Exception:
        pass
    return True


# Aliases para compatibilidade camelCase
calcularCurvasFinanceiras = calcular_curvas_financeiras
projetarRealizado = projetar_realizado


# ==============================================================================
# Modelos Excel para Download (Custo Projetado, Incorrido, Pagamentos)
# ==============================================================================

def generate_custo_projetado_template() -> bytes:
    """Gera modelo de planilha Excel para importação de Custo Projetado."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Custo_Projetado"

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    headers = [
        "Código Estruturado",
        "Descrição do Item / Insumo",
        "Nível",
        "Definição / Tipo (SE / MT)",
        "Custo Projetado (R$)"
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    sample_rows = [
        ["01.01.001", "Concreto Usinado FCK 30 MPa", 5, "MT", 150000.00],
        ["01.01.001", "MO Aplicação de Concreto Estrutural", 5, "SE", 65000.00],
        ["01.01.002", "Aço CA-50 10mm Cortado e Dobrado", 5, "MT", 120000.00],
        ["01.01.002", "MO Armador de Ferro", 5, "SE", 45000.00],
        ["01.02.001", "Bloco Cerâmico 14x19x29", 5, "MT", 80000.00],
        ["01.02.001", "MO Alvenaria de Vedação", 5, "SE", 50000.00],
    ]

    for row_idx, r in enumerate(sample_rows, start=2):
        for col_idx, val in enumerate(r, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = border
            if col_idx in (1, 3, 4):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 5:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = "#,##0.00"

    col_widths = [22, 45, 12, 26, 24]
    for idx, width in enumerate(col_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws.column_dimensions[col_letter].width = width

    ws.views.sheetView[0].showGridLines = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_incorrido_template() -> bytes:
    """Gera modelo de planilha Excel para importação de Incorrido / Análise do Realizado."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Incorrido_Realizado"

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    headers = [
        "Código Estruturado",
        "Data Documento (AAAA-MM-DD)",
        "Número AP",
        "Descrição do Documento / Insumo",
        "Valor Apropriação (R$)"
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    sample_rows = [
        ["01.01.001", "2026-01-15", 10245, "NF 8492 Concremax - Lote 1", 45000.00],
        ["01.01.001", "2026-01-20", 10250, "Medição 01 - Empreiteira Alpha MO", 25000.00],
        ["01.01.002", "2026-01-22", 10280, "NF 1290 Gerdau Aço CA-50", 60000.00],
    ]

    for row_idx, r in enumerate(sample_rows, start=2):
        for col_idx, val in enumerate(r, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = border
            if col_idx in (1, 2, 3):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 5:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = "#,##0.00"

    col_widths = [22, 28, 16, 45, 24]
    for idx, width in enumerate(col_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws.column_dimensions[col_letter].width = width

    ws.views.sheetView[0].showGridLines = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_conciliacao_template() -> bytes:
    """Gera modelo de planilha Excel para importação de Conciliação Financeira (Mega)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Conciliacao_Financeira"

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    headers = [
        "Número AP",
        "Parcela",
        "Data Vencimento",
        "Valor Rateado (R$)",
        "Pagamentos (R$)",
        "Saldo a Pagar (R$)",
        "Código Estruturado"
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    sample_rows = [
        [10245, "1", "2026-02-12", 45000.00, 45000.00, 0.00, "01.01.001 - Concreto"],
        [10250, "1", "2026-02-05", 25000.00, 25000.00, 0.00, "01.01.001 - Concreto"],
        [10280, "1", "2026-02-20", 30000.00, 30000.00, 0.00, "01.01.002 - Aço"],
        [10280, "2", "2026-03-20", 30000.00, 0.00, 30000.00, "01.01.002 - Aço"],
    ]

    for row_idx, r in enumerate(sample_rows, start=2):
        for col_idx, val in enumerate(r, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = border
            if col_idx in (1, 2, 3):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx in (4, 5, 6):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = "#,##0.00"

    col_widths = [16, 12, 18, 20, 20, 20, 32]
    for idx, width in enumerate(col_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws.column_dimensions[col_letter].width = width

    ws.views.sheetView[0].showGridLines = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()





