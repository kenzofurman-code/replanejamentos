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
        levelFilterFFRep: 3,    // 2, 3, 4, 0
        levelFilterReplan: 0,   // 0 (all), 2, 3, 4, 5
        levelFilterComp: 3,     // 2, 3, 4, 0
        levelFilterFin: 3,      // 2, 3, 4, 0

        ffViewMode: "pct",      // 'pct' | 'val'
        ffRepViewMode: "pct",   // 'pct' | 'val'
        distViewMode: "pct",    // 'pct' (% Obra) | 'pct_service' (% Serviço) | 'val' (R$)
        compViewMode: "val",    // 'val' | 'mat' | 'mo' | 'pct'
        finViewMode: "val",     // 'val' | 'mat' | 'mo' | 'pct'

        showConfigCurvasModal: false,
        editableCurvasConfigs: [],
        isSavingCurvasConfig: false,
        comparisonChartInstance: null,

        // Pagination
        distPage: 1,
        distPageSize: 50,   // rolagem infinita: carrega +50 linhas ao chegar no fim
        cronoPage: 1,
        cronoPageSize: 50,
        replanPage: 1,
        replanPageSize: 50,
        medPage: 1,
        medPageSize: 50,

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
          this.selectedVersionId = this.versions.cronograma?.active || null;
          this.customMonthlyL5 = JSON.parse(JSON.stringify(med.monthly_l5 || {}));
          this.customMonthlyL6 = JSON.parse(JSON.stringify(med.monthly_l6 || {}));
          this.customScheduleOverrides = JSON.parse(JSON.stringify(crono.schedule_overrides || {}));
          this.customLinksByL5 = JSON.parse(JSON.stringify(dist.links_by_l5 || {}));
          this.hasCustomLinksFlag = !!dist.links_by_l5;
          this.savedEditsJson = {
            medicao: JSON.stringify(this.medicaoEdits()),
            cronograma: JSON.stringify(this.cronogramaEdits())
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

        async persistEdits() {
          // Grava na versão ativa só o que mudou desde o último salvamento
          if (!this.selectedProjectId) return;
          const pending = { medicao: this.medicaoEdits(), cronograma: this.cronogramaEdits() };
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
              alert(err.detail || "Erro ao ativar versão.");
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
              alert(err.detail || "Erro ao importar versão.");
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

        // Rolagem infinita: quando o marcador no fim da tabela aparece, carrega mais uma página
        observeMore(el, pageKey, totalFn) {
          const io = new IntersectionObserver((entries) => {
            if (entries.some(e => e.isIntersecting) && this[pageKey] * 50 < totalFn()) {
              this[pageKey]++;
              this.$nextTick(() => lucide.createIcons());
            }
          }, { rootMargin: "300px" });
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
          this.$nextTick(() => {
            lucide.createIcons();
            if (tab === 'dashboard') {
              this.renderCurvaS();
            } else if (tab === 'financeiro') {
              this.renderComparisonChart();
            }
          });
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
              custom_links_by_l5: (this.customLinksByL5 && Object.keys(this.customLinksByL5).length > 0) ? this.customLinksByL5 : null
            };

            const resp = await fetch("/api/replan/simulate", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload)
            });

            if (!resp.ok) {
              const err = await resp.json();
              alert(err.detail || "Erro ao simular replanejamento.");
              return;
            }

            this.replanResult = await resp.json();
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

            this.$nextTick(() => {
              this.renderCurvaS();
              if (this.activeTab === 'financeiro') {
                this.renderComparisonChart();
              }
              lucide.createIcons();
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
          for (const row of filtered) {
            if (row.level === 1) continue;
            out.push({ ...row, isL6: false, _rowKey: row.code });
            if (row.level === 5 && (this.expandedL5[row.code] || this.selectedFilterMonths.length > 0) && row.tasks_l6 && row.tasks_l6.length > 0) {
              for (const t of row.tasks_l6) {
                if (this.selectedFilterMonths.length > 0) {
                  let tHasVal = false;
                  for (const m of this.selectedFilterMonths) {
                    if (this.getL6MonthPct(row.code, t.task_name, m) > 0.0001) {
                      tHasVal = true;
                      break;
                    }
                  }
                  if (!tHasVal) continue;
                }
                out.push({
                  isL6: true,
                  _rowKey: row.code + '_' + t.task_name,
                  parent_code: row.code,
                  task_name: t.task_name,
                  duration: t.duration,
                  weight_pct: t.weight_pct,
                  measured_pct: t.measured_pct,
                  monthly_measurements: t.monthly_measurements || {}
                });
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
          if (this.customMonthlyL5[code] && this.customMonthlyL5[code][medNum] !== undefined) {
            return this.customMonthlyL5[code][medNum];
          }
          if (typeof rowOrCode === 'object' && rowOrCode.monthly_map && rowOrCode.monthly_map[String(medNum)] !== undefined) {
            return rowOrCode.monthly_map[String(medNum)];
          }
          const row = (typeof rowOrCode === 'object') ? rowOrCode : this.replanResult?.tab_medicao?.find(r => r.code === code);
          if (row?.monthly_map && row.monthly_map[String(medNum)] !== undefined) {
            return row.monthly_map[String(medNum)];
          }
          const col = row?.monthly_measurements?.find(m => m.med_num === medNum);
          return col ? col.realizado_pct : 0.0;
        },

        getL6MonthPct(rowOrParentCode, taskNameOrMedNum, medNumMaybe) {
          let parentCode, taskName, medNum;
          if (typeof rowOrParentCode === 'object') {
            parentCode = rowOrParentCode.parent_code;
            taskName = rowOrParentCode.task_name;
            medNum = taskNameOrMedNum;
            if (this.customMonthlyL6[parentCode] && 
                this.customMonthlyL6[parentCode][taskName] && 
                this.customMonthlyL6[parentCode][taskName][medNum] !== undefined) {
              return this.customMonthlyL6[parentCode][taskName][medNum];
            }
            if (rowOrParentCode.monthly_measurements && rowOrParentCode.monthly_measurements[String(medNum)] !== undefined) {
              return rowOrParentCode.monthly_measurements[String(medNum)];
            }
          } else {
            parentCode = rowOrParentCode;
            taskName = taskNameOrMedNum;
            medNum = medNumMaybe;
            if (this.customMonthlyL6[parentCode] && 
                this.customMonthlyL6[parentCode][taskName] && 
                this.customMonthlyL6[parentCode][taskName][medNum] !== undefined) {
              return this.customMonthlyL6[parentCode][taskName][medNum];
            }
            const row = this.replanResult?.tab_medicao?.find(r => r.code === parentCode);
            const t = row?.tasks_l6?.find(tk => tk.task_name === taskName);
            if (t?.monthly_measurements) {
              return t.monthly_measurements[String(medNum)] || 0.0;
            }
          }
          return 0.0;
        },

        getRollupMonthPct(row, medNum) {
          if (row.monthly_map && row.monthly_map[String(medNum)] !== undefined) {
            const v = row.monthly_map[String(medNum)];
            return v > 0 ? v.toFixed(2) + '%' : '-';
          }
          const col = row.monthly_measurements?.find(m => m.med_num === medNum);
          return col && col.realizado_pct > 0 ? col.realizado_pct.toFixed(2) + '%' : '-';
        },

        onMonthInputL5(code, medNum, val) {
          const num = Math.min(100, Math.max(0, parseFloat(val) || 0.0));
          if (!this.customMonthlyL5[code]) {
            this.customMonthlyL5[code] = {};
          }
          this.customMonthlyL5[code][medNum] = num;
          this.queueSaveMedicao();
        },

        onMonthInputL6(parentCode, taskName, medNum, val) {
          const num = Math.min(100, Math.max(0, parseFloat(val) || 0.0));
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
            await this.runSimulation();
            this.showTaskDrawer = false;
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

        openConfigCurvasModal() {
          if (this.replanResult?.stage_configs && this.replanResult.stage_configs.length > 0) {
            this.editableCurvasConfigs = JSON.parse(JSON.stringify(this.replanResult.stage_configs));
          } else {
            this.fetchCurvasConfig();
          }
          this.showConfigCurvasModal = true;
          this.$nextTick(() => lucide.createIcons());
        },

        async fetchCurvasConfig() {
          try {
            const resp = await fetch(`/api/replan/${this.selectedProjectId}/curvas-config`);
            if (resp.ok) {
              const data = await resp.json();
              this.editableCurvasConfigs = data.configs || [];
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
            this.editableCurvasConfigs = data.configs || [];
            alert(data.message || "Configurações atualizadas!");
            await this.runSimulation();
          } catch (e) {
            console.error(e);
            alert("Erro ao enviar arquivo.");
          } finally {
            event.target.value = "";
          }
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

        get filteredReplanRows() {
          let allRows = (this.replanResult?.tab_replanejado || []).filter(r => r.level > 1);
          let rows = allRows;
          if (this.levelFilterReplan > 0) {
            rows = rows.filter(r => r.level <= this.levelFilterReplan);
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
              alert(err.detail || "Erro ao importar cronograma.");
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
              alert(err.detail || "Não foi possível excluir a obra.");
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
            'replanejado': 'Replanejado Saldo (' + (this.ffRepViewMode === 'pct' ? '%' : 'R$') + ')',
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
              export_target: target,
              active_tab: this.activeTab,
              dist_view_mode: this.distViewMode || 'val',
              ff_rep_view_mode: this.ffRepViewMode || 'val',
              ff_view_mode: this.ffViewMode || 'val'
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
          if (val === undefined || val === null || isNaN(val)) return "-";
          return "R$ " + Number(val).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        },

        formatDateBr(val) {
          if (!val || val === '-') return '-';
          const parts = val.split('-');
          if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
          return val;
        }
      };
    }
