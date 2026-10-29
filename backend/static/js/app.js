    const brlFormatter = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    function replanApp() {
      return {
        // App state
        projects: [],
        selectedProjectId: "platea",
        activeProject: null,
        activeTab: "dashboard",
        cronoSubTab: "table",
        cycleStartDay: 21,
        get computedCycleEndDay() {
          const start = parseInt(this.cycleStartDay) || 1;
          if (start <= 1) return 0;
          return start - 1;
        },
        get computedCycleEndDayLabel() {
          const start = parseInt(this.cycleStartDay) || 1;
          if (start <= 1) return "Fim Mês";
          const end = start - 1;
          return end < 10 ? '0' + end : '' + end;
        },
        get cycleEndDay() {
          return this.computedCycleEndDay;
        },
        set cycleEndDay(val) {
          // controlled automatically (1 month - 1 day)
        },
        cutoffMedNum: 11,
        selectedVersionId: null,

        // Data from simulate
        replanResult: null,
        isLoading: false,
        isExporting: false,
        showExportMenu: false,
        isUploading: false,

        // Modals
        showProjectModal: false,
        showUploadModal: false,
        uploadProjectName: "",
        isUploadingProject: false,
        uploadError: null,
        showImportModal: false,
        versions: {},            // {domain: {active, versions: [{id, name, has_edits}], edits}}
        showVersionImportModal: false,
        importDomain: null,
        versionImportName: "",
        versionImportFile: null,
        savedEditsJson: {},      // last JSON persisted per domain (avoids redundant saves)
        medicaoSaveTimer: null,
        importVersionName: "",
        selectedScheduleFile: null,

        // Link Modal (Nível 6)
        showLinkModal: false,
        linkTargetL5Code: "",
        linkTargetL5Desc: "",
        linkModalIndex: -1,
        linkCurrentTaskName: "",
        linkSearch: "",
        linkTypeFilter: "all",
        selectedLinkTaskId: "",
        selectedGroupLeaves: [],
        customLinksByL5: {},
        hasCustomLinksFlag: false,

        // Filters
        searchBudget: "",
        searchDist: "",
        searchCrono: "",
        searchMed: "",
        searchReplan: "",

        levelFilterFF: 3,       // 2, 3, 4, 0 (all)
        levelFilterMed: 0,      // 0 (all), 2, 3, 4
        showPrevistoMedicao: false, // Checkbox na Medição: exibe coluna P (Previsto) ao lado de R (Realizado)
        cachedMedCycleCols: [],
        medPrevistoLookup: {},
        medRowMap: {},
        medL6MonthlyMap: {},
        levelFilterFFRep: 3,    // 2, 3, 4, 0
        levelFilterReplan: 5,   // 5 (default: até N5 com accordion N6), 0 (todos N2-N6), 2, 3, 4
        expandedReplanL5: {},   // { [code]: boolean }
        levelFilterComp: 3,     // 2, 3, 4, 0
        levelFilterFin: 3,      // 2, 3, 4, 0

        ffViewMode: "pct",      // 'pct' | 'val'
        ffRepViewMode: "pct",   // 'pct' (% Obra) | 'pct_service' (% Serviço) | 'val' (R$)
        replanSaldoInPct: false, // Checkbox: false (R$) | true (%)
        distViewMode: "pct",    // 'pct' (% Obra) | 'pct_service' (% Serviço) | 'val' (R$)
        compViewMode: "val",    // 'val' | 'mat' | 'mo' | 'pct'
        finViewMode: "val",     // 'val' | 'mat' | 'mo' | 'pct'

        showConfigCurvasModal: false,
        editableCurvasConfigs: [],
        isSavingCurvasConfig: false,
        searchCurvasConfig: "",
        curvasLevelFilter: 0,
        collapsedCurvasNodes: {},
        comparisonChartInstance: null,
        tripleChartInstance: null,
        realizadoProjecaoChartInstance: null,

        // Curvas Avançadas (Custo Projetado, Incorrido, Conciliação, Realizado + Projeção)
        showCurvasImportModal: false,
        curvasImportTab: 'custo_projetado',
        showCurvasVinculosModal: false,
        curvasSubView: 'sintetica',
        curvasCorte: new Date().toISOString().slice(0, 7),
        curvasDados: null,
        curvasRealizadoData: null,
        isLoadingCurvasDados: false,
        isLoadingRealizado: false,
        novoVinculoOrigem: '',
        novoVinculoDestino: '',
        searchAnalitica: '',
        filtroTipoAnalitica: 'TODOS',
        configCurvasTab: 'etapas',
        curvasParamsObra: {
          dias_antecedencia_padrao: 10,
          prazo_pagamento_padrao_dias: 28,
          dia_corte_medicao_mo: 20,
          dia_pagamento_mo: 5,
          retencao_mo_ativa: false,
          retencao_mo_percentual: 5.0,
          data_fim_obra: ''
        },

        // Modal Redistribuição de Saldo (Nível 5)
        showReplanWeightModal: false,
        modalReplanRow: null,
        modalReplanTasks: [],
        modalReplanCriteria: 'percentual', // 'tempo' | 'quantidade' | 'area' | 'percentual'
        customReplanWeights: {},
        isSavingReplanWeights: false,

        // Pagination
        distPage: 1,
        distPageSize: 100,   // rolagem infinita: carrega +100 linhas ao chegar no fim
        cronoPage: 1,
        cronoPageSize: 100,
        replanPage: 1,
        replanPageSize: 150,
        medPage: 1,
        medPageSize: 100,

        // Curve Visibility
        curveVisibility: {
          baseline: true,
          realized: true,
          replan: true
        },
        chartInstance: null,

        // Medição State & Accordion
        expandedL5: {},
        customMonthlyL5: {},    // {code: {med_num: pct}}
        customMonthlyL6: {},    // {code: {task_name: {med_num: pct}}}

        // Task Drawer State
        showTaskDrawer: false,
        isSavingDrawer: false,
        drawerTask: null,
        drawerPredecessors: [],
        selectedNewPredId: "",

        // Gantt Interactive State
        ganttZoom: 3.5,
        dragState: null,
        wasDragging: false,
        customScheduleOverrides: {},
        lobLoteMaeFilter: "all",
        lobLotFilter: "all",
        lobSortOrder: "bottom-to-top",

        // Month Filter State & Level Colors
        selectedFilterMonths: [],

        getLevelRowClass(level) {
          const l = parseInt(level) || 0;
          if (l === 1) return 'row-level-1';
          if (l === 2) return 'row-level-2';
          if (l === 3) return 'row-level-3';
          if (l === 4) return 'row-level-4';
          if (l === 5) return 'row-level-5';
          if (l === 6) return 'row-level-6';
          return 'bg-white text-slate-700';
        },

        getLevelStickyClass(level) {
          const l = parseInt(level) || 0;
          if (l === 1) return 'sticky-level-1';
          if (l === 2) return 'sticky-level-2';
          if (l === 3) return 'sticky-level-3';
          if (l === 4) return 'sticky-level-4';
          if (l === 5) return 'sticky-level-5';
          if (l === 6) return 'sticky-level-6';
          return 'bg-white text-slate-700';
        },

        toggleMonthFilter(cycleNum) {
          cycleNum = parseInt(cycleNum);
          const idx = this.selectedFilterMonths.indexOf(cycleNum);
          if (idx !== -1) {
            this.selectedFilterMonths.splice(idx, 1);
          } else {
            this.selectedFilterMonths.push(cycleNum);
          }
          this.distPage = 1;
          this.replanPage = 1;
          this.medPage = 1;
          this.$nextTick(() => lucide.createIcons());
        },

        clearMonthFilter() {
          this.selectedFilterMonths = [];
          this.distPage = 1;
          this.replanPage = 1;
          this.medPage = 1;
          this.$nextTick(() => lucide.createIcons());
        },

        isMonthFilterActive(cycleNum) {
          return this.selectedFilterMonths.includes(parseInt(cycleNum));
        },

        getMonthFilterLabel() {
          if (!this.selectedFilterMonths.length) return '';
          const cycles = this.replanResult?.cycles || [];
          const names = this.selectedFilterMonths
            .slice()
            .sort((a, b) => a - b)
            .map(num => {
              const c = cycles.find(cy => cy.num === num);
              return c ? (c.period_label || c.name) : ('M' + num);
            });
          return names.join(', ');
        },

        hasDistCycleVal(row, cycleNum) {
          if (!row) return false;
          const cStr = String(cycleNum);
          const val = (row.cycle_vals && row.cycle_vals[cStr]) || 0;
          const pct = (row.cycle_pcts && row.cycle_pcts[cStr]) || 0;
          const pctObra = (row.cycle_pcts_obra && row.cycle_pcts_obra[cStr]) || 0;
          return (val > 0.0001 || pct > 0.0001 || pctObra > 0.0001);
        },

        hasReplanCycleVal(row, cycleNum) {
          if (!row) return false;
          const cStr = String(cycleNum);
          const val = (row.cycle_vals && row.cycle_vals[cStr]) || 0;
          return val > 0.0001;
        },

        async init() {
          const savedReplanSaldoPct = localStorage.getItem('replanSaldoInPct');
          if (savedReplanSaldoPct !== null) {
            this.replanSaldoInPct = savedReplanSaldoPct === 'true';
          }
          this.$watch('replanSaldoInPct', (val) => {
            localStorage.setItem('replanSaldoInPct', val);
          });
          await this.loadProjects();
          await this.loadVersions();
          await this.runSimulation();
          this.$nextTick(() => {
            lucide.createIcons();
          });
          this.$watch('distPage', () => { this.$nextTick(() => lucide.createIcons()); });
          this.$watch('cronoPage', () => { this.$nextTick(() => lucide.createIcons()); });
          this.$watch('searchDist', () => { this.distPage = 1; this.$nextTick(() => lucide.createIcons()); });
          this.$watch('searchCrono', () => { this.cronoPage = 1; this.$nextTick(() => lucide.createIcons()); });
          this.$watch('distViewMode', () => { this.$nextTick(() => lucide.createIcons()); });
          this.$watch('showPrevistoMedicao', () => {
            this.updateMedCycleCols();
            this.$nextTick(() => lucide.createIcons());
          });
        },

        async loadProjects() {
          try {
            const resp = await fetch("/api/projects");
            if (resp.ok) {
              this.projects = await resp.json();
              if (this.projects.length && !this.selectedProjectId) {
                this.selectedProjectId = this.projects[0].id;
              }
              this.activeProject = this.projects.find(p => p.id === this.selectedProjectId);
            }
          } catch (e) {
            console.error("Erro ao carregar projetos:", e);
          }
        },

        async onProjectSelectChange() {
          this.activeProject = this.projects.find(p => p.id === this.selectedProjectId);
          await this.loadVersions();
          this.runSimulation();
        },

        // --- Versões por tela (edições salvas sempre na versão ativa) ---
        async loadVersions() {
          if (!this.selectedProjectId) return;
          try {
            const resp = await fetch(`/api/versions/${this.selectedProjectId}`);
            if (!resp.ok) return;
            this.versions = await resp.json();
          } catch (e) {
            console.error("Erro ao carregar versões:", e);
            return;
          }
          const med = this.versions.medicao?.edits || {};
          const crono = this.versions.cronograma?.edits || {};
          const dist = this.versions.distribuicao?.edits || {};
          const replan = this.versions.replanejado?.edits || {};
          this.selectedVersionId = this.versions.cronograma?.active || null;
          this.customMonthlyL5 = JSON.parse(JSON.stringify(med.monthly_l5 || {}));
          this.customMonthlyL6 = JSON.parse(JSON.stringify(med.monthly_l6 || {}));
          this.customScheduleOverrides = JSON.parse(JSON.stringify(crono.schedule_overrides || {}));
          this.customLinksByL5 = JSON.parse(JSON.stringify(dist.links_by_l5 || {}));
          this.customReplanWeights = JSON.parse(JSON.stringify(replan.replan_weights || {}));
          this.hasCustomLinksFlag = !!dist.links_by_l5;
          this.savedEditsJson = {
            medicao: JSON.stringify(this.medicaoEdits()),
            cronograma: JSON.stringify(this.cronogramaEdits()),
            replanejado: JSON.stringify(this.replanejadoEdits())
          };
        },

        medicaoEdits() {
          const e = {};
          if (Object.keys(this.customMonthlyL5 || {}).length) e.monthly_l5 = this.customMonthlyL5;
          if (Object.keys(this.customMonthlyL6 || {}).length) e.monthly_l6 = this.customMonthlyL6;
          return e;
        },

        cronogramaEdits() {
          return Object.keys(this.customScheduleOverrides || {}).length ? { schedule_overrides: this.customScheduleOverrides } : {};
        },

        replanejadoEdits() {
          return Object.keys(this.customReplanWeights || {}).length ? { replan_weights: this.customReplanWeights } : {};
        },

        async persistEdits() {
          // Grava na versão ativa só o que mudou desde o último salvamento
          if (!this.selectedProjectId) return;
          const pending = { 
            medicao: this.medicaoEdits(), 
            cronograma: this.cronogramaEdits(),
            replanejado: this.replanejadoEdits()
          };
          for (const [domain, edits] of Object.entries(pending)) {
            const json = JSON.stringify(edits);
            if (json === this.savedEditsJson[domain]) continue;
            try {
              await fetch(`/api/versions/${this.selectedProjectId}/${domain}/edits`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ edits })
              });
              this.savedEditsJson[domain] = json;
            } catch (e) {
              console.error(`Erro ao salvar edições (${domain}):`, e);
            }
          }
        },

        queueSaveMedicao() {
          clearTimeout(this.medicaoSaveTimer);
          this.medicaoSaveTimer = setTimeout(() => this.persistEdits(), 800);
        },

        async activateVersion(domain, versionId) {
          await this.persistEdits();
          try {
            const resp = await fetch(`/api/versions/${this.selectedProjectId}/${domain}/activate`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ version_id: versionId })
            });
            if (!resp.ok) {
              const err = await resp.json();
              alert(this.formatErrorDetail(err, "Erro ao ativar versão."));
            }
          } catch (e) {
            console.error(e);
          }
          await this.loadVersions();
          await this.runSimulation();
        },

        async restoreVersion(domain) {
          await fetch(`/api/versions/${this.selectedProjectId}/${domain}/edits`, { method: "DELETE" });
          await this.loadVersions();
        },

        domainLabel(domain) {
          return { orcamento: "Orçamento", cronograma: "Cronograma", distribuicao: "Distribuição", medicao: "Medição" }[domain] || "";
        },

        openVersionImport(domain) {
          this.importDomain = domain;
          this.versionImportName = "";
          this.versionImportFile = null;
          this.showVersionImportModal = true;
          this.$nextTick(() => lucide.createIcons());
        },

        async submitVersionImport() {
          if (!this.versionImportFile) return;
          this.isUploading = true;
          try {
            await this.persistEdits();
            const formData = new FormData();
            formData.append("version_name", this.versionImportName || this.versionImportFile.name);
            formData.append("file", this.versionImportFile);
            const resp = await fetch(`/api/versions/${this.selectedProjectId}/${this.importDomain}/import`, {
              method: "POST",
              body: formData
            });
            if (!resp.ok) {
              const err = await resp.json();
              alert(this.formatErrorDetail(err, "Erro ao importar versão."));
              return;
            }
            this.showVersionImportModal = false;
            await this.loadVersions();
            await this.runSimulation();
          } catch (e) {
            console.error(e);
            alert("Erro ao enviar arquivo.");
          } finally {
            this.isUploading = false;
          }
        },

        // Rolagem infinita com throttling e escopo correto no container de rolagem
        observeMore(el, pageKey, totalFn) {
          const scrollContainer = el.closest('.overflow-x-auto') || el.closest('.overflow-y-auto') || el.parentElement;
          let isPaging = false;
          const io = new IntersectionObserver((entries) => {
            if (isPaging) return;
            const pageSize = this[pageKey + 'Size'] || 100;
            if (entries.some(e => e.isIntersecting) && this[pageKey] * pageSize < totalFn()) {
              isPaging = true;
              this[pageKey]++;
              setTimeout(() => {
                isPaging = false;
                if (window.lucide && scrollContainer) {
                  try { lucide.createIcons({ root: scrollContainer }); } catch (_) {}
                }
              }, 150);
            }
          }, { root: scrollContainer, rootMargin: "300px" });
          io.observe(el);
        },

        downloadSplitTemplate(domain) {
          window.location.href = `/api/projects/template-split/${domain}`;
        },

        selectProject(pid) {
          this.selectedProjectId = pid;
          this.showProjectModal = false;
          this.onProjectSelectChange();
        },

        onCycleStartChange() {
          let start = parseInt(this.cycleStartDay);
          if (isNaN(start) || start < 1) start = 1;
          if (start > 31) start = 31;
          this.cycleStartDay = start;
          this.runSimulation();
        },

        setPreset(start) {
          this.cycleStartDay = start;
          this.runSimulation();
        },

        switchTab(tab) {
          this.activeTab = tab;
          if (tab === 'medicao') {
            this.buildMedicaoLookups();
            this.updateMedCycleCols();
          }
          this.$nextTick(() => {
            if (tab === 'dashboard') {
              this.renderCurvaS();
            } else if (tab === 'financeiro') {
              this.renderComparisonChart();
            }
            if (window.lucide) {
              try { lucide.createIcons(); } catch (_) {}
            }
          });
        },

        prepareMedicaoRows(tab_medicao) {
          if (!tab_medicao || !Array.isArray(tab_medicao)) return;
          for (let i = 0; i < tab_medicao.length; i++) {
            const r = tab_medicao[i];
            r.isL6 = false;
            r._rowKey = r.code;
            if (r.tasks_l6 && r.tasks_l6.length > 0) {
              for (let j = 0; j < r.tasks_l6.length; j++) {
                const t = r.tasks_l6[j];
                t.isL6 = true;
                t._rowKey = r.code + '_' + t.task_name;
                t.parent_code = r.code;
                t.monthly_measurements = t.monthly_measurements || {};
              }
            }
          }
        },

        indexReplanData(tab_replanejado) {
          this._replanChildrenByParent = {};
          if (!tab_replanejado || !Array.isArray(tab_replanejado)) return;
          for (let i = 0; i < tab_replanejado.length; i++) {
            const r = tab_replanejado[i];
            if (r.level === 6 && r.parent_code) {
              if (!this._replanChildrenByParent[r.parent_code]) {
                this._replanChildrenByParent[r.parent_code] = [];
              }
              this._replanChildrenByParent[r.parent_code].push(r);
            }
          }
          for (let i = 0; i < tab_replanejado.length; i++) {
            const r = tab_replanejado[i];
            if (r.level === 5) {
              r.l6_count = (this._replanChildrenByParent[r.code] || []).length;
            }
          }
        },

        async runSimulation() {
          if (this.isLoading) return;
          this.isLoading = true;
          try {
            await this.persistEdits();
            const payload = {
              project_id: this.selectedProjectId,
              cycle_start_day: this.cycleStartDay,
              cycle_end_day: this.computedCycleEndDay,
              cutoff_med_num: this.cutoffMedNum,
              version_id: this.selectedVersionId,
              custom_monthly_medicao: this.customMonthlyL5,
              custom_monthly_medicao_l6: this.customMonthlyL6,
              custom_schedule_overrides: this.customScheduleOverrides,
              custom_links_by_l5: (this.customLinksByL5 && Object.keys(this.customLinksByL5).length > 0) ? this.customLinksByL5 : null,
              custom_weights: (this.customReplanWeights && Object.keys(this.customReplanWeights).length > 0) ? this.customReplanWeights : null
            };

            const resp = await fetch("/api/replan/simulate", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload)
            });

            if (!resp.ok) {
              const err = await resp.json();
              alert(this.formatErrorDetail(err, "Erro ao simular replanejamento."));
              return;
            }

            const rawData = await resp.json();
            this.prepareMedicaoRows(rawData.tab_medicao);
            this.indexReplanData(rawData.tab_replanejado);

            // Freeze large calculation tables to eliminate Alpine recursive reactivity proxying overhead
            const freezeKeys = ['tab_distribuicao', 'tab_ff_replanejado', 'tree_rows', 'tab_fisico_financeiro', 'tab_orcamento'];
            for (let i = 0; i < freezeKeys.length; i++) {
              const k = freezeKeys[i];
              if (rawData[k] && Array.isArray(rawData[k])) Object.freeze(rawData[k]);
            }

            this.replanResult = rawData;
            if (this.replanResult.cutoff_med_num) {
              this.cutoffMedNum = this.replanResult.cutoff_med_num;
            }
            if (!this.selectedVersionId && this.replanResult.tab_cronograma?.versions?.length) {
              this.selectedVersionId = this.replanResult.tab_cronograma.versions[0].id;
            }

            if (this.replanResult.links_by_l5 && (!this.customLinksByL5 || Object.keys(this.customLinksByL5).length === 0)) {
              this.customLinksByL5 = JSON.parse(JSON.stringify(this.replanResult.links_by_l5));
            }
            if (this.replanResult.has_custom_links !== undefined) {
              this.hasCustomLinksFlag = !!this.replanResult.has_custom_links;
            }

            // Reset initial pagination so the table starts lightweight and doesn't re-render thousands of rows
            this.replanPage = 1;
            this.medPage = 1;
            this.cronoPage = 1;
            this.distPage = 1;

            if (this.activeTab === 'medicao') {
              this.buildMedicaoLookups();
              this.updateMedCycleCols();
            }

            this.$nextTick(() => {
              if (this.activeTab === 'dashboard') {
                this.renderCurvaS();
              } else if (this.activeTab === 'financeiro') {
                this.renderComparisonChart();
              }
              if (window.lucide) {
                try { lucide.createIcons(); } catch (_) {}
              }
            });
          } catch (e) {
            console.error("Erro na simulação:", e);
          } finally {
            this.isLoading = false;
          }
        },


        renderCurvaS() {
          const canvas = document.getElementById("curvaSChart");
          if (!canvas) return;

          // Destroy any existing chart on this canvas to prevent zombie instances
          const existing = Chart.getChart(canvas);
          if (existing) {
            try { existing.destroy(); } catch (e) {}
          }
          if (this.chartInstance) {
            try { this.chartInstance.destroy(); } catch (e) {}
            this.chartInstance = null;
          }

          const sc = this.replanResult?.s_curve || this.replanResult?.curva_s_series;
          if (!sc) return;

          const labels = sc.labels || (this.replanResult?.cycles || []).map(c => c.period_label || c.name);
          const baselineData = sc.baseline_accum_pcts || sc.baseline_pcts || [];
          const realizedData = sc.realized_accum_pcts || sc.realized_pcts || [];
          const replanData = sc.replan_accum_pcts || [];

          // Pass the canvas element directly (Chart.js v4 acquires context from canvas)
          this.chartInstance = new Chart(canvas, {
            type: "line",
            data: {
              labels: labels,
              datasets: [
                {
                  label: "Linha de Base Prevista (%)",
                  data: baselineData,
                  borderColor: "#64748b",
                  borderDash: [5, 5],
                  borderWidth: 2,
                  pointRadius: 0,
                  fill: false,
                  tension: 0.1,
                  hidden: !this.curveVisibility.baseline
                },
                {
                  label: "Realizado Medido (%)",
                  data: realizedData,
                  borderColor: "#16a34a",
                  backgroundColor: "rgba(22, 163, 74, 0.1)",
                  borderWidth: 3,
                  pointRadius: 3,
                  pointBackgroundColor: "#16a34a",
                  fill: false,
                  tension: 0.1,
                  hidden: !this.curveVisibility.realized
                },
                {
                  label: "Curva Replanejada (%)",
                  data: replanData,
                  borderColor: "#2563eb",
                  backgroundColor: "rgba(37, 99, 235, 0.08)",
                  borderWidth: 3,
                  pointRadius: 0,
                  fill: true,
                  tension: 0.2,
                  hidden: !this.curveVisibility.replan
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              animation: false, // Instant render without animation lag or frame drop crashes
              interaction: { mode: "index", intersect: false },
              plugins: {
                legend: { position: "top", labels: { boxWidth: 12, font: { size: 10, weight: '600' } } },
                tooltip: {
                  callbacks: {
                    label: function(c) {
                      return c.dataset.label + ": " + (c.parsed.y !== null && c.parsed.y !== undefined ? c.parsed.y.toFixed(2) + "%" : "Não medido");
                    }
                  }
                }
              },
              scales: {
                y: {
                  min: 0,
                  max: 100,
                  ticks: { stepSize: 10, callback: v => v + "%", font: { size: 9 } },
                  title: { display: true, text: "Avanço Físico Acumulado (%)", font: { size: 10, weight: 'bold' } },
                  grid: { color: "#f1f5f9" }
                },
                x: {
                  ticks: { maxRotation: 45, minRotation: 45, font: { size: 9 } },
                  grid: { display: false }
                }
              }
            }
          });
        },

        updateChartVisibility() {
          const canvas = document.getElementById("curvaSChart");
          const chart = this.chartInstance || (canvas ? Chart.getChart(canvas) : null);
          if (!chart) return;
          chart.data.datasets[0].hidden = !this.curveVisibility.baseline;
          chart.data.datasets[1].hidden = !this.curveVisibility.realized;
          chart.data.datasets[2].hidden = !this.curveVisibility.replan;
          chart.update();
        },

        renderComparisonChart() {
          const canvas = document.getElementById("chartComparisonCurves");
          if (!canvas) return;

          const existing = Chart.getChart(canvas);
          if (existing) {
            try { existing.destroy(); } catch (e) {}
          }
          if (this.comparisonChartInstance) {
            try { this.comparisonChartInstance.destroy(); } catch (e) {}
            this.comparisonChartInstance = null;
          }

          const sc = this.replanResult?.s_curve;
          const sComp = this.replanResult?.s_curves_comparison;
          if (!sComp) return;

          const labels = sComp.labels || [];
          const replanData = sc?.replan_accum_pcts || [];
          const compData = sComp.comp_accum_pcts || [];
          const finData = sComp.fin_accum_pcts || [];

          this.comparisonChartInstance = new Chart(canvas, {
            type: "line",
            data: {
              labels: labels,
              datasets: [
                {
                  label: "Físico Produzido (%)",
                  data: replanData,
                  borderColor: "#6366f1",
                  backgroundColor: "rgba(99, 102, 241, 0.05)",
                  borderWidth: 2.5,
                  pointRadius: 2,
                  tension: 0.2,
                  fill: false
                },
                {
                  label: "Competência / NF (%)",
                  data: compData,
                  borderColor: "#3b82f6",
                  backgroundColor: "rgba(59, 130, 246, 0.05)",
                  borderWidth: 2.5,
                  pointRadius: 2,
                  tension: 0.2,
                  fill: false
                },
                {
                  label: "Financeiro / Caixa (%)",
                  data: finData,
                  borderColor: "#10b981",
                  backgroundColor: "rgba(16, 185, 129, 0.05)",
                  borderWidth: 2.5,
                  pointRadius: 2,
                  tension: 0.2,
                  fill: false
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              animation: false,
              interaction: { mode: "index", intersect: false },
              plugins: {
                legend: { position: "top", labels: { boxWidth: 12, font: { size: 10, weight: '600' } } },
                tooltip: {
                  callbacks: {
                    label: function(c) {
                      return c.dataset.label + ": " + (c.parsed.y !== null && c.parsed.y !== undefined ? c.parsed.y.toFixed(2) + "%" : "-");
                    }
                  }
                }
              },
              scales: {
                y: {
                  min: 0,
                  max: 105,
                  ticks: { stepSize: 20, callback: v => v + "%", font: { size: 9 } },
                  title: { display: true, text: "Acumulado (%)", font: { size: 10, weight: 'bold' } },
                  grid: { color: "#f1f5f9" }
                },
                x: {
                  ticks: { maxRotation: 45, minRotation: 45, font: { size: 9 } },
                  grid: { display: false }
                }
              }
            }
          });
        },


        // --- Medição Accordion & Interactive Month Inputs ---
        toggleExpandL5(code) {
          this.expandedL5[code] = !this.expandedL5[code];
        },

        get displayMedRows() {
          const raw = this.replanResult?.tab_medicao || [];
          let filtered = raw;

          // Level Filter
          if (this.levelFilterMed > 0) {
            filtered = filtered.filter(r => r.level <= this.levelFilterMed);
          }

          // Search
          if (this.searchMed && this.searchMed.trim()) {
            const q = this.searchMed.toLowerCase();
            filtered = filtered.filter(r => r.code.toLowerCase().includes(q) || r.description.toLowerCase().includes(q));
          }

          // Month Filter
          if (this.selectedFilterMonths.length > 0) {
            const months = this.selectedFilterMonths;
            const matchingCodes = new Set();
            for (const r of raw) {
              let hasVal = false;
              for (const m of months) {
                if (r.level === 5) {
                  if (this.getL5MonthPct(r, m) > 0.0001) hasVal = true;
                  if (r.tasks_l6) {
                    for (const t of r.tasks_l6) {
                      if (this.getL6MonthPct(r.code, t.task_name, m) > 0.0001) hasVal = true;
                    }
                  }
                } else {
                  if (this.getL5MonthPct(r, m) > 0.0001) hasVal = true;
                }
                if (hasVal) break;
              }
              if (hasVal) {
                matchingCodes.add(r.code);
                const parts = r.code.split('.');
                for (let i = 1; i < parts.length; i++) {
                  matchingCodes.add(parts.slice(0, i).join('.'));
                }
              }
            }
            filtered = filtered.filter(r => matchingCodes.has(r.code));
          }

          const out = [];
          const monthsFilterActive = this.selectedFilterMonths.length > 0;
          for (let i = 0; i < filtered.length; i++) {
            const row = filtered[i];
            if (row.level === 1) continue;
            out.push(row);
            if (row.level === 5 && (this.expandedL5[row.code] || monthsFilterActive) && row.tasks_l6 && row.tasks_l6.length > 0) {
              for (let j = 0; j < row.tasks_l6.length; j++) {
                const t = row.tasks_l6[j];
                if (monthsFilterActive) {
                  let tHasVal = false;
                  for (let k = 0; k < this.selectedFilterMonths.length; k++) {
                    if (this.getL6MonthPct(row.code, t.task_name, this.selectedFilterMonths[k]) > 0.0001) {
                      tHasVal = true;
                      break;
                    }
                  }
                  if (!tHasVal) continue;
                }
                out.push(t);
              }
            }
          }
          return out;
        },

        get totalMedPages() {
          return Math.ceil(this.displayMedRows.length / this.medPageSize) || 1;
        },

        get paginatedMedRows() {
          return this.displayMedRows.slice(0, this.medPage * this.medPageSize);
        },

        getEffectiveL5AccumPct(row) {
          if (row.isL6) {
            return row.measured_pct || 0.0;
          }
          if (this.customMonthlyL5[row.code] || this.customMonthlyL6[row.code]) {
            let sum = 0.0;
            for (let m = 1; m <= this.cutoffMedNum; m++) {
              sum += this.getL5MonthPct(row, m);
            }
            return Math.min(100.0, sum);
          }
          return row.accum_realizado_pct || 0.0;
        },

        getL5MonthPct(rowOrCode, medNum) {
          const code = (typeof rowOrCode === 'object') ? rowOrCode.code : rowOrCode;
          if (this.customMonthlyL5[code]?.[medNum] !== undefined) {
            return this.customMonthlyL5[code][medNum];
          }
          if (typeof rowOrCode === 'object' && rowOrCode.monthly_map) {
            return rowOrCode.monthly_map[String(medNum)] || 0.0;
          }
          const row = this.medRowMap?.[code];
          return row?.monthly_map?.[String(medNum)] || 0.0;
        },

        getL6MonthPct(rowOrParentCode, taskNameOrMedNum, medNumMaybe) {
          let parentCode, taskName, medNum;
          if (typeof rowOrParentCode === 'object') {
            parentCode = rowOrParentCode.parent_code;
            taskName = rowOrParentCode.task_name;
            medNum = taskNameOrMedNum;
          } else {
            parentCode = rowOrParentCode;
            taskName = taskNameOrMedNum;
            medNum = medNumMaybe;
          }
          if (this.customMonthlyL6[parentCode]?.[taskName]?.[medNum] !== undefined) {
            return this.customMonthlyL6[parentCode][taskName][medNum];
          }
          if (typeof rowOrParentCode === 'object' && rowOrParentCode.monthly_measurements) {
            return rowOrParentCode.monthly_measurements[String(medNum)] || 0.0;
          }
          const tKey = parentCode + '::' + taskName;
          return this.medL6MonthlyMap?.[tKey]?.[String(medNum)] || 0.0;
        },

        getRollupMonthPct(row, medNum) {
          if (row.monthly_map && row.monthly_map[String(medNum)] !== undefined) {
            const v = row.monthly_map[String(medNum)];
            return v > 0 ? this.formatPercent(v) : '-';
          }
          const col = row.monthly_measurements?.find(m => m.med_num === medNum);
          return col && col.realizado_pct > 0 ? this.formatPercent(col.realizado_pct) : '-';
        },

        onMonthInputL5(code, medNum, val) {
          const cleanVal = typeof val === 'string' ? val.replace(',', '.').trim() : val;
          const num = Math.min(100, Math.max(0, parseFloat(cleanVal) || 0.0));
          if (!this.customMonthlyL5[code]) {
            this.customMonthlyL5[code] = {};
          }
          this.customMonthlyL5[code][medNum] = num;
          this.queueSaveMedicao();
        },

        onMonthInputL6(parentCode, taskName, medNum, val) {
          const cleanVal = typeof val === 'string' ? val.replace(',', '.').trim() : val;
          const num = Math.min(100, Math.max(0, parseFloat(cleanVal) || 0.0));
          if (!this.customMonthlyL6[parentCode]) {
            this.customMonthlyL6[parentCode] = {};
          }
          if (!this.customMonthlyL6[parentCode][taskName]) {
            this.customMonthlyL6[parentCode][taskName] = {};
          }
          this.customMonthlyL6[parentCode][taskName][medNum] = num;

          // Recalculate parent Level 5 for this month by weighted sum
          const row = this.replanResult?.tab_medicao?.find(r => r.code === parentCode);
          if (row && row.tasks_l6) {
            let weightedSum = 0.0;
            for (const t of row.tasks_l6) {
              const taskVal = this.getL6MonthPct(parentCode, t.task_name, medNum);
              weightedSum += taskVal * (t.weight_pct / 100.0);
            }
            this.onMonthInputL5(parentCode, medNum, weightedSum);
          }
        },

        formatPercent(val, decimals = 2) {
          if (val === undefined || val === null || isNaN(val)) return "-";
          return Number(val).toLocaleString("pt-BR", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
          }) + "%";
        },

        formatInputPct(val) {
          if (val === undefined || val === null || isNaN(val) || val === 0) return "0";
          const num = Number(val);
          if (num === 0) return "0";
          const rounded = Math.round(num * 100) / 100;
          return String(rounded).replace(".", ",");
        },

        formatPrevistoPct(pct) {
          if (pct === undefined || pct === null || isNaN(pct) || pct <= 0.001) return "-";
          return this.formatPercent(pct);
        },

        buildMedicaoLookups() {
          const lookup = {};
          const cycles = this.replanResult?.cycles || [];
          const cNums = cycles.map(c => String(c.num));

          // 1. Level 5 from tab_replanejado
          for (const r of (this.replanResult?.tab_replanejado || [])) {
            if (r.level === 5 && r.code) {
              const cPcts = r.cycle_pcts_service || {};
              for (const cn of cNums) {
                const v = cPcts[cn];
                if (v > 0) lookup[`${r.code}_${cn}`] = v;
              }
            } else if (r.level === 6 && r.parent_code) {
              const tname = r.task_name || r.description;
              const sal = r.allocated_saldo || 0.0;
              const cVals = r.cycle_vals || {};
              const cPcts = r.cycle_pcts_service || {};
              for (const cn of cNums) {
                const cv = cVals[cn] || 0.0;
                if (sal > 0 && cv > 0) {
                  lookup[`${r.parent_code}::${tname}_${cn}`] = (cv / sal) * 100.0;
                } else if (cPcts[cn] > 0) {
                  lookup[`${r.parent_code}::${tname}_${cn}`] = cPcts[cn];
                }
              }
            }
          }

          // 2. Fallback past cycles from tab_distribuicao
          for (const r of (this.replanResult?.tab_distribuicao || [])) {
            if (r.level === 5 && r.code) {
              const cPcts = r.cycle_pcts || {};
              for (const cn of cNums) {
                const k = `${r.code}_${cn}`;
                if (lookup[k] === undefined && cPcts[cn] > 0) {
                  lookup[k] = cPcts[cn];
                }
              }
            } else if (r.level === 6 && r.parent_code) {
              const tname = r.task_name || r.description;
              const cPcts = r.cycle_pcts || {};
              for (const cn of cNums) {
                const k = `${r.parent_code}::${tname}_${cn}`;
                if (lookup[k] === undefined && cPcts[cn] > 0) {
                  lookup[k] = cPcts[cn];
                }
              }
            }
          }

          // 3. Macro levels from tab_ff_replanejado
          for (const r of (this.replanResult?.tab_ff_replanejado || [])) {
            if (r.level >= 1 && r.level <= 4) {
              const b = r.budget || 0.0;
              const cVals = r.cycle_vals || {};
              if (b > 0) {
                for (const cn of cNums) {
                  const cv = cVals[cn] || 0.0;
                  if (cv > 0) {
                    lookup[`${r.code}_${cn}`] = (cv / b) * 100.0;
                  }
                }
              }
            }
          }

          // 4. Level 1 Pinned Totalizer
          const totB = this.replanResult?.total_budget || 1.0;
          if (this.level1ReplanRow && totB > 0) {
            const cVals = this.level1ReplanRow.cycle_vals || {};
            for (const cn of cNums) {
              const cv = cVals[cn] || 0.0;
              if (cv > 0) {
                lookup[`level_1_${cn}`] = (cv / totB) * 100.0;
              }
            }
          }

          this.medPrevistoLookup = Object.freeze(lookup);

          // Pre-index tab_medicao for instant O(1) lookups (frozen to eliminate Alpine proxy overhead)
          this.medRowMap = Object.freeze(Object.fromEntries((this.replanResult?.tab_medicao || []).map(r => [r.code, r])));
          const l6map = {};
          const medRows = this.replanResult?.tab_medicao || [];
          for (let i = 0; i < medRows.length; i++) {
            const r = medRows[i];
            if (r.tasks_l6 && r.tasks_l6.length > 0) {
              for (let j = 0; j < r.tasks_l6.length; j++) {
                const t = r.tasks_l6[j];
                l6map[r.code + '::' + t.task_name] = t.monthly_measurements || {};
              }
            }
          }
          this.medL6MonthlyMap = Object.freeze(l6map);
        },

        updateMedCycleCols() {
          const cycles = this.replanResult?.cycles || [];
          if (!this.showPrevistoMedicao) {
            this.cachedMedCycleCols = cycles.map(c => ({
              key: `${c.num}_R`,
              num: c.num,
              type: 'R',
              label: 'M' + c.num,
              subLabel: c.period_label || c.name || ('M' + c.num),
              isPast: c.num <= this.cutoffMedNum
            }));
            return;
          }
          const cols = [];
          for (const c of cycles) {
            cols.push({
              key: `${c.num}_P`,
              num: c.num,
              type: 'P',
              label: `M${c.num} P`,
              subLabel: c.period_label || c.name || ('M' + c.num),
              isPast: c.num <= this.cutoffMedNum
            });
            cols.push({
              key: `${c.num}_R`,
              num: c.num,
              type: 'R',
              label: `M${c.num} R`,
              subLabel: c.period_label || c.name || ('M' + c.num),
              isPast: c.num <= this.cutoffMedNum
            });
          }
          this.cachedMedCycleCols = cols;
        },

        getMedPrevistoPct(row, cycleNum) {
          if (!row || !this.medPrevistoLookup) return 0.0;
          const k = row.isL6 
            ? (row.parent_code + '::' + (row.task_name || row.description) + '_' + cycleNum)
            : (row.code + '_' + cycleNum);
          return this.medPrevistoLookup[k] || 0.0;
        },

        getMedLevel1MonthDisplay(col) {
          if (!col) return '-';
          if (col.type === 'P') {
            const pct = this.medPrevistoLookup?.[`level_1_${col.num}`] || 0.0;
            return pct > 0.001 ? this.formatPercent(pct) : '-';
          }
          return this.level1MedRow ? this.getRollupMonthPct(this.level1MedRow, col.num) : '-';
        },

        hasCustomMonthly() {
          return Object.keys(this.customMonthlyL5).length > 0 || Object.keys(this.customMonthlyL6).length > 0;
        },

        async resetCustomMonthly() {
          if (!confirm("Deseja descartar as edições de medição e voltar ao que veio na importação desta versão?")) return;
          await this.restoreVersion('medicao');
          this.runSimulation();
        },

        recalculateWithCustomMeasurements() {
          this.runSimulation();
        },

        // --- Workday & Predecessor Math ---
        addWorkdays(dateStr, workdays) {
          if (!dateStr || dateStr === '-') return dateStr;
          const d = new Date(dateStr + "T00:00:00");
          let dur = Math.max(1, parseInt(workdays, 10) || 1);
          while (d.getDay() === 0 || d.getDay() === 6) {
            d.setDate(d.getDate() + 1);
          }
          let count = 1;
          while (count < dur) {
            d.setDate(d.getDate() + 1);
            if (d.getDay() !== 0 && d.getDay() !== 6) {
              count++;
            }
          }
          return d.toISOString().slice(0, 10);
        },

        calcStartDate(finishStr, workdays) {
          if (!finishStr || finishStr === '-') return finishStr;
          const d = new Date(finishStr + "T00:00:00");
          let dur = Math.max(1, parseInt(workdays, 10) || 1);
          while (d.getDay() === 0 || d.getDay() === 6) {
            d.setDate(d.getDate() - 1);
          }
          let count = 1;
          while (count < dur) {
            d.setDate(d.getDate() - 1);
            if (d.getDay() !== 0 && d.getDay() !== 6) {
              count++;
            }
          }
          return d.toISOString().slice(0, 10);
        },

        calcWorkdays(startStr, endStr) {
          if (!startStr || !endStr || startStr === '-' || endStr === '-') return 1;
          const s = new Date(startStr + "T00:00:00");
          const e = new Date(endStr + "T00:00:00");
          if (e < s) return 1;
          let count = 0;
          const cur = new Date(s);
          while (cur <= e) {
            if (cur.getDay() !== 0 && cur.getDay() !== 6) count++;
            cur.setDate(cur.getDate() + 1);
          }
          return Math.max(1, count);
        },

        getMinStartDateForTask(task) {
          if (!task || !task.predecessors || !task.predecessors.length) return null;
          const tasks = this.replanResult?.tab_cronograma?.tasks || [];
          let maxReq = null;
          for (const pStr of task.predecessors) {
            const m = String(pStr).trim().match(/^(\d+)\s*(FS|SS|FF|SF)?\s*([+-]\s*\d+)?d?$/i);
            if (!m) continue;
            const pId = m[1];
            const rtype = (m[2] || 'FS').toUpperCase();
            const lag = parseInt(m[3] || '0', 10);
            const pTask = tasks.find(t => String(t.id) === String(pId));
            if (!pTask || !pTask.end_date || pTask.end_date === '-') continue;
            let req = null;
            if (rtype === 'FS') {
              req = this.addWorkdays(pTask.end_date, 1 + lag);
            } else if (rtype === 'SS') {
              req = this.addWorkdays(pTask.start_date, lag);
            } else if (rtype === 'FF') {
              const targetFinish = this.addWorkdays(pTask.end_date, lag);
              req = this.calcStartDate(targetFinish, task.duration || 1);
            } else if (rtype === 'SF') {
              const targetFinish = this.addWorkdays(pTask.start_date, lag);
              req = this.calcStartDate(targetFinish, task.duration || 1);
            }
            if (req && (!maxReq || req > maxReq)) {
              maxReq = req;
            }
          }
          return maxReq;
        },

        openTaskDrawer(task) {
          if (this.wasDragging) return;
          this.drawerTask = JSON.parse(JSON.stringify(task));
          this.drawerPredecessors = [];
          if (this.drawerTask.predecessors) {
            for (const pStr of this.drawerTask.predecessors) {
              const m = String(pStr).trim().match(/^(\d+)\s*(FS|SS|FF|SF)?\s*([+-]\s*\d+)?d?$/i);
              if (!m) continue;
              const pId = m[1];
              const type = (m[2] || 'FS').toUpperCase();
              const lag = parseInt(m[3] || '0', 10);

              const other = this.replanResult?.tab_cronograma?.tasks?.find(tk => String(tk.id) === String(pId));
              this.drawerPredecessors.push({
                id: pId,
                name: other ? other.name : 'Tarefa #' + pId,
                type: type,
                lag: lag
              });
            }
          }
          this.selectedNewPredId = "";
          this.showTaskDrawer = true;
          this.$nextTick(() => lucide.createIcons());
        },

        openTaskDrawerFromRow(row) {
          if (!row || row.level !== 6) return;
          const tasks = this.replanResult?.tab_cronograma?.tasks || [];
          let target = null;
          if (row.task_id) {
            target = tasks.find(t => String(t.id) === String(row.task_id));
          }
          const searchName = (row.task_name || row.description || "").trim().toLowerCase();
          if (!target && searchName) {
            target = tasks.find(t => (t.name || "").trim().toLowerCase() === searchName);
          }
          if (!target && searchName) {
            target = tasks.find(t => {
              const tn = (t.name || "").trim().toLowerCase();
              return tn.startsWith(searchName) || searchName.startsWith(tn);
            });
          }
          if (target) {
            this.openTaskDrawer(target);
          } else {
            console.warn("Atividade do cronograma não encontrada para a linha:", row);
            alert(`Atividade "${row.description}" não encontrada no cronograma ativo.`);
          }
        },

        updateDrawerPred(pIdx) {
          this.rebuildDrawerPredecessorsStrings();
          this.syncDrawerWithPredecessors();
        },

        removeDrawerPred(pIdx) {
          this.drawerPredecessors.splice(pIdx, 1);
          this.rebuildDrawerPredecessorsStrings();
        },

        addDrawerPred() {
          if (!this.selectedNewPredId) return;
          const other = this.replanResult?.tab_cronograma?.tasks?.find(tk => String(tk.id) === String(this.selectedNewPredId));
          this.drawerPredecessors.push({
            id: String(this.selectedNewPredId),
            name: other ? other.name : 'Tarefa #' + this.selectedNewPredId,
            type: 'FS',
            lag: 0
          });
          this.selectedNewPredId = "";
          this.rebuildDrawerPredecessorsStrings();
          this.syncDrawerWithPredecessors();
        },

        syncDrawerWithPredecessors() {
          const minStart = this.getMinStartDateForTask(this.drawerTask);
          if (minStart && (!this.drawerTask.start_date || this.drawerTask.start_date < minStart)) {
            this.drawerTask.start_date = minStart;
            this.drawerTask.end_date = this.addWorkdays(minStart, this.drawerTask.duration || 1);
          }
        },

        rebuildDrawerPredecessorsStrings() {
          this.drawerTask.predecessors = this.drawerPredecessors.map(p => {
            const lagStr = p.lag > 0 ? `+${p.lag}d` : (p.lag < 0 ? `${p.lag}d` : '');
            return `${p.id}${p.type}${lagStr}`;
          });
        },

        onDrawerDurationChange() {
          if (this.drawerTask.start_date && this.drawerTask.duration > 0) {
            this.drawerTask.end_date = this.addWorkdays(this.drawerTask.start_date, this.drawerTask.duration);
          }
        },

        onDrawerStartChange() {
          if (this.drawerTask.start_date && this.drawerTask.duration > 0) {
            const minStart = this.getMinStartDateForTask(this.drawerTask);
            if (minStart && this.drawerTask.start_date < minStart) {
              this.drawerTask.start_date = minStart;
            }
            this.drawerTask.end_date = this.addWorkdays(this.drawerTask.start_date, this.drawerTask.duration);
          }
        },

        onDrawerEndChange() {
          if (this.drawerTask.start_date && this.drawerTask.end_date) {
            this.drawerTask.duration = this.calcWorkdays(this.drawerTask.start_date, this.drawerTask.end_date);
          }
        },

        async saveDrawerTask() {
          if (!this.drawerTask || this.isSavingDrawer) return;
          this.isSavingDrawer = true;
          try {
            const taskList = this.replanResult?.tab_cronograma?.tasks || [];
            const idx = taskList.findIndex(t => t.id === this.drawerTask.id || t.name === this.drawerTask.name);
            if (idx !== -1) {
              taskList[idx] = JSON.parse(JSON.stringify(this.drawerTask));
            }
            const key = String(this.drawerTask.id || this.drawerTask.name);
            if (!this.customScheduleOverrides) this.customScheduleOverrides = {};
            this.customScheduleOverrides[key] = {
              id: this.drawerTask.id,
              name: this.drawerTask.name,
              duration: this.drawerTask.duration,
              start_date: this.drawerTask.start_date,
              end_date: this.drawerTask.end_date,
              predecessors: this.drawerTask.predecessors || []
            };
            this.showTaskDrawer = false;
            await this.runSimulation();
          } catch (err) {
            console.error("Erro ao salvar tarefa:", err);
            alert("Erro ao salvar alterações da tarefa.");
          } finally {
            this.isSavingDrawer = false;
          }
        },

        // --- Gantt & LOB Math ---
        get projectStartDate() {
          const pStart = this.replanResult?.tab_cronograma?.project_start;
          if (pStart && pStart !== '-') return pStart;
          if (this.replanResult?.cycles && this.replanResult.cycles.length > 0) {
            return this.replanResult.cycles[0].start;
          }
          const tasks = this.replanResult?.tab_cronograma?.tasks || [];
          let min = "2025-09-21";
          for (const t of tasks) {
            if (t.start_date && t.start_date !== '-' && t.start_date < min) min = t.start_date;
          }
          return min;
        },

        get ganttMonths() {
          if (this.replanResult?.cycles && this.replanResult.cycles.length > 0) {
            const start = new Date(this.projectStartDate + "T00:00:00");
            return this.replanResult.cycles.map(c => {
              const cStart = new Date(c.start + "T00:00:00");
              const cEnd = new Date(c.end + "T00:00:00");
              const days = Math.max(1, Math.round((cEnd - cStart) / 86400000) + 1);
              const x = Math.max(0, Math.round((cStart - start) / 86400000) * this.ganttZoom);
              const width = Math.max(24, days * this.ganttZoom);
              return {
                label: c.period_label || c.name,
                x: x,
                width: width,
                num: c.num
              };
            });
          }
          const start = new Date(this.projectStartDate + "T00:00:00");
          const months = [];
          for (let m = 0; m < 48; m++) {
            const d = new Date(start);
            d.setMonth(d.getMonth() + m);
            d.setDate(1);
            months.push({
              label: d.toLocaleDateString("pt-BR", { month: "short", year: "2-digit" }).toUpperCase(),
              x: m * 30 * this.ganttZoom,
              width: 30 * this.ganttZoom,
              num: m + 1
            });
          }
          return months;
        },

        get ganttWidth() {
          const months = this.ganttMonths;
          if (!months.length) return 1600;
          const last = months[months.length - 1];
          return Math.max(1600, last.x + last.width + 100);
        },

        get visibleGanttTasks() {
          let tasks = [...(this.replanResult?.tab_cronograma?.tasks || [])];
          if (this.searchCrono) {
            const q = this.searchCrono.toLowerCase();
            tasks = tasks.filter(t => 
              (t.name && t.name.toLowerCase().includes(q)) || 
              (t.lot && t.lot.toLowerCase().includes(q)) || 
              (t.lote_mae && t.lote_mae.toLowerCase().includes(q)) ||
              (t.id && String(t.id).includes(q))
            );
          }
          tasks.sort((a, b) => {
            const idA = parseInt(a.id, 10) || 0;
            const idB = parseInt(b.id, 10) || 0;
            return idA - idB;
          });
          return tasks;
        },

        get ganttHeight() {
          return this.visibleGanttTasks.length * 28 + 80;
        },

        get ganttCutoffX() {
          const start = new Date(this.projectStartDate + "T00:00:00");
          let cutoffDateStr = this.replanResult?.cutoff_date;
          if (!cutoffDateStr && this.replanResult?.cycles && this.cutoffMedNum > 0) {
            const c = this.replanResult.cycles.find(cy => cy.num === this.cutoffMedNum);
            if (c) cutoffDateStr = c.end;
          }
          if (cutoffDateStr) {
            const cutoff = new Date(cutoffDateStr + "T00:00:00");
            const days = Math.round((cutoff - start) / 86400000);
            return Math.max(0, days * this.ganttZoom);
          }
          return (this.cutoffMedNum * 30.4) * this.ganttZoom;
        },

        getTaskX(t) {
          if (!t || !t.start_date || t.start_date === '-') return 0;
          const start = new Date(this.projectStartDate + "T00:00:00");
          const taskStart = new Date(t.start_date + "T00:00:00");
          const days = Math.round((taskStart - start) / 86400000);
          return Math.max(0, days * this.ganttZoom);
        },

        getTaskW(t) {
          if (!t) return 10;
          const dur = t.duration || 1;
          return Math.max(10, dur * this.ganttZoom);
        },

        startTaskDrag(event, task, mode) {
          this.wasDragging = false;
          this.dragState = {
            task: task,
            mode: mode,
            startX: event.clientX,
            origDuration: task.duration || 1,
            origStart: task.start_date,
            origEnd: task.end_date
          };
        },

        onGanttMouseMove(event) {
          if (!this.dragState) return;
          const dx = event.clientX - this.dragState.startX;
          if (Math.abs(dx) > 3) {
            this.wasDragging = true;
          }
          const dayDelta = Math.round(dx / this.ganttZoom);

          if (this.dragState.mode === 'move') {
            const d = new Date(this.dragState.origStart + "T00:00:00");
            d.setDate(d.getDate() + dayDelta);
            let newStart = d.toISOString().slice(0, 10);
            const minStart = this.getMinStartDateForTask(this.dragState.task);
            if (minStart && newStart < minStart) {
              newStart = minStart;
            }
            this.dragState.task.start_date = newStart;
            this.dragState.task.end_date = this.addWorkdays(newStart, this.dragState.task.duration || 1);
          } else if (this.dragState.mode === 'resize') {
            const newDur = Math.max(1, this.dragState.origDuration + dayDelta);
            this.dragState.task.duration = newDur;
            this.dragState.task.end_date = this.addWorkdays(this.dragState.task.start_date, newDur);
          }
        },

        async onGanttMouseUp() {
          if (!this.dragState) return;
          const task = this.dragState.task;
          const origDur = this.dragState.origDuration;
          const origStart = this.dragState.origStart;
          const origEnd = this.dragState.origEnd;
          const hasChanged = (task.duration !== origDur || task.start_date !== origStart || task.end_date !== origEnd);
          this.dragState = null;

          if (hasChanged && task) {
            const key = String(task.id || task.name);
            if (!this.customScheduleOverrides) this.customScheduleOverrides = {};
            this.customScheduleOverrides[key] = {
              id: task.id,
              name: task.name,
              duration: task.duration,
              start_date: task.start_date,
              end_date: task.end_date,
              predecessors: task.predecessors || []
            };
            await this.runSimulation();
          }

          setTimeout(() => {
            this.wasDragging = false;
          }, 150);
        },

        resetScheduleOverrides() {
          if (confirm("Deseja reverter todas as alterações manuais do cronograma para o original desta versão?")) {
            this.restoreVersion('cronograma').then(() => this.runSimulation());
          }
        },

        // --- Linha de Balanço (LOB) ---
        getFloorRank(name) {
          if (!name) return 500;
          const n = name.toLowerCase().trim();
          if (n.includes("subsolo 4") || n.includes("ss4") || n.includes("4º subsolo") || n.includes("4o subsolo")) return -40;
          if (n.includes("subsolo 3") || n.includes("ss3") || n.includes("3º subsolo") || n.includes("3o subsolo")) return -30;
          if (n.includes("subsolo 2") || n.includes("ss2") || n.includes("2º subsolo") || n.includes("2o subsolo")) return -20;
          if (n.includes("subsolo 1") || n.includes("ss1") || n.includes("1º subsolo") || n.includes("1o subsolo") || n.includes("subsolo")) return -10;
          if (n.includes("fundação") || n.includes("fundacao") || n.includes("estaca") || n.includes("bloco")) return -5;
          if (n.includes("térreo") || n.includes("terreo") || n.includes("hall") || n.includes("guarita")) return 0;
          if (n.includes("mezanino") || n.includes("garagem")) return 5;
          
          const match = n.match(/(\d+)[\sºoaª]*\s*(?:pav|andar|tipo|laje)/i) || n.match(/(?:pav|andar|tipo)[\sºoaª]*\s*(\d+)/i) || n.match(/^(\d+)[\sºoaª]*/);
          if (match) {
            const num = parseInt(match[1]);
            if (!isNaN(num)) return num * 10;
          }
          
          if (n.includes("ático") || n.includes("atico")) return 800;
          if (n.includes("barrilete") || n.includes("cx") || n.includes("caixa")) return 850;
          if (n.includes("cobertura") || n.includes("cob")) return 900;
          if (n.includes("telhado") || n.includes("platibanda")) return 950;
          
          return 500;
        },

        get lobUniqueLotesMae() {
          const tasks = this.replanResult?.tab_cronograma?.tasks || [];
          const fromResult = this.replanResult?.tab_cronograma?.lotes_mae;
          const list = (fromResult && fromResult.length) ? fromResult : [...new Set(tasks.map(t => t.lote_mae || 'Geral'))];
          return list.filter(Boolean);
        },

        get lobFilteredLots() {
          const tasks = this.replanResult?.tab_cronograma?.tasks || [];
          let filtered = tasks;
          if (this.lobLoteMaeFilter !== "all") {
            filtered = filtered.filter(t => (t.lote_mae || 'Geral') === this.lobLoteMaeFilter);
          }
          const lots = [...new Set(filtered.map(t => t.lot || 'Geral'))];
          return this.sortLots(lots);
        },

        get lobUniqueLots() {
          const tasks = this.replanResult?.tab_cronograma?.tasks || [];
          const lots = [...new Set(tasks.map(t => t.lot || 'Geral'))];
          return this.sortLots(lots);
        },

        sortLots(lotList) {
          const list = [...lotList];
          if (this.lobSortOrder === "bottom-to-top") {
            // Screen top is high rank (e.g. Cobertura: 900), screen bottom is low rank (Subsolo: -10)
            return list.sort((a, b) => {
              const diff = this.getFloorRank(b) - this.getFloorRank(a);
              return diff !== 0 ? diff : a.localeCompare(b, 'pt-BR', { numeric: true });
            });
          } else if (this.lobSortOrder === "top-to-bottom") {
            return list.sort((a, b) => {
              const diff = this.getFloorRank(a) - this.getFloorRank(b);
              return diff !== 0 ? diff : a.localeCompare(b, 'pt-BR', { numeric: true });
            });
          } else {
            return list.sort((a, b) => a.localeCompare(b, 'pt-BR', { numeric: true }));
          }
        },

        get lobLanes() {
          let tasks = this.replanResult?.tab_cronograma?.tasks || [];
          if (this.lobLoteMaeFilter !== "all") {
            tasks = tasks.filter(t => (t.lote_mae || 'Geral') === this.lobLoteMaeFilter);
          }
          let lots = this.lobFilteredLots;
          if (this.lobLotFilter !== "all") {
            lots = lots.filter(l => l === this.lobLotFilter);
          }
          return lots.map(lotName => ({
            name: lotName,
            tasks: tasks.filter(t => (t.lot || 'Geral') === lotName)
          }));
        },

        get lobWidth() {
          return this.ganttWidth;
        },

        get lobHeight() {
          return this.lobLanes.length * 34 + 60;
        },

        getLobTaskColor(name) {
          const n = name.toUpperCase();
          if (n.includes("ESTRUTURA")) return "#2563eb";
          if (n.includes("ALVENARIA")) return "#f97316";
          if (n.includes("INSTALAÇÕES") || n.includes("ELETRICA") || n.includes("HIDRAULICA")) return "#059669";
          if (n.includes("EMBOÇO") || n.includes("REVEST")) return "#7c3aed";
          if (n.includes("PINTURA")) return "#db2777";
          if (n.includes("FACHADA")) return "#d97706";
          return "#475569";
        },

        // --- Level 1 Totalizer Getters (pinned to header) ---
        get level1BudgetRow() {
          return (this.replanResult?.tab_orcamento || []).find(r => r.level === 1) || null;
        },
        get level1FFRow() {
          return (this.replanResult?.tab_fisico_financeiro || []).find(r => r.level === 1) || null;
        },
        get level1MedRow() {
          return (this.replanResult?.tab_medicao || []).find(r => r.level === 1) || null;
        },
        get level1ReplanRow() {
          return (this.replanResult?.tab_replanejado || []).find(r => r.level === 1) || null;
        },
        get level1FFRepRow() {
          return (this.replanResult?.tab_ff_replanejado || []).find(r => r.level === 1) || null;
        },

        // --- Filtered Getters ---
        get filteredFFRows() {
          const allRows = (this.replanResult?.tab_fisico_financeiro || []).filter(r => r.level > 1);
          let rows = allRows;
          if (this.levelFilterFF > 0) {
            rows = rows.filter(r => r.level <= this.levelFilterFF);
          }
          if (this.selectedFilterMonths.length > 0) {
            const months = this.selectedFilterMonths;
            const matchingCodes = new Set();
            for (const r of allRows) {
              let hasVal = false;
              for (const m of months) {
                const val = (r.cycle_vals && r.cycle_vals[String(m)]) || 0;
                const pct = (r.cycle_pcts && r.cycle_pcts[String(m)]) || 0;
                if (val > 0.0001 || pct > 0.0001) {
                  hasVal = true;
                  break;
                }
              }
              if (hasVal) {
                matchingCodes.add(r.code);
                const parts = r.code.split('.');
                for (let i = 1; i < parts.length; i++) {
                  matchingCodes.add(parts.slice(0, i).join('.'));
                }
              }
            }
            rows = rows.filter(r => matchingCodes.has(r.code));
          }
          return rows;
        },

        get filteredFFRepRows() {
          const allRows = (this.replanResult?.tab_ff_replanejado || []).filter(r => r.level > 1);
          let rows = allRows;
          if (this.levelFilterFFRep > 0) {
            rows = rows.filter(r => r.level <= this.levelFilterFFRep);
          }
          if (this.selectedFilterMonths.length > 0) {
            const months = this.selectedFilterMonths;
            const matchingCodes = new Set();
            for (const r of allRows) {
              let hasVal = false;
              for (const m of months) {
                const val = (r.cycle_vals && r.cycle_vals[String(m)]) || 0;
                const pct = (r.cycle_pcts && r.cycle_pcts[String(m)]) || 0;
                if (val > 0.0001 || pct > 0.0001) {
                  hasVal = true;
                  break;
                }
              }
              if (hasVal) {
                matchingCodes.add(r.code);
                const parts = r.code.split('.');
                for (let i = 1; i < parts.length; i++) {
                  matchingCodes.add(parts.slice(0, i).join('.'));
                }
              }
            }
            rows = rows.filter(r => matchingCodes.has(r.code));
          }
          return rows;
        },

        get activeCyclesList() {
          return this.replanResult?.extended_cycles || this.replanResult?.cycles || [];
        },

        get level1CompRow() {
          return (this.replanResult?.tab_competencia || []).find(r => r.level === 1) || null;
        },

        get level1FinRow() {
          return (this.replanResult?.tab_financeiro || []).find(r => r.level === 1) || null;
        },

        get filteredCompRows() {
          const allRows = (this.replanResult?.tab_competencia || []).filter(r => r.level > 1);
          if (this.levelFilterComp > 0) {
            return allRows.filter(r => r.level <= this.levelFilterComp);
          }
          return allRows;
        },

        get filteredFinRows() {
          const allRows = (this.replanResult?.tab_financeiro || []).filter(r => r.level > 1);
          if (this.levelFilterFin > 0) {
            return allRows.filter(r => r.level <= this.levelFilterFin);
          }
          return allRows;
        },

        getCompCellValue(row, cycleNum) {
          if (!row) return "-";
          const cKey = String(cycleNum);
          if (this.compViewMode === 'pct') {
            const pct = row.cycle_pcts?.[cKey] || 0;
            return pct > 0 ? pct.toFixed(2) + '%' : '-';
          } else if (this.compViewMode === 'mat') {
            const val = row.cycle_mat_vals?.[cKey];
            return val !== undefined ? this.formatCurrency(val) : '-';
          } else if (this.compViewMode === 'mo') {
            const val = row.cycle_mo_vals?.[cKey];
            return val !== undefined ? this.formatCurrency(val) : '-';
          } else {
            const val = row.cycle_vals?.[cKey];
            return val !== undefined ? this.formatCurrency(val) : '-';
          }
        },

        getCompCellTotal(row) {
          if (!row) return "-";
          if (this.compViewMode === 'pct') {
            return row.total_pct ? row.total_pct.toFixed(2) + '%' : '0.00%';
          } else if (this.compViewMode === 'mat') {
            return this.formatCurrency(row.total_mat);
          } else if (this.compViewMode === 'mo') {
            return this.formatCurrency(row.total_mo);
          } else {
            return this.formatCurrency(row.total);
          }
        },

        getFinCellValue(row, cycleNum) {
          if (!row) return "-";
          const cKey = String(cycleNum);
          if (this.finViewMode === 'pct') {
            const pct = row.cycle_pcts?.[cKey] || 0;
            return pct > 0 ? pct.toFixed(2) + '%' : '-';
          } else if (this.finViewMode === 'mat') {
            const val = row.cycle_mat_vals?.[cKey];
            return val !== undefined ? this.formatCurrency(val) : '-';
          } else if (this.finViewMode === 'mo') {
            const val = row.cycle_mo_vals?.[cKey];
            return val !== undefined ? this.formatCurrency(val) : '-';
          } else {
            const val = row.cycle_vals?.[cKey];
            return val !== undefined ? this.formatCurrency(val) : '-';
          }
        },

        getFinCellTotal(row) {
          if (!row) return "-";
          if (this.finViewMode === 'pct') {
            return row.total_pct ? row.total_pct.toFixed(2) + '%' : '0.00%';
          } else if (this.finViewMode === 'mat') {
            return this.formatCurrency(row.total_mat);
          } else if (this.finViewMode === 'mo') {
            return this.formatCurrency(row.total_mo);
          } else {
            return this.formatCurrency(row.total);
          }
        },

        getReplanSaldoValue(row) {
          if (!row) return "-";
          if (this.replanSaldoInPct) {
            if (row.level === 6) {
              if (row.allocated_saldo_pct_service !== undefined && row.allocated_saldo_pct_service !== null) {
                return row.allocated_saldo_pct_service.toFixed(2) + '%';
              }
              const pBudget = row.parent_budget || 0;
              return pBudget > 0 ? ((row.allocated_saldo / pBudget) * 100).toFixed(2) + '%' : '-';
            }
            if (row.saldo_pct !== undefined && row.saldo_pct !== null) {
              return row.saldo_pct.toFixed(2) + '%';
            }
            return (row.budget && row.budget > 0) ? ((row.saldo / row.budget) * 100).toFixed(2) + '%' : '-';
          }
          return this.formatCurrency(row.level === 6 ? row.allocated_saldo : row.saldo);
        },

        getReplanCellValue(row, cycleNum) {
          if (!row) return "-";
          const cKey = String(cycleNum);
          const val = row.cycle_vals?.[cKey] ?? 0;
          if (!val || val <= 0.0001) return "-";
          if (this.ffRepViewMode === 'pct') {
            const totProj = this.replanResult?.total_budget || 1.0;
            return ((val / totProj) * 100).toFixed(2) + '%';
          } else if (this.ffRepViewMode === 'pct_service') {
            const baseBudget = row.level === 6 ? (row.parent_budget || 0) : (row.budget || 0);
            return baseBudget > 0 ? ((val / baseBudget) * 100).toFixed(2) + '%' : '-';
          } else if (this.ffRepViewMode === 'pct_etapa') {
            if (row.level === 6) {
              const sal = row.allocated_saldo || 0;
              return sal > 0 ? ((val / sal) * 100).toFixed(2) + '%' : '-';
            } else {
              const baseBudget = row.budget || 0;
              return baseBudget > 0 ? ((val / baseBudget) * 100).toFixed(2) + '%' : '-';
            }
          } else {
            return this.formatCurrency(val);
          }
        },

        getReplanCellTotal(row) {
          if (!row) return "-";
          const totVal = row.total ?? 0;
          if (this.ffRepViewMode === 'pct') {
            const totProj = this.replanResult?.total_budget || 1.0;
            return totProj > 0 ? ((totVal / totProj) * 100).toFixed(2) + '%' : '0.00%';
          } else if (this.ffRepViewMode === 'pct_service') {
            const baseBudget = row.level === 6 ? (row.parent_budget || 0) : (row.budget || 0);
            return baseBudget > 0 ? ((totVal / baseBudget) * 100).toFixed(2) + '%' : '-';
          } else if (this.ffRepViewMode === 'pct_etapa') {
            if (row.level === 6) {
              const sal = row.allocated_saldo || 0;
              return sal > 0 ? ((totVal / sal) * 100).toFixed(2) + '%' : (totVal > 0 ? '100.00%' : '-');
            } else {
              const baseBudget = row.budget || 0;
              return baseBudget > 0 ? ((totVal / baseBudget) * 100).toFixed(2) + '%' : '-';
            }
          } else {
            return this.formatCurrency(totVal);
          }
        },

        getReplanLevel1Saldo() {
          const s = this.level1ReplanRow?.saldo ?? this.replanResult?.total_balance ?? 0;
          const b = this.level1ReplanRow?.budget || this.replanResult?.total_budget || 0;
          if (this.replanSaldoInPct) {
            return b > 0 ? ((s / b) * 100).toFixed(2) + '%' : '0.00%';
          }
          return this.formatCurrency(s);
        },

        getReplanLevel1CycleValue(cycleNum) {
          const cKey = String(cycleNum);
          const val = this.level1ReplanRow?.cycle_vals?.[cKey] || 0;
          if (this.ffRepViewMode === 'pct' || this.ffRepViewMode === 'pct_service' || this.ffRepViewMode === 'pct_etapa') {
            const totProj = this.replanResult?.total_budget || 1.0;
            return val > 0 ? ((val / totProj) * 100).toFixed(2) + '%' : '-';
          } else {
            return this.formatCurrency(val);
          }
        },

        getReplanLevel1Total() {
          const totVal = this.level1ReplanRow?.total || this.replanResult?.total_budget || 0;
          if (this.ffRepViewMode === 'pct' || this.ffRepViewMode === 'pct_service' || this.ffRepViewMode === 'pct_etapa') {
            return '100.00%';
          } else {
            return this.formatCurrency(totVal);
          }
        },

        // --- Modal Redistribuição de Saldo (Nível 5 ↳ 6) ---
        openReplanWeightModal(row) {
          if (!row || row.level !== 5) return;
          this.modalReplanRow = row;

          const allRows = this.replanResult?.tab_replanejado || [];
          const childRows = (this._replanChildrenByParent && this._replanChildrenByParent[row.code]) 
            ? this._replanChildrenByParent[row.code] 
            : allRows.filter(r => r.parent_code === row.code && r.level === 6);
          if (childRows.length === 0) {
            if (confirm(`O serviço "${row.code} - ${row.description}" ainda não possui atividades vinculadas no cronograma para redistribuir o saldo.\n\nDeseja abrir a janela de vínculos agora para vincular atividades do cronograma a este serviço?`)) {
              this.openLinkModal(row.code, -1);
            }
            return;
          }

          const existingCfg = this.customReplanWeights[row.code] || row.replan_weight_config;
          const initialMode = existingCfg?.mode || (row.has_custom_replan_weights ? row.replan_weight_mode : 'percentual');
          this.modalReplanCriteria = initialMode || 'percentual';

          this.modalReplanTasks = childRows.map(child => {
            const tName = child.task_name || child.description;
            const tId = child.task_id || "";
            let savedWeight = null;
            let savedQty = null;
            let savedArea = null;

            if (existingCfg) {
              const weightsDict = existingCfg.weights || existingCfg;
              savedWeight = weightsDict[tName] ?? weightsDict[tId] ?? null;
              if (existingCfg.inputs) {
                if (existingCfg.mode === 'quantidade') savedQty = existingCfg.inputs[tName] ?? existingCfg.inputs[tId] ?? null;
                if (existingCfg.mode === 'area') savedArea = existingCfg.inputs[tName] ?? existingCfg.inputs[tId] ?? null;
              }
            }

            const weightPct = savedWeight !== null ? Number(savedWeight) : Number(child.future_weight_pct || 0);
            const saldoVal = Number(row.saldo || 0) * (weightPct / 100.0);

            return {
              task_id: tId,
              task_name: tName,
              duration: child.duration || 1,
              input_qty: savedQty,
              input_area: savedArea,
              weight_pct: Number(weightPct.toFixed(2)),
              allocated_saldo: Number(saldoVal.toFixed(2))
            };
          });

          this.showReplanWeightModal = true;
          this.$nextTick(() => {
            if (window.lucide) {
              const modalEl = document.querySelector('[x-show="showReplanWeightModal"]');
              try {
                if (modalEl) lucide.createIcons({ root: modalEl });
                else lucide.createIcons();
              } catch (_) {}
            }
          });
        },

        closeReplanWeightModal() {
          this.showReplanWeightModal = false;
          this.modalReplanRow = null;
          this.modalReplanTasks = [];
        },

        setReplanCriteria(mode) {
          this.modalReplanCriteria = mode;
          if (mode === 'tempo') {
            const totDur = this.modalReplanTasks.reduce((acc, t) => acc + (Number(t.duration) || 0), 0);
            const parentSaldo = Number(this.modalReplanRow?.saldo || 0);
            this.modalReplanTasks.forEach(t => {
              const w = totDur > 0 ? ((Number(t.duration) || 0) / totDur) * 100.0 : 0.0;
              t.weight_pct = Number(w.toFixed(2));
              t.allocated_saldo = Number((parentSaldo * (t.weight_pct / 100.0)).toFixed(2));
            });
          } else if (mode === 'quantidade' || mode === 'area') {
            this.onReplanQtyOrAreaChange();
          }
          this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        onReplanQtyOrAreaChange() {
          const isQty = this.modalReplanCriteria === 'quantidade';
          const parentSaldo = Number(this.modalReplanRow?.saldo || 0);
          const totalMetric = this.modalReplanTasks.reduce((acc, t) => {
            const val = Number(isQty ? t.input_qty : t.input_area) || 0;
            return acc + val;
          }, 0);

          this.modalReplanTasks.forEach(t => {
            const val = Number(isQty ? t.input_qty : t.input_area) || 0;
            const w = totalMetric > 0 ? (val / totalMetric) * 100.0 : 0.0;
            t.weight_pct = Number(w.toFixed(2));
            t.allocated_saldo = Number((parentSaldo * (t.weight_pct / 100.0)).toFixed(2));
          });
        },

        onReplanPercentChange(idx) {
          const parentSaldo = Number(this.modalReplanRow?.saldo || 0);
          const t = this.modalReplanTasks[idx];
          if (!t) return;
          if (t.weight_pct < 0) t.weight_pct = 0;
          if (t.weight_pct > 100) t.weight_pct = 100;
          t.allocated_saldo = Number((parentSaldo * (Number(t.weight_pct || 0) / 100.0)).toFixed(2));
        },

        divideReplanEqually() {
          const n = this.modalReplanTasks.length;
          if (n === 0) return;
          const parentSaldo = Number(this.modalReplanRow?.saldo || 0);
          const basePct = Number((100.0 / n).toFixed(2));
          let sumAssigned = 0;
          this.modalReplanTasks.forEach((t, i) => {
            if (i === n - 1) {
              t.weight_pct = Number((100.0 - sumAssigned).toFixed(2));
            } else {
              t.weight_pct = basePct;
              sumAssigned += basePct;
            }
            t.allocated_saldo = Number((parentSaldo * (t.weight_pct / 100.0)).toFixed(2));
          });
        },

        adjustReplanDifferenceOnLast() {
          const n = this.modalReplanTasks.length;
          if (n < 2) return;
          const parentSaldo = Number(this.modalReplanRow?.saldo || 0);
          const sumOthers = this.modalReplanTasks.slice(0, n - 1).reduce((acc, t) => acc + (Number(t.weight_pct) || 0), 0);
          const last = this.modalReplanTasks[n - 1];
          last.weight_pct = Math.max(0, Number((100.0 - sumOthers).toFixed(2)));
          last.allocated_saldo = Number((parentSaldo * (last.weight_pct / 100.0)).toFixed(2));
        },

        getReplanModalTotalPct() {
          return this.modalReplanTasks.reduce((acc, t) => acc + (Number(t.weight_pct) || 0), 0);
        },

        getReplanModalTotalSaldo() {
          return this.modalReplanTasks.reduce((acc, t) => acc + (Number(t.allocated_saldo) || 0), 0);
        },

        isReplanModalValid() {
          if (!this.modalReplanTasks || this.modalReplanTasks.length === 0) return false;
          const tot = this.getReplanModalTotalPct();
          return Math.abs(tot - 100.0) < 0.05;
        },

        async saveReplanWeights() {
          if (!this.isReplanModalValid() || !this.modalReplanRow) return;
          this.isSavingReplanWeights = true;
          try {
            const weights = {};
            const inputs = {};
            this.modalReplanTasks.forEach(t => {
              weights[t.task_name] = t.weight_pct;
              if (this.modalReplanCriteria === 'quantidade') inputs[t.task_name] = t.input_qty;
              if (this.modalReplanCriteria === 'area') inputs[t.task_name] = t.input_area;
            });

            this.customReplanWeights[this.modalReplanRow.code] = {
              mode: this.modalReplanCriteria,
              weights: weights,
              inputs: inputs
            };

            this.closeReplanWeightModal();
            await this.runSimulation();
          } catch (e) {
            console.error("Erro ao salvar pesos do replanejamento:", e);
            alert("Erro ao salvar redistribuição de pesos.");
          } finally {
            this.isSavingReplanWeights = false;
          }
        },

        async resetReplanWeights(code) {
          if (!confirm("Deseja restaurar a distribuição para a duração padrão do cronograma?")) return;
          delete this.customReplanWeights[code];
          this.closeReplanWeightModal();
          await this.runSimulation();
        },

        async openConfigCurvasModal() {
          this.searchCurvasConfig = "";
          this.curvasLevelFilter = 0;
          this.collapsedCurvasNodes = {};
          this.showConfigCurvasModal = true;
          await this.fetchCurvasConfig();
          this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        get filteredCurvasConfigs() {
          let list = this.editableCurvasConfigs || [];
          const q = (this.searchCurvasConfig || '').trim().toLowerCase();
          
          if (q) {
            return list.filter(st => 
              (st.code && st.code.toLowerCase().includes(q)) || 
              (st.description && st.description.toLowerCase().includes(q))
            );
          }
          
          const maxLevel = Number(this.curvasLevelFilter) || 0;
          if (maxLevel > 0) {
            list = list.filter(st => {
              const lvl = Number(st.level) || (st.code ? st.code.split('.').length : 2);
              return lvl <= maxLevel;
            });
          }
          
          // Oculta nós cujos ancestrais estejam colapsados
          const collapsed = this.collapsedCurvasNodes || {};
          return list.filter(st => {
            const code = st.code || '';
            const parts = code.split('.');
            for (let i = 1; i < parts.length; i++) {
              const ancestorCode = parts.slice(0, i).join('.');
              if (collapsed[ancestorCode]) return false;
            }
            return true;
          });
        },

        hasCurvasChildren(code) {
          if (!code) return false;
          const prefix = code + '.';
          return (this.editableCurvasConfigs || []).some(st => (st.code || '').startsWith(prefix));
        },

        isCurvasNodeCollapsed(code) {
          return !!this.collapsedCurvasNodes[code];
        },

        toggleCurvasNode(code) {
          const current = !!this.collapsedCurvasNodes[code];
          this.collapsedCurvasNodes = Object.assign({}, this.collapsedCurvasNodes, { [code]: !current });
          this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        expandAllCurvasNodes() {
          this.collapsedCurvasNodes = {};
          this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        collapseAllCurvasNodes() {
          const map = {};
          (this.editableCurvasConfigs || []).forEach(st => {
            const lvl = Number(st.level) || (st.code ? st.code.split('.').length : 2);
            if (lvl < 5 && this.hasCurvasChildren(st.code)) {
              map[st.code] = true;
            }
          });
          this.collapsedCurvasNodes = map;
          this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },


        onCurvasStageEdited(st, field) {
          if (!st) return;
          if (field === 'material_pct') {
            const m = Math.max(0, Math.min(100, Number(st.material_pct) || 0));
            st.material_pct = m;
            st.labor_pct = Math.round((100 - m) * 100) / 100;
          } else if (field === 'labor_pct') {
            const l = Math.max(0, Math.min(100, Number(st.labor_pct) || 0));
            st.labor_pct = l;
            st.material_pct = Math.round((100 - l) * 100) / 100;
          }

          st.is_custom = true;
          st.source = "Personalizado";

          // Propagação em cascata para todos os descendentes que herdam deste nó
          const prefix = st.code + '.';
          (this.editableCurvasConfigs || []).forEach(desc => {
            if ((desc.code || '').startsWith(prefix)) {
              if (!desc.is_custom || (desc.source && desc.source.startsWith("Herdado de"))) {
                desc.material_pct = st.material_pct;
                desc.labor_pct = st.labor_pct;
                desc.anticipation_days = st.anticipation_days;
                desc.distribution_type = st.distribution_type;
                desc.num_batches = st.num_batches;
                desc.payment_terms = st.payment_terms;
                desc.is_custom = false;
                desc.source = `Herdado de ${st.code}`;
              }
            }
          });
        },

        resetToInherited(st) {
          if (!st || !st.code) return;
          const parts = st.code.split('.');
          let parentCfg = null;
          
          for (let i = parts.length - 1; i >= 1; i--) {
            const pCode = parts.slice(0, i).join('.');
            const found = (this.editableCurvasConfigs || []).find(c => c.code === pCode);
            if (found) {
              parentCfg = found;
              break;
            }
          }

          if (parentCfg) {
            st.material_pct = parentCfg.material_pct;
            st.labor_pct = parentCfg.labor_pct;
            st.anticipation_days = parentCfg.anticipation_days;
            st.distribution_type = parentCfg.distribution_type;
            st.num_batches = parentCfg.num_batches;
            st.payment_terms = parentCfg.payment_terms;
            st.is_custom = false;
            st.source = `Herdado de ${parentCfg.code}`;
          } else {
            st.material_pct = 60.0;
            st.labor_pct = 40.0;
            st.anticipation_days = 15;
            st.distribution_type = "continuo";
            st.num_batches = null;
            st.payment_terms = "28";
            st.is_custom = false;
            st.source = "Padrão da Obra";
          }

          // Propaga o reset para descendentes dependentes
          const prefix = st.code + '.';
          (this.editableCurvasConfigs || []).forEach(desc => {
            if ((desc.code || '').startsWith(prefix)) {
              if (!desc.is_custom || (desc.source && desc.source.startsWith("Herdado de"))) {
                desc.material_pct = st.material_pct;
                desc.labor_pct = st.labor_pct;
                desc.anticipation_days = st.anticipation_days;
                desc.distribution_type = st.distribution_type;
                desc.num_batches = st.num_batches;
                desc.payment_terms = st.payment_terms;
                desc.is_custom = false;
                desc.source = `Herdado de ${st.source.startsWith("Herdado de") ? st.source.replace("Herdado de ", "") : st.code}`;
              }
            }
          });
        },

        async fetchCurvasConfig() {
          try {
            const resp = await fetch(`/api/replan/${this.selectedProjectId}/curvas-config`);
            if (resp.ok) {
              const data = await resp.json();
              const configs = data.configs || [];
              configs.forEach(st => {
                st.level = Number(st.level) || (st.code ? st.code.split('.').length : 2);
              });
              this.editableCurvasConfigs = configs;
            }
          } catch (e) {
            console.error("Erro ao carregar configurações de curvas:", e);
          }
        },

        async saveCurvasConfig() {
          this.isSavingCurvasConfig = true;
          try {
            const resp = await fetch(`/api/replan/${this.selectedProjectId}/curvas-config`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ configs: this.editableCurvasConfigs })
            });
            if (!resp.ok) {
              alert("Erro ao salvar configurações de curvas.");
              return;
            }
            this.showConfigCurvasModal = false;
            await this.runSimulation();
          } catch (e) {
            console.error(e);
            alert("Erro ao salvar.");
          } finally {
            this.isSavingCurvasConfig = false;
          }
        },

        downloadCurvasTemplate() {
          window.location.href = `/api/replan/${this.selectedProjectId}/curvas-config/template`;
        },

        async uploadCurvasTemplate(event) {
          const file = event.target.files[0];
          if (!file) return;
          const formData = new FormData();
          formData.append("file", file);
          try {
            const resp = await fetch(`/api/replan/${this.selectedProjectId}/curvas-config/upload`, {
              method: "POST",
              body: formData
            });
            if (!resp.ok) {
              alert("Erro ao importar planilha de configurações.");
              return;
            }
            const data = await resp.json();
            const configs = data.configs || [];
            configs.forEach(st => {
              st.level = Number(st.level) || (st.code ? st.code.split('.').length : 2);
            });
            this.editableCurvasConfigs = configs;
            alert(data.message || "Configurações atualizadas!");
            await this.runSimulation();
          } catch (e) {
            console.error(e);
            alert("Erro ao enviar arquivo.");
          } finally {
            event.target.value = "";
          }
        },

        // --- Curvas Avançadas: Custo Projetado, Incorrido, Pagamentos & Realizado + Projeção ---

        openCurvasImportModal() {
          this.showCurvasImportModal = true;
          this.carregarCurvasDados();
          this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        openCurvasVinculosModal() {
          this.showCurvasVinculosModal = true;
          this.novoVinculoOrigem = '';
          this.novoVinculoDestino = '';
          this.carregarCurvasDados();
          this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        },

        downloadCurvasTemplateFile(type) {
          window.location.href = `/api/replan/${this.selectedProjectId}/curvas-templates/${type}`;
        },

        async handleFileUploadCurvas(event, type) {
          let file = null;
          if (event.target && event.target.files && event.target.files[0]) {
            file = event.target.files[0];
          } else if (event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0]) {
            file = event.dataTransfer.files[0];
          }
          if (!file) return;

          const endpointMap = {
            'custo_projetado': `/api/replan/${this.selectedProjectId}/curvas-importar-custo-projetado`,
            'incorrido': `/api/replan/${this.selectedProjectId}/curvas-importar-incorrido`,
            'conciliacao': `/api/replan/${this.selectedProjectId}/curvas-importar-pagamentos`
          };

          const url = endpointMap[type];
          if (!url) return;

          const formData = new FormData();
          formData.append("file", file);

          try {
            const resp = await fetch(url, { method: "POST", body: formData });
            if (!resp.ok) {
              const err = await resp.json().catch(() => ({}));
              alert(err.detail || "Erro ao importar planilha.");
              return;
            }
            const res = await resp.json();
            alert(res.message || "Planilha importada com sucesso!");
            await this.carregarCurvasDados();
            if (this.curvasSubView === 'realizado') {
              await this.carregarRealizadoProjecao();
            }
            await this.runSimulation();
          } catch (e) {
            console.error(e);
            alert("Erro ao enviar arquivo.");
          } finally {
            if (event.target && event.target.value) {
              event.target.value = "";
            }
          }
        },

        async carregarCurvasDados() {
          this.isLoadingCurvasDados = true;
          try {
            const resp = await fetch(`/api/replan/${this.selectedProjectId}/curvas-dados`);
            if (resp.ok) {
              this.curvasDados = await resp.json();
              if (this.curvasDados.parametros_obra) {
                this.curvasParamsObra = Object.assign({}, this.curvasParamsObra, this.curvasDados.parametros_obra);
              }
            }
          } catch (e) {
            console.error("Erro ao carregar curvas-dados:", e);
          } finally {
            this.isLoadingCurvasDados = false;
            this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
          }
        },

        async carregarRealizadoProjecao() {
          this.isLoadingRealizado = true;
          try {
            const corte = this.curvasCorte || '';
            const resp = await fetch(`/api/replan/${this.selectedProjectId}/curvas-realizado?corte=${encodeURIComponent(corte)}`);
            if (resp.ok) {
              this.curvasRealizadoData = await resp.json();
              this.$nextTick(() => {
                this.renderChartRealizadoProjecao();
                if (window.lucide) lucide.createIcons();
              });
            }
          } catch (e) {
            console.error("Erro ao carregar curvas-realizado:", e);
          } finally {
            this.isLoadingRealizado = false;
          }
        },

        async salvarNovoVinculo() {
          if (!this.novoVinculoOrigem.trim()) {
            alert("Informe o código de origem.");
            return;
          }
          try {
            const resp = await fetch(`/api/replan/${this.selectedProjectId}/curvas-vinculos`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                codigo_origem: this.novoVinculoOrigem.trim(),
                codigo_destino: this.novoVinculoDestino ? this.novoVinculoDestino.trim() : null,
                remover: false
              })
            });
            if (resp.ok) {
              this.novoVinculoOrigem = '';
              this.novoVinculoDestino = '';
              await this.carregarCurvasDados();
              if (this.curvasSubView === 'realizado') {
                await this.carregarRealizadoProjecao();
              }
            }
          } catch (e) {
            console.error(e);
          }
        },

        async vincularItemFora(origem, destino) {
          if (!origem) return;
          try {
            const resp = await fetch(`/api/replan/${this.selectedProjectId}/curvas-vinculos`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                codigo_origem: origem,
                codigo_destino: destino || null,
                remover: !destino
              })
            });
            if (resp.ok) {
              await this.carregarCurvasDados();
              if (this.curvasSubView === 'realizado') {
                await this.carregarRealizadoProjecao();
              }
            }
          } catch (e) {
            console.error(e);
          }
        },

        async desvincularItem(origem) {
          await this.vincularItemFora(origem, null);
        },

        async promptSalvarVersaoCurvas() {
          const nome = prompt("Nome para a versão congelada das curvas:", `Versão ${new Date().toLocaleDateString('pt-BR')}`);
          if (nome === null) return;
          try {
            const resp = await fetch(`/api/replan/${this.selectedProjectId}/curvas-versoes`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ nome: nome.trim() || undefined })
            });
            if (resp.ok) {
              alert("Versão das curvas salva com sucesso!");
            }
          } catch (e) {
            console.error(e);
          }
        },

        isNivel1Considerado(codigo) {
          const excl = this.curvasParamsObra?.niveis1_excluidos || [];
          return !excl.includes(String(codigo));
        },

        toggleNivel1Considerado(codigo) {
          const sCod = String(codigo);
          let excl = this.curvasParamsObra.niveis1_excluidos || [];
          if (excl.includes(sCod)) {
            excl = excl.filter(x => x !== sCod);
          } else {
            excl.push(sCod);
          }
          this.curvasParamsObra.niveis1_excluidos = excl;
        },

        getFilteredFluxos() {
          const etapas = this.curvasDados?.etapas || [];
          const q = (this.searchAnalitica || '').trim().toLowerCase();
          const tipoFiltro = this.filtroTipoAnalitica || 'TODOS';
          let allFluxos = [];
          etapas.forEach(et => {
            (et.fluxos || []).forEach(fl => {
              allFluxos.push(Object.assign({}, fl, { codigo_etapa: et.codigo_etapa, nome: et.nome }));
            });
          });
          if (tipoFiltro !== 'TODOS') {
            allFluxos = allFluxos.filter(fl => fl.tipo === tipoFiltro);
          }
          if (q) {
            allFluxos = allFluxos.filter(fl => 
              (fl.codigo_etapa && fl.codigo_etapa.toLowerCase().includes(q)) ||
              (fl.nome && fl.nome.toLowerCase().includes(q)) ||
              (fl.comp && fl.comp.toLowerCase().includes(q)) ||
              (fl.fin && fl.fin.toLowerCase().includes(q))
            );
          }
          return allFluxos;
        },

        renderCurvasChart() {
          const canvas = document.getElementById("curvasTripleChartCanvas");
          if (!canvas) return;
          const existing = Chart.getChart(canvas);
          if (existing) {
            try { existing.destroy(); } catch (e) {}
          }
          if (this.tripleChartInstance) {
            try { this.tripleChartInstance.destroy(); } catch (e) {}
            this.tripleChartInstance = null;
          }

          const sComp = this.curvasDados?.s_curves_comparison || this.replanResult?.s_curves_comparison;
          if (!sComp) return;

          const labels = sComp.labels || [];
          const compData = sComp.comp_accum_pcts || [];
          const finData = sComp.fin_accum_pcts || [];
          const sc = this.replanResult?.s_curve;
          const fisicoData = sc?.replan_accum_pcts || [];

          this.tripleChartInstance = new Chart(canvas, {
            type: "line",
            data: {
              labels: labels,
              datasets: [
                {
                  label: "Físico Produzido (%)",
                  data: fisicoData,
                  borderColor: "#6366f1",
                  borderWidth: 2,
                  pointRadius: 2.5,
                  tension: 0.2
                },
                {
                  label: "Competência Contábil (%)",
                  data: compData,
                  borderColor: "#2563eb",
                  borderWidth: 2.5,
                  pointRadius: 3,
                  tension: 0.2
                },
                {
                  label: "Financeiro / Desembolso (%)",
                  data: finData,
                  borderColor: "#0d9488",
                  borderWidth: 2.5,
                  pointRadius: 3,
                  tension: 0.2
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              interaction: { mode: "index", intersect: false },
              scales: {
                y: {
                  beginAtZero: true,
                  max: 100,
                  ticks: { callback: v => v + "%" },
                  grid: { color: "#f1f5f9" }
                },
                x: {
                  grid: { display: false }
                }
              },
              plugins: {
                legend: { position: "top" }
              }
            }
          });
        },

        renderChartRealizadoProjecao() {
          const canvas = document.getElementById("chartRealizadoProjecaoCanvas");
          if (!canvas) return;
          const existing = Chart.getChart(canvas);
          if (existing) {
            try { existing.destroy(); } catch (e) {}
          }
          if (this.realizadoProjecaoChartInstance) {
            try { this.realizadoProjecaoChartInstance.destroy(); } catch (e) {}
            this.realizadoProjecaoChartInstance = null;
          }

          const series = this.curvasRealizadoData?.seriesMensal || [];
          if (!series.length) return;

          const labels = series.map(s => s.mes);
          const corte = this.curvasRealizadoData?.corte;

          let realCompAcc = 0;
          let teoricoCompAcc = 0;

          const compRealData = [];
          const compProjData = [];
          const teoricoData = [];

          series.forEach(s => {
            teoricoCompAcc += (s.teoricoCompetenciaMensal || 0);
            teoricoData.push(teoricoCompAcc);

            if (s.mes <= corte) {
              realCompAcc += (s.competenciaMensal || 0);
              compRealData.push(realCompAcc);
              compProjData.push(null);
            } else {
              if (compRealData[compRealData.length - 1] !== null && compProjData[compProjData.length - 1] === null) {
                compProjData[compProjData.length - 1] = realCompAcc;
              }
              realCompAcc += (s.competenciaMensal || 0);
              compRealData.push(null);
              compProjData.push(realCompAcc);
            }
          });

          this.realizadoProjecaoChartInstance = new Chart(canvas, {
            type: "line",
            data: {
              labels: labels,
              datasets: [
                {
                  label: "Incorrido até Corte (R$)",
                  data: compRealData,
                  borderColor: "#2563eb",
                  borderWidth: 3,
                  pointRadius: 3,
                  tension: 0.2
                },
                {
                  label: "Projeção Futura (R$)",
                  data: compProjData,
                  borderColor: "#2563eb",
                  borderDash: [6, 4],
                  borderWidth: 2.5,
                  pointRadius: 3,
                  tension: 0.2
                },
                {
                  label: "Teórico Base (R$)",
                  data: teoricoData,
                  borderColor: "#94a3b8",
                  borderWidth: 1.5,
                  pointRadius: 2,
                  tension: 0.2
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              interaction: { mode: "index", intersect: false },
              scales: {
                y: {
                  beginAtZero: true,
                  ticks: { callback: v => "R$ " + (v / 1000).toFixed(0) + "k" },
                  grid: { color: "#f1f5f9" }
                },
                x: { grid: { display: false } }
              },
              plugins: {
                legend: { position: "top" }
              }
            }
          });
        },





        get filteredBudgetRows() {
          const rows = (this.replanResult?.tab_orcamento || []).filter(r => r.level > 1);
          if (!this.searchBudget.trim()) return rows;
          const q = this.searchBudget.toLowerCase();
          return rows.filter(r => r.code.toLowerCase().includes(q) || r.description.toLowerCase().includes(q));
        },

        get filteredDistRows() {
          const allRows = this.replanResult?.tab_distribuicao || [];
          let rows = allRows;

          if (this.searchDist.trim()) {
            const q = this.searchDist.toLowerCase();
            rows = rows.filter(r => r.code.toLowerCase().includes(q) || r.description.toLowerCase().includes(q));
          }

          if (this.selectedFilterMonths.length > 0) {
            const months = this.selectedFilterMonths;
            const matchingL6Codes = new Set();
            const matchingParentCodes = new Set();

            for (const r of allRows) {
              if (r.level === 6) {
                let hasVal = false;
                for (const m of months) {
                  if (this.hasDistCycleVal(r, m)) {
                    hasVal = true;
                    break;
                  }
                }
                if (hasVal) {
                  matchingL6Codes.add(r.code);
                  if (r.parent_code) matchingParentCodes.add(r.parent_code);
                }
              } else if (r.level === 5) {
                let hasVal = false;
                for (const m of months) {
                  if (this.hasDistCycleVal(r, m)) {
                    hasVal = true;
                    break;
                  }
                }
                if (hasVal) {
                  matchingParentCodes.add(r.code);
                }
              }
            }

            rows = rows.filter(r => {
              if (r.level === 5) return matchingParentCodes.has(r.code);
              if (r.level === 6) return matchingL6Codes.has(r.code);
              return false;
            });
          }

          return rows;
        },

        get paginatedDistRows() {
          const filtered = this.filteredDistRows;
          return filtered.slice(0, this.distPage * this.distPageSize);
        },

        get filteredCronoTasks() {
          let tasks = [...(this.replanResult?.tab_cronograma?.tasks || [])];
          if (this.searchCrono.trim()) {
            const q = this.searchCrono.toLowerCase();
            tasks = tasks.filter(t => 
              t.name.toLowerCase().includes(q) || 
              (t.lot && t.lot.toLowerCase().includes(q)) ||
              (t.id && String(t.id).includes(q)) ||
              (t.predecessors && t.predecessors.some(p => p.toLowerCase().includes(q)))
            );
          }
          tasks.sort((a, b) => {
            const idA = parseInt(a.id, 10) || 0;
            const idB = parseInt(b.id, 10) || 0;
            return idA - idB;
          });
          return tasks;
        },

        get pagedCronoTasks() {
          const filtered = this.filteredCronoTasks;
          return filtered.slice(0, this.cronoPage * this.cronoPageSize);
        },

        toggleExpandReplanL5(code) {
          this.expandedReplanL5 = Object.assign({}, this.expandedReplanL5, { [code]: !this.expandedReplanL5[code] });
        },

        toggleAllReplanL6() {
          if (this.isAnyReplanL6Expanded()) {
            this.expandedReplanL5 = {};
            if (this.levelFilterReplan === 0) this.levelFilterReplan = 5;
          } else {
            const map = {};
            const all = this.replanResult?.tab_replanejado || [];
            for (let i = 0; i < all.length; i++) {
              if (all[i].level === 5 && all[i].code) map[all[i].code] = true;
            }
            this.expandedReplanL5 = map;
          }
        },

        isAnyReplanL6Expanded() {
          if (this.levelFilterReplan === 0) return true;
          return Object.values(this.expandedReplanL5 || {}).some(Boolean);
        },

        getReplanL6Count(code) {
          if (!code) return 0;
          return (this._replanChildrenByParent && this._replanChildrenByParent[code]) ? this._replanChildrenByParent[code].length : 0;
        },

        getDistCellValue(row, cycleNum) {
          if (!row) return "-";
          const cStr = String(cycleNum);
          const val = (row.cycle_vals && row.cycle_vals[cStr]) || 0;
          if (this.distViewMode === 'pct') {
            const pctObra = (row.cycle_pcts_obra && row.cycle_pcts_obra[cStr]) || 0;
            if (pctObra > 0) return pctObra.toFixed(2) + '%';
            const tot = this.replanResult?.total_budget || 1.0;
            return val > 0 ? ((val / tot) * 100).toFixed(2) + '%' : '-';
          } else if (this.distViewMode === 'pct_service') {
            const pctServ = (row.cycle_pcts && row.cycle_pcts[cStr]) || 0;
            if (pctServ > 0) return pctServ.toFixed(2) + '%';
            const alloc = row.allocated_val || 0;
            return (alloc > 0 && val > 0) ? ((val / alloc) * 100).toFixed(2) + '%' : '-';
          } else {
            return val > 0 ? this.formatCurrency(val) : '-';
          }
        },

        get filteredReplanRows() {
          const allRows = (this.replanResult?.tab_replanejado || []).filter(r => r.level > 1);
          let rows = allRows;
          if (this.levelFilterReplan > 0 && this.levelFilterReplan < 5) {
            rows = rows.filter(r => r.level <= this.levelFilterReplan);
          } else if (this.levelFilterReplan === 5) {
            // Level 5 mode: show Level 2-5, plus Level 6 only for expanded Level 5s
            rows = rows.filter(r => r.level <= 5 || (r.level === 6 && this.expandedReplanL5[r.parent_code]));
          }
          if (this.searchReplan.trim()) {
            const q = this.searchReplan.toLowerCase();
            rows = rows.filter(r => r.code.toLowerCase().includes(q) || r.description.toLowerCase().includes(q));
          }
          if (this.selectedFilterMonths.length > 0) {
            const months = this.selectedFilterMonths;
            const matchingCodes = new Set();
            for (const r of allRows) {
              let hasVal = false;
              for (const m of months) {
                if (this.hasReplanCycleVal(r, m)) {
                  hasVal = true;
                  break;
                }
              }
              if (hasVal) {
                matchingCodes.add(r.code);
                const parts = r.code.split('.');
                for (let i = 1; i < parts.length; i++) {
                  matchingCodes.add(parts.slice(0, i).join('.'));
                }
              }
            }
            rows = rows.filter(r => matchingCodes.has(r.code));
          }
          return rows;
        },

        get paginatedReplanRows() {
          const filtered = this.filteredReplanRows;
          return filtered.slice(0, this.replanPage * this.replanPageSize);
        },

        setReplanPageSize(size) {
          if (size === 'all') {
            this.replanPage = 1;
            this.replanPageSize = Math.max(this.filteredReplanRows.length, 1000);
          } else {
            const curLoaded = this.replanPage * this.replanPageSize;
            this.replanPageSize = Number(size);
            this.replanPage = Math.max(1, Math.ceil(curLoaded / this.replanPageSize));
          }
          this.$nextTick(() => {
            if (window.lucide && this.$refs.replanContainer) {
              try { lucide.createIcons({ root: this.$refs.replanContainer }); } catch (_) {}
            }
          });
        },

        loadMoreReplanRows(qty = 1) {
          this.replanPage += qty;
          this.$nextTick(() => {
            if (window.lucide && this.$refs.replanContainer) {
              try { lucide.createIcons({ root: this.$refs.replanContainer }); } catch (_) {}
            }
          });
        },

        loadAllReplanRows() {
          if (this.replanPageSize < this.filteredReplanRows.length) {
            this.replanPageSize = Math.max(this.filteredReplanRows.length, 1000);
          }
          this.replanPage = 1;
          this.$nextTick(() => {
            if (window.lucide && this.$refs.replanContainer) {
              try { lucide.createIcons({ root: this.$refs.replanContainer }); } catch (_) {}
            }
          });
        },

        scrollToReplanBottom() {
          this.loadAllReplanRows();
          this.$nextTick(() => {
            const container = this.$refs.replanContainer;
            if (container) {
              container.scrollTop = container.scrollHeight;
              setTimeout(() => {
                if (container) {
                  container.scrollTop = container.scrollHeight;
                }
              }, 120);
            }
          });
        },

        scrollToReplanTop() {
          const container = this.$refs.replanContainer;
          if (container) {
            container.scrollTo({ top: 0, behavior: 'smooth' });
          }
        },

        setMedPageSize(size) {
          if (size === 'all') {
            this.medPage = 1;
            this.medPageSize = Math.max(this.displayMedRows.length, 500);
          } else {
            const curLoaded = this.medPage * this.medPageSize;
            this.medPageSize = Number(size);
            this.medPage = Math.max(1, Math.ceil(curLoaded / this.medPageSize));
          }
          this.$nextTick(() => {
            if (window.lucide && this.$refs.medContainer) {
              try { lucide.createIcons({ root: this.$refs.medContainer }); } catch (_) {}
            }
          });
        },

        loadMoreMedRows(qty = 1) {
          this.medPage += qty;
          this.$nextTick(() => {
            if (window.lucide && this.$refs.medContainer) {
              try { lucide.createIcons({ root: this.$refs.medContainer }); } catch (_) {}
            }
          });
        },

        loadAllMedRows() {
          if (this.medPageSize < this.displayMedRows.length) {
            this.medPageSize = Math.max(this.displayMedRows.length, 500);
          }
          this.medPage = 1;
          this.$nextTick(() => {
            if (window.lucide && this.$refs.medContainer) {
              try { lucide.createIcons({ root: this.$refs.medContainer }); } catch (_) {}
            }
          });
        },

        scrollToMedBottom() {
          this.loadAllMedRows();
          this.$nextTick(() => {
            const container = this.$refs.medContainer;
            if (container) {
              container.scrollTop = container.scrollHeight;
              setTimeout(() => {
                if (container) {
                  container.scrollTop = container.scrollHeight;
                }
              }, 120);
            }
          });
        },

        scrollToMedTop() {
          const container = this.$refs.medContainer;
          if (container) {
            container.scrollTo({ top: 0, behavior: 'smooth' });
          }
        },

        // --- Upload Schedule ---
        async uploadScheduleFile() {
          if (!this.selectedScheduleFile) return;
          this.isUploading = true;
          try {
            const formData = new FormData();
            formData.append("project_id", this.selectedProjectId);
            formData.append("version_name", this.importVersionName || this.selectedScheduleFile.name);
            formData.append("file", this.selectedScheduleFile);

            const resp = await fetch("/api/replan/import-schedule", {
              method: "POST",
              body: formData
            });

            if (!resp.ok) {
              const err = await resp.json();
              alert(this.formatErrorDetail(err, "Erro ao importar cronograma."));
              return;
            }

            const data = await resp.json();
            alert(`Cronograma importado com sucesso! ${data.tasks_count} atividades processadas.`);
            this.showImportModal = false;
            await this.loadVersions();
            this.runSimulation();
          } catch (e) {
            console.error(e);
            alert("Erro ao enviar arquivo.");
          } finally {
            this.isUploading = false;
          }
        },

        downloadTemplate() {
          window.location.href = "/api/projects/template";
        },

        async submitUploadProject() {
          if (!this.uploadProjectName || !this.uploadProjectName.trim()) {
            alert("Por favor, informe o nome da obra.");
            return;
          }
          const fileInput = document.getElementById("uploadProjectFileInput");
          if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            alert("Por favor, selecione a planilha Excel (.xlsx) da obra.");
            return;
          }
          const scheduleInput = document.getElementById("uploadProjectScheduleInput");
          
          this.isUploadingProject = true;
          this.uploadError = null;
          try {
            const formData = new FormData();
            formData.append("project_name", this.uploadProjectName.trim());
            formData.append("file", fileInput.files[0]);
            if (scheduleInput && scheduleInput.files && scheduleInput.files.length > 0) {
              formData.append("schedule_file", scheduleInput.files[0]);
            }
            
            const resp = await fetch("/api/projects/upload", {
              method: "POST",
              body: formData
            });
            
            if (!resp.ok) {
              const err = await resp.json();
              throw new Error(err.detail || "Erro ao fazer upload da obra.");
            }
            
            const data = await resp.json();
            await this.loadProjects();
            this.selectedProjectId = data.project_id;
            this.showUploadModal = false;
            this.uploadProjectName = "";
            if (fileInput) fileInput.value = "";
            if (scheduleInput) scheduleInput.value = "";
            this.onProjectSelectChange();
            alert(`Obra "${data.project_name}" importada com sucesso!\n${data.budget_items_count} etapas orçamentárias e ${data.tasks_count} atividades no cronograma.`);
          } catch (e) {
            console.error(e);
            this.uploadError = e.message;
            alert("Erro na importação: " + e.message);
          } finally {
            this.isUploadingProject = false;
          }
        },

        async deleteProject(pid, pname) {
          if (!confirm(`Tem certeza que deseja excluir a obra "${pname}"? Esta ação removerá os arquivos associados.`)) {
            return;
          }
          try {
            const resp = await fetch(`/api/projects/${pid}`, { method: "DELETE" });
            if (!resp.ok) {
              const err = await resp.json();
              alert(this.formatErrorDetail(err, "Não foi possível excluir a obra."));
              return;
            }
            await this.loadProjects();
            if (this.selectedProjectId === pid && this.projects.length > 0) {
              this.selectedProjectId = this.projects[0].id;
              this.onProjectSelectChange();
            }
          } catch (e) {
            console.error(e);
            alert("Erro ao excluir obra.");
          }
        },

        // --- Export ---
        get currentTabLabel() {
          const map = {
            'dashboard': 'Resumo Curva S',
            'orcamento': 'Orçamento',
            'cronograma': 'Cronograma',
            'distribuicao': 'Distribuição (' + (this.distViewMode === 'pct' ? '% Obra' : (this.distViewMode === 'pct_service' ? 'Peso Serviço' : 'R$')) + ')',
            'fisico_financeiro': 'FF Previsto (' + (this.ffViewMode === 'pct' ? '%' : 'R$') + ')',
            'medicao': 'Medição da Obra',
            'replanejado': 'Replanejado Saldo (' + (this.ffRepViewMode === 'pct' ? '% Obra' : (this.ffRepViewMode === 'pct_service' ? '% Serviço' : (this.ffRepViewMode === 'pct_etapa' ? '% Etapa' : 'R$'))) + ')',
            'ff_replanejado': 'FF Replanejado (' + (this.ffRepViewMode === 'pct' ? '%' : 'R$') + ')',
            'competencia': 'Competência Contábil (' + (this.compViewMode === 'pct' ? '%' : 'R$') + ')',
            'financeiro': 'Curva Financeira (' + (this.finViewMode === 'pct' ? '%' : 'R$') + ')'
          };
          return map[this.activeTab] || 'Tela Atual';
        },

        async exportExcel(target = 'current') {
          if (this.isExporting) return;
          this.isExporting = true;
          this.showExportMenu = false;
          try {
            const payload = {
              project_id: this.selectedProjectId,
              cycle_start_day: this.cycleStartDay,
              cycle_end_day: this.computedCycleEndDay,
              cutoff_med_num: this.cutoffMedNum,
              version_id: this.selectedVersionId,
              custom_monthly_medicao: this.customMonthlyL5,
              custom_monthly_medicao_l6: this.customMonthlyL6,
              custom_schedule_overrides: this.customScheduleOverrides,
              custom_links_by_l5: (this.customLinksByL5 && Object.keys(this.customLinksByL5).length > 0) ? this.customLinksByL5 : null,
              custom_weights: (this.customReplanWeights && Object.keys(this.customReplanWeights).length > 0) ? this.customReplanWeights : null,
              export_target: target,
              active_tab: this.activeTab,
              dist_view_mode: this.distViewMode || 'val',
              ff_rep_view_mode: this.ffRepViewMode || 'val',
              ff_view_mode: this.ffViewMode || 'val',
              replan_saldo_in_pct: !!this.replanSaldoInPct
            };

            const resp = await fetch("/api/replan/export", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload)
            });

            if (!resp.ok) {
              alert("Erro ao exportar planilha.");
              return;
            }

            let downloadFilename = `Replanejado_${this.selectedProjectId.toUpperCase()}_M${this.cutoffMedNum}.xlsx`;
            const disposition = resp.headers.get("Content-Disposition");
            if (disposition && disposition.includes("filename=")) {
              const match = disposition.match(/filename="?([^"]+)"?/);
              if (match && match[1]) {
                downloadFilename = match[1];
              }
            }

            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = downloadFilename;
            document.body.appendChild(a);
            a.click();
            a.remove();
          } catch (e) {
            console.error(e);
            alert("Falha no download da planilha.");
          } finally {
            this.isExporting = false;
          }
        },

        // --- Link Management (Nível 6) ---
        get selectedTaskIsGroup() {
          const t = (this.replanResult?.tab_cronograma?.tasks || []).find(tk => String(tk.id) === String(this.selectedLinkTaskId));
          return !!t?.is_summary;
        },

        get filteredLinkTasks() {
          let tasks = [...(this.replanResult?.tab_cronograma?.tasks || [])];
          if (this.linkTypeFilter === "groups") {
            tasks = tasks.filter(t => t.is_summary);
          } else if (this.linkTypeFilter === "tasks") {
            tasks = tasks.filter(t => !t.is_summary);
          }
          if (this.linkSearch && this.linkSearch.trim()) {
            const q = this.linkSearch.toLowerCase();
            tasks = tasks.filter(t => 
              (t.name && t.name.toLowerCase().includes(q)) ||
              (t.id && String(t.id).includes(q)) ||
              (t.wbs && t.wbs.toLowerCase().includes(q)) ||
              (t.lot && t.lot.toLowerCase().includes(q))
            );
          }
          return tasks;
        },

        hasCustomLinks() {
          return this.hasCustomLinksFlag || (this.customLinksByL5 && Object.keys(this.customLinksByL5).length > 0);
        },

        openLinkModal(l5Code, linkIndex) {
          this.linkTargetL5Code = l5Code;
          this.linkModalIndex = linkIndex;
          
          const targetL5 = (this.replanResult?.tab_orcamento || []).find(i => i.code === l5Code) || 
                           (this.replanResult?.tab_distribuicao || []).find(i => i.code === l5Code);
          this.linkTargetL5Desc = targetL5 ? targetL5.description : '';

          if (linkIndex >= 0) {
            const l6 = (this.replanResult?.tab_distribuicao || []).find(r => r.parent_code === l5Code && r.link_index === linkIndex);
            this.linkCurrentTaskName = l6 ? l6.description : '';
            this.selectedLinkTaskId = l6 && l6.task_id ? String(l6.task_id) : '';
          } else {
            this.linkCurrentTaskName = '';
            this.selectedLinkTaskId = '';
          }
          
          this.linkSearch = '';
          this.linkTypeFilter = 'all';
          this.selectedGroupLeaves = [];
          this.showLinkModal = true;
          this.$nextTick(() => { lucide.createIcons(); });
        },

        async onLinkTaskSelected(task) {
          this.selectedLinkTaskId = String(task.id);
          this.selectedGroupLeaves = [];
          if (task.is_summary) {
            const allTasks = this.replanResult?.tab_cronograma?.tasks || [];
            const taskWbs = task.wbs || task.outline || '';
            let leaves = [];
            if (taskWbs) {
              const prefix = taskWbs + '.';
              leaves = allTasks.filter(t => (t.wbs || t.outline || '').startsWith(prefix) && !t.is_summary);
            }
            if (!leaves.length) {
              leaves = allTasks.filter(t => String(t.parent_id) === String(task.id) && !t.is_summary);
            }
            this.selectedGroupLeaves = leaves;

            try {
              const resp = await fetch(`/api/replan/expand-group?project_id=${this.selectedProjectId}&group_id=${task.id}&version_id=${this.selectedVersionId || ''}`);
              if (resp.ok) {
                const data = await resp.json();
                if (data.leaf_tasks && data.leaf_tasks.length > 0) {
                  this.selectedGroupLeaves = data.leaf_tasks;
                }
              }
            } catch (e) {
              console.warn("expand-group fallback:", e);
            }
          }
          this.$nextTick(() => { lucide.createIcons(); });
        },

        async confirmLinkModal() {
          if (!this.selectedLinkTaskId || !this.linkTargetL5Code) return;
          const task = (this.replanResult?.tab_cronograma?.tasks || []).find(t => String(t.id) === String(this.selectedLinkTaskId));
          if (!task) return;

          if (!this.customLinksByL5[this.linkTargetL5Code]) {
            const existingLinks = (this.replanResult?.links_by_l5 && this.replanResult.links_by_l5[this.linkTargetL5Code]) ? 
                                  JSON.parse(JSON.stringify(this.replanResult.links_by_l5[this.linkTargetL5Code])) : [];
            this.customLinksByL5[this.linkTargetL5Code] = existingLinks;
          }

          const currentList = this.customLinksByL5[this.linkTargetL5Code];

          if (task.is_summary) {
            let leaves = this.selectedGroupLeaves;
            if (!leaves || !leaves.length) {
              alert("Este grupo não possui atividades executáveis filhas no cronograma.");
              return;
            }
            const newLinkItems = leaves.map(l => ({
              wbs_code: this.linkTargetL5Code,
              task_name: l.name,
              duration: l.duration || 1.0
            }));

            if (this.linkModalIndex >= 0 && this.linkModalIndex < currentList.length) {
              currentList.splice(this.linkModalIndex, 1, ...newLinkItems);
            } else {
              currentList.push(...newLinkItems);
            }
          } else {
            const newLinkItem = {
              wbs_code: this.linkTargetL5Code,
              task_name: task.name,
              duration: task.duration || 1.0
            };
            if (this.linkModalIndex >= 0 && this.linkModalIndex < currentList.length) {
              currentList[this.linkModalIndex] = newLinkItem;
            } else {
              currentList.push(newLinkItem);
            }
          }

          this.hasCustomLinksFlag = true;
          this.showLinkModal = false;

          try {
            await fetch("/api/replan/save-links", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                project_id: this.selectedProjectId,
                links_by_l5: this.customLinksByL5
              })
            });
          } catch (e) {
            console.error("Erro ao salvar links:", e);
          }

          await this.runSimulation();
        },

        async removeLink(l5Code, linkIndex) {
          if (!confirm("Deseja realmente remover este vínculo do cronograma?")) return;
          if (!this.customLinksByL5[l5Code]) {
            const existingLinks = (this.replanResult?.links_by_l5 && this.replanResult.links_by_l5[l5Code]) ? 
                                  JSON.parse(JSON.stringify(this.replanResult.links_by_l5[l5Code])) : [];
            this.customLinksByL5[l5Code] = existingLinks;
          }

          const currentList = this.customLinksByL5[l5Code];
          if (linkIndex >= 0 && linkIndex < currentList.length) {
            currentList.splice(linkIndex, 1);
          }

          this.hasCustomLinksFlag = true;

          try {
            await fetch("/api/replan/save-links", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                project_id: this.selectedProjectId,
                links_by_l5: this.customLinksByL5
              })
            });
          } catch (e) {
            console.error("Erro ao salvar links:", e);
          }

          await this.runSimulation();
        },

        async resetLinks() {
          if (!confirm("Deseja restaurar todos os vínculos da distribuição para os padrões originais da planilha?")) return;
          try {
            await fetch("/api/replan/reset-links", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ project_id: this.selectedProjectId })
            });
          } catch (e) {
            console.error("Erro ao resetar links:", e);
          }
          await this.loadVersions();
          await this.runSimulation();
        },

        formatCurrency(val) {
          if (val === undefined || val === null || isNaN(val) || val === 0) return val === 0 ? "R$ 0,00" : "-";
          return "R$ " + brlFormatter.format(val);
        },

        formatDateBr(val) {
          if (!val || val === '-') return '-';
          const parts = val.split('-');
          if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
          return val;
        },

        formatErrorDetail(err, fallback = "Ocorreu um erro.") {
          if (!err) return fallback;
          const detail = err.detail !== undefined ? err.detail : err;
          if (typeof detail === "string") return detail;
          if (Array.isArray(detail)) {
            return detail.map(d => (d.loc ? d.loc.slice(1).join(".") + ": " : "") + (d.msg || JSON.stringify(d))).join("\n");
          }
          if (typeof detail === "object") {
            try { return JSON.stringify(detail); } catch (_) {}
          }
          return String(detail || fallback);
        }
      };
    }
