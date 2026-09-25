import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

def generate_standard_replan_template() -> io.BytesIO:
    """
    Generates a beautifully formatted, standardized Excel template (.xlsx)
    for importing projects into the Replanejamento Físico-Financeiro system.
    Contains:
      1. Aba 'Orçamento & Distribuição' (Levels 1-5 budget + Level 6 schedule links)
      2. Aba 'Cronograma' (Task ID, WBS, Name, Duration, Start, Finish, Predecessors, Lot)
      3. Aba 'Instruções' (Complete guide on columns and formatting)
    """
    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active
    wb.remove(default_sheet)

    # Styles
    navy_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    blue_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    l6_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    bold_font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
    regular_font = Font(name="Segoe UI", size=10, color="1E293B")
    l6_font = Font(name="Segoe UI", size=9, color="334155", italic=True)
    l6_arrow_font = Font(name="Segoe UI", size=9, bold=True, color="2563EB")
    
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # =========================================================================
    # 1. ABA: ORÇAMENTO & DISTRIBUIÇÃO
    # =========================================================================
    ws_orc = wb.create_sheet(title="Orçamento & Distribuição")
    ws_orc.views.sheetView[0].showGridLines = True

    orc_headers = [
        "Nível", "Código", "Descrição da Etapa / Atividade", "Unidade",
        "Quantidade", "Preço Unitário (R$)", "Preço Total (R$)",
        "Medição Acumulada (%)", "Duração Manual (dias)", "Valor Alocado (R$)"
    ]
    ws_orc.append(orc_headers)
    for col_num in range(1, len(orc_headers) + 1):
        cell = ws_orc.cell(row=1, column=col_num)
        cell.fill = navy_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center" if col_num in [1, 2, 4] else ("right" if col_num >= 5 else "left"), vertical="center")
    ws_orc.row_dimensions[1].height = 26

    # Sample Data for Orçamento & Distribuição
    sample_orc_rows = [
        (1, "1", "EDIFÍCIO RESIDENCIAL HORIZONTE", None, None, None, 25000000.0, None, None, None),
        (2, "1.1", "INFRAESTRUTURA E FUNDAÇÕES", None, None, None, 2800000.0, None, None, None),
        (3, "1.1.1", "FUNDAÇÕES PROFUNDAS", None, None, None, 1450000.0, None, None, None),
        (4, "1.1.1.1", "ESTACAS ESCAVADAS", None, None, None, 850000.0, None, None, None),
        (5, "01.01.01.01.001", "Perfuração de estaca escavada Ø 50cm em solo", "m", 1200.0, 320.0, 384000.0, 1.0, None, None),
        (6, None, "ESTACAS ESCAVADAS - Torre 1", None, None, None, None, None, 15, None),
        (6, None, "ESTACAS ESCAVADAS - Torre 2", None, None, None, None, None, 12, None),
        (5, "01.01.01.01.002", "Concreto usinado fck 30 MPa para estacas", "m³", 235.0, 480.0, 112800.0, 1.0, None, None),
        (6, None, "CONCRETAGEM ESTACAS - Torre 1", None, None, None, None, None, 15, None),
        (6, None, "CONCRETAGEM ESTACAS - Torre 2", None, None, None, None, None, 12, None),
        (3, "1.1.2", "BLOCOS DE COROAMENTO E VIGAS BALDRAME", None, None, None, 1350000.0, None, None, None),
        (4, "1.1.2.1", "BLOCOS DE COROAMENTO", None, None, None, 750000.0, None, None, None),
        (5, "01.01.02.01.001", "Armação de aço CA-50 em blocos de fundação", "kg", 25000.0, 12.5, 312500.0, 0.85, None, None),
        (6, None, "ARMAÇÃO BLOCOS - Bloco 1", None, None, None, None, None, 20, None),
        (6, None, "ARMAÇÃO BLOCOS - Bloco 2", None, None, None, None, None, 18, None),
        (2, "1.2", "ESTRUTURA DE CONCRETO ARMADO", None, None, None, 8500000.0, None, None, None),
        (3, "1.2.1", "ESTRUTURA TORRE 1", None, None, None, 4500000.0, None, None, None),
        (4, "1.2.1.1", "ESTRUTURA TÉRREO", None, None, None, 450000.0, None, None, None),
        (5, "01.02.01.01.001", "Estrutura de concreto armado Térreo Torre 1", "m³", 180.0, 1850.0, 333000.0, 0.50, None, None),
        (6, None, "ESTRUTURA - T1 - Térreo", None, None, None, None, None, 25, None),
        (4, "1.2.1.2", "ESTRUTURA 1º AO 10º TIPO", None, None, None, 3500000.0, None, None, None),
        (5, "01.02.01.02.001", "Estrutura de concreto armado 1º Pavimento Tipo", "m³", 120.0, 1850.0, 222000.0, 0.0, None, None),
        (6, None, "ESTRUTURA - T1 - 1º Pavimento", None, None, None, None, None, 18, None),
        (5, "01.02.01.02.002", "Estrutura de concreto armado 2º Pavimento Tipo", "m³", 120.0, 1850.0, 222000.0, 0.0, None, None),
        (6, None, "ESTRUTURA - T1 - 2º Pavimento", None, None, None, None, None, 18, None),
        (2, "1.3", "FACHADAS E REVESTIMENTOS EXTERNOS", None, None, None, 3800000.0, None, None, None),
        (3, "1.3.1", "EMBOÇO E PASTILHA FACHADA", None, None, None, 2200000.0, None, None, None),
        (4, "1.3.1.1", "EMBOÇO EXTERNO", None, None, None, 1200000.0, None, None, None),
        (5, "01.03.01.01.001", "Emboço paulista externo traço 1:2:8", "m²", 4800.0, 85.0, 408000.0, 0.0, None, None),
        (6, None, "BALANCIM/ANDAIME - T1 - Fachada A", None, None, None, None, None, 15, None),
        (6, None, "EMBOÇO EXT. - T1 - Fachada A", None, None, None, None, None, 25, None),
        (6, None, "BALANCIM/ANDAIME - T1 - Fachada B", None, None, None, None, None, 15, None),
        (6, None, "EMBOÇO EXT. - T1 - Fachada B", None, None, None, None, None, 25, None)
    ]

    for r_idx, row_vals in enumerate(sample_orc_rows, start=2):
        lvl = row_vals[0]
        desc = row_vals[2]
        
        # Prepend indent visual
        indent = "    " * (lvl - 1) if lvl < 6 else "        ↳ "
        formatted_desc = f"{indent}{desc}"
        
        row_data = [
            lvl,
            row_vals[1] or "",
            formatted_desc,
            row_vals[3] or "",
            row_vals[4],
            row_vals[5],
            row_vals[6],
            row_vals[7],
            row_vals[8],
            row_vals[9]
        ]
        ws_orc.append(row_data)
        
        row_cell = ws_orc[r_idx]
        is_l6 = (lvl == 6)
        
        for c_idx, cell in enumerate(row_cell, start=1):
            cell.border = thin_border
            if is_l6:
                cell.fill = l6_fill
                cell.font = l6_font
                if c_idx == 3:
                    cell.font = l6_arrow_font
            elif lvl <= 2:
                cell.font = bold_font
            else:
                cell.font = regular_font

            # Alignments & Formats
            if c_idx == 1:
                cell.alignment = Alignment(horizontal="center")
            elif c_idx == 2:
                cell.alignment = Alignment(horizontal="center")
            elif c_idx in [5, 6, 7]:
                cell.alignment = Alignment(horizontal="right")
                if c_idx in [6, 7] and cell.value is not None:
                    cell.number_format = '"R$ "#,##0.00'
                elif c_idx == 5 and cell.value is not None:
                    cell.number_format = '#,##0.00'
            elif c_idx == 8 and cell.value is not None:
                cell.alignment = Alignment(horizontal="right")
                cell.number_format = '0.00%'
            elif c_idx in [9, 10]:
                cell.alignment = Alignment(horizontal="right")
                if c_idx == 10 and cell.value is not None:
                    cell.number_format = '"R$ "#,##0.00'

    # Auto-adjust column widths
    for col in ws_orc.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws_orc.column_dimensions[col_letter].width = max(12, min(max_len + 3, 50))
    ws_orc.column_dimensions['C'].width = 55

    # =========================================================================
    # 2. ABA: CRONOGRAMA
    # =========================================================================
    ws_crono = wb.create_sheet(title="Cronograma")
    ws_crono.views.sheetView[0].showGridLines = True

    crono_headers = [
        "ID", "EDT", "Nome da Atividade", "Duração (dias)",
        "Data Início", "Data Término", "Predecessoras", "Lote Mãe", "Lote / Pavimento"
    ]
    ws_crono.append(crono_headers)
    for col_num in range(1, len(crono_headers) + 1):
        cell = ws_crono.cell(row=1, column=col_num)
        cell.fill = blue_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center" if col_num in [1, 2, 4, 5, 6] else "left", vertical="center")
    ws_crono.row_dimensions[1].height = 26

    sample_crono_rows = [
        ("1", "1", "ESTACAS ESCAVADAS - Torre 1", 15, "2026-10-01", "2026-10-21", "", "Torre 1", "Fundações"),
        ("2", "2", "CONCRETAGEM ESTACAS - Torre 1", 15, "2026-10-05", "2026-10-23", "1SS+2d", "Torre 1", "Fundações"),
        ("3", "3", "ESTACAS ESCAVADAS - Torre 2", 12, "2026-10-22", "2026-11-06", "1FS", "Torre 2", "Fundações"),
        ("4", "4", "CONCRETAGEM ESTACAS - Torre 2", 12, "2026-10-26", "2026-11-10", "3SS+2d", "Torre 2", "Fundações"),
        ("5", "5", "ARMAÇÃO BLOCOS - Bloco 1", 20, "2026-10-26", "2026-11-20", "2FS", "Torre 1", "Blocos"),
        ("6", "6", "ARMAÇÃO BLOCOS - Bloco 2", 18, "2026-11-11", "2026-12-04", "4FS", "Torre 2", "Blocos"),
        ("7", "7", "ESTRUTURA - T1 - Térreo", 25, "2026-11-23", "2026-12-25", "5FS", "Torre 1", "Térreo"),
        ("8", "8", "ESTRUTURA - T1 - 1º Pavimento", 18, "2026-12-28", "2027-01-20", "7FS", "Torre 1", "1º Pavimento"),
        ("9", "9", "ESTRUTURA - T1 - 2º Pavimento", 18, "2027-01-21", "2027-02-15", "8FS", "Torre 1", "2º Pavimento"),
        ("10", "10", "BALANCIM/ANDAIME - T1 - Fachada A", 15, "2027-01-15", "2027-02-04", "8SS", "Torre 1", "Fachada A"),
        ("11", "11", "EMBOÇO EXT. - T1 - Fachada A", 25, "2027-02-05", "2027-03-11", "10FS", "Torre 1", "Fachada A"),
        ("12", "12", "BALANCIM/ANDAIME - T1 - Fachada B", 15, "2027-02-08", "2027-02-26", "10FS", "Torre 1", "Fachada B"),
        ("13", "13", "EMBOÇO EXT. - T1 - Fachada B", 25, "2027-03-01", "2027-04-02", "12FS; 11SS+5d", "Torre 1", "Fachada B")
    ]

    for r_idx, row_vals in enumerate(sample_crono_rows, start=2):
        ws_crono.append(list(row_vals))
        row_cell = ws_crono[r_idx]
        for c_idx, cell in enumerate(row_cell, start=1):
            cell.border = thin_border
            cell.font = regular_font
            if c_idx in [1, 2, 4]:
                cell.alignment = Alignment(horizontal="center")
            elif c_idx in [5, 6]:
                cell.alignment = Alignment(horizontal="center")
            elif c_idx == 7:
                cell.alignment = Alignment(horizontal="center")
                cell.font = Font(name="Consolas", size=9, bold=True, color="1E3A8A")

    for col in ws_crono.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws_crono.column_dimensions[col_letter].width = max(12, min(max_len + 3, 40))
    ws_crono.column_dimensions['C'].width = 42

    # =========================================================================
    # 3. ABA: INSTRUÇÕES
    # =========================================================================
    ws_inst = wb.create_sheet(title="Instruções e Padrão")
    ws_inst.views.sheetView[0].showGridLines = True
    
    inst_title = ws_inst.cell(row=1, column=1, value="MANUAL DO MODELO PADRÃO DE REPLANEJAMENTO")
    inst_title.font = Font(name="Segoe UI", size=14, bold=True, color="0F172A")
    
    instructions = [
        ("", ""),
        ("1. OBJETIVO DO MODELO", "Substituir planilhas gigantes de 60 MB por um arquivo leve (< 100 KB) que carrega instantaneamente e contém apenas o que a engenharia precisa: o Orçamento com vínculos e o Cronograma."),
        ("", ""),
        ("2. ABA 'ORÇAMENTO & DISTRIBUIÇÃO'", "Define a EAP (Níveis 1 a 5) e os vínculos das atividades do cronograma (Nível 6):"),
        ("   • Níveis 1 a 4", "Linhas totalizadoras de grupos e subgrupos da obra. Preencha Nível, Código, Descrição e Preço Total."),
        ("   • Nível 5", "Item analítico do orçamento que tem preço, quantidade e saldo a realizar."),
        ("   • Nível 6 (Vínculos)", "Linhas inseridas LOGO ABAIXO do Nível 5 correspondente. Na coluna 'Descrição', coloque o NOME EXATO da atividade do Cronograma que executa esse item!"),
        ("   • Medição Acumulada (%)", "Percentual já executado na data de corte da obra (ex: 100% para concluído, 50% para metade, 0% ou vazio para ainda não iniciado)."),
        ("   • Duração Manual e Valor Alocado", "Opcionais. Se deixar em branco, o sistema busca a duração do cronograma e rateia o valor proporcionalmente."),
        ("", ""),
        ("3. ABA 'CRONOGRAMA'", "Define a rede de atividades, prazos e precedências:"),
        ("   • ID", "Número único de identificação da tarefa (1, 2, 3...)."),
        ("   • Nome da Atividade", "Deve coincidir com o nome usado nas linhas de Nível 6 do Orçamento para fazer o vínculo automático."),
        ("   • Duração (dias)", "Duração em dias úteis (Segunda a Sexta)."),
        ("   • Predecessoras (Vínculos CPM)", "Exemplos de preenchimento aceitos pelo motor CPM:"),
        ("     - '4FS'", "Término-Início padrão (começa no dia útil seguinte ao término da tarefa 4)."),
        ("     - '4FS+2d'", "Término-Início com 2 dias de folga/lag."),
        ("     - '2SS+3d'", "Início-Início com 3 dias de defasagem."),
        ("     - '5FF'", "Término-Término (termina junto com a tarefa 5)."),
        ("     - '12FS; 11SS+5d'", "Múltiplas predecessoras separadas por ponto e vírgula ou vírgula."),
        ("", ""),
        ("4. CÁLCULO E SIMULAÇÃO NO APLICATIVO", "Físico-Financeiro Base, Curva S, Saldo Nível 6, Físico-Financeiro Replanejado e Distribuição Mensal são gerados 100% automaticamente pelo sistema em milissegundos!")
    ]

    for r_i, (topic, text) in enumerate(instructions, start=2):
        c1 = ws_inst.cell(row=r_i, column=1, value=topic)
        c2 = ws_inst.cell(row=r_i, column=2, value=text)
        c1.font = Font(name="Segoe UI", size=10, bold=bool(topic and not topic.startswith("   •")), color="0F172A")
        c2.font = Font(name="Segoe UI", size=10, color="334155")
        
    ws_inst.column_dimensions['A'].width = 30
    ws_inst.column_dimensions['B'].width = 90

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
