/*
 * Script completo e funcional para o Wizard de Cálculo Judicial
 * Versão: 2.3 (Auditada e Corrigida com Delegação de Eventos)
 *
 * RESPONSABILIDADES:
 * - Controlar a navegação e o estado visual do wizard (stepper).
 * - Gerenciar a adição, remoção e replicação de parcelas e faixas de cálculo via DELEGAÇÃO DE EVENTOS.
 * - Aplicar máscaras de input e validações de formulário no frontend.
 * - Preencher datas de forma inteligente para agilizar o uso.
 * - Carregar dinamicamente os índices de correção do backend.
 * - Coletar, formatar e enviar os dados do cálculo para a API.
 * - Renderizar o resultado detalhado do cálculo na etapa final.
 */
document.addEventListener('DOMContentLoaded', async () => {
    // =========================================================================
    // CONFIGURAÇÃO E VARIÁVEIS GLOBAIS
    // =========================================================================
    const API_INDICES_CATALOGO = window.API_INDICES_CATALOGO || "/api/indices/catalogo/";
    const CALC_ENDPOINT = window.CALC_ENDPOINT || "/ajax/calculo/wizard/calcular/";

    let INDICE_CATALOGO = [];
    let parcelaSeq = 0;
    let currentStep = 1;

    // Seletores de elementos principais da interface
    const wizard = document.getElementById('calculadora-wizard');
    if (!wizard) return; // Aborta se o wizard não estiver na página

    const stepperLinks = wizard.querySelectorAll('.wizard-steps .nav-link');
    const stepContents = wizard.querySelectorAll('.wizard-step');
    const btnPrev = wizard.querySelector('#btn-prev');
    const btnNext = wizard.querySelector('#btn-next');
    const btnCalcular = wizard.querySelector('#btn-calcular');
    const parcelasContainer = wizard.querySelector('#parcelas-container');
    const resultadoContainer = wizard.querySelector('#resultado-container');
    const parcelasSidebar = wizard.querySelector('#parcelas-sidebar');
    const parcelasPlaceholder = wizard.querySelector('#parcelas-placeholder');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    // =========================================================================
    // FUNÇÕES UTILITÁRIAS (MÁSCARAS E DATAS)
    // =========================================================================

    /** Aplica máscaras de formatação a campos de input usando jQuery Mask Plugin. */
    function applyMasks(context) {
        if (typeof $ === 'undefined' || typeof $.fn.mask !== 'function') {
            console.warn("jQuery Mask Plugin não está disponível. Máscaras não serão aplicadas.");
            return;
        }
        const scope = context || document;
        $(scope).find('[data-mask="money"]').mask('#.##0,00', { reverse: true });
        $(scope).find('[data-mask="date"]').mask('00/00/0000');
        $(scope).find('[data-mask="processo"]').mask('0000000-00.0000.0.00.0000');
    }

    /** Retorna a data de hoje no formato YYYY-MM-DD. */
    function getTodayISO() {
        return new Date().toISOString().split('T')[0];
    }

    /** Retorna o dia seguinte de uma data (formato DD/MM/AAAA) para o formato do input (YYYY-MM-DD). */
    function getNextDayForInput(dateStr) {
        if (!dateStr || !/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return '';
        const [day, month, year] = dateStr.split('/');
        const date = new Date(year, month - 1, day);
        date.setDate(date.getDate() + 1);
        return date.toISOString().split('T')[0];
    }

    /** Converte uma data de dd/mm/aaaa para YYYY-MM-DD. */
    function dateToISO(dateStr) {
        if (!dateStr || !/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return null;
        const [day, month, year] = dateStr.split('/');
        return `${year}-${month}-${day}`;
    }

    /** Formata um número como moeda BRL (Real Brasileiro). */
    function formatCurrency(value) {
        const num = Number(String(value).replace(/[^0-9,.]+/g,"").replace('.','').replace(',','.')) || 0;
        return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    /** Converte uma string dd/mm/aaaa para um objeto Date. */
    function parseDateBR(dateStr) {
        if (!dateStr || !/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return null;
        const [day, month, year] = dateStr.split('/');
        return new Date(year, month - 1, day);
    }

    /** Formata um objeto Date para uma string dd/mm/aaaa. */
    function formatDateBR(date) {
        if (!(date instanceof Date) || isNaN(date.getTime())) return "";
        return date.toLocaleDateString('pt-BR');
    }

    function addMonths(date, months) { const d = new Date(date); d.setMonth(d.getMonth() + months); return d; }
    function addYears(date, years) { const d = new Date(date); d.setFullYear(d.getFullYear() + years); return d; }

    // =========================================================================
    // LÓGICA DA INTERFACE DO WIZARD (UI)
    // =========================================================================

    /** Atualiza a interface do wizard (stepper, botões e conteúdo visível). */
    function updateWizardUI() {
        stepperLinks.forEach(link => {
            const step = parseInt(link.dataset.step, 10);
            link.classList.remove('active', 'completed');
            if (step < currentStep) link.classList.add('completed');
            else if (step === currentStep) link.classList.add('active');
        });
        stepContents.forEach(content => {
            content.style.display = parseInt(content.dataset.step, 10) === currentStep ? 'block' : 'none';
        });
        btnPrev.style.display = currentStep > 1 ? 'inline-flex' : 'none';
        btnNext.style.display = currentStep < stepperLinks.length ? 'inline-flex' : 'none';
        btnCalcular.style.display = currentStep === stepperLinks.length ? 'inline-flex' : 'none';
    }

    /** Navega para a próxima ou anterior etapa do wizard. */
    function navigateStep(direction) {
        const nextStep = currentStep + direction;
        if (nextStep > 0 && nextStep <= stepperLinks.length) {
            currentStep = nextStep;
            updateWizardUI();
        }
    }

    // =========================================================================
    // CARREGAMENTO E MANIPULAÇÃO DE ÍNDICES
    // =========================================================================

    /** Carrega o catálogo de índices da API do backend. */
    async function carregarCatalogoIndices() {
        try {
            const response = await fetch(API_INDICES_CATALOGO);
            if (!response.ok) throw new Error('Falha ao carregar índices');
            const data = await response.json();
            INDICE_CATALOGO = data.indices || [];
        } catch (error) {
            console.error(error);
            alert('Não foi possível carregar a lista de índices econômicos.');
        }
    }

    /** Popula um elemento <select> com os índices do catálogo, agrupados por categoria. */
    function popularSelectIndice(selectElement) {
        selectElement.innerHTML = '<option value="">Selecione um índice...</option>';
        const groupedIndices = INDICE_CATALOGO.reduce((acc, idx) => {
            const group = idx.group || 'Outros';
            if (!acc[group]) acc[group] = [];
            acc[group].push(idx);
            return acc;
        }, {});

        for (const groupName in groupedIndices) {
            const optgroup = document.createElement('optgroup');
            optgroup.label = groupName;
            // Valida se a label existe antes de ordenar
            groupedIndices[groupName].sort((a,b) => (a.label || '').localeCompare(b.label || '', 'pt-BR')).forEach(idx => {
                optgroup.appendChild(new Option(idx.label, idx.key));
            });
            selectElement.appendChild(optgroup);
        }
    }

    // =========================================================================
    // MANIPULAÇÃO DINÂMICA DE PARCELAS E FAIXAS (CRUD)
    // =========================================================================

    /** Atualiza a barra lateral com a lista de parcelas. */
    function reindexarParcelas() {
        parcelasSidebar.innerHTML = '';
        const cards = parcelasContainer.querySelectorAll('.parcela-card');
        cards.forEach((card, index) => {
            const id = card.dataset.parcelaId;
            const title = `Parcela ${index + 1}`;
            card.querySelector('.parcela-title').textContent = title;

            const template = document.getElementById('template-parcela-sidebar-item');
            const sidebarItem = template.content.cloneNode(true).firstElementChild;
            sidebarItem.href = `#parcela-card-${id}`;
            sidebarItem.querySelector('.parcela-title').textContent = card.querySelector('.parcela-descricao').value || title;
            sidebarItem.querySelector('.parcela-valor-original').textContent = card.querySelector('.parcela-valor').value || 'R$ 0,00';
            parcelasSidebar.appendChild(sidebarItem);
        });
        document.getElementById('parcelas-count').textContent = cards.length;
        parcelasPlaceholder.style.display = cards.length === 0 ? 'block' : 'none';
    }

    /** Adiciona uma nova faixa de cálculo a uma parcela, com preenchimento automático de datas. */
    function adicionarFaixa(parcelaCard) {
        const template = document.getElementById('template-faixa-row');
        const faixa = template.content.cloneNode(true).firstElementChild;

        const lastFaixa = parcelaCard.querySelector('.faixa-row:last-child');
        const dataInicioInput = faixa.querySelector('.faixa-data-inicio');
        const dataFimInput = faixa.querySelector('.faixa-data-fim');

        if (lastFaixa) {
            const lastEndDate = lastFaixa.querySelector('.faixa-data-fim').value;
            dataInicioInput.value = getNextDayForInput(lastEndDate);
        } else {
            const dataValor = parcelaCard.querySelector('.parcela-data').value;
            if (dataValor) dataInicioInput.value = dataValor;
        }

        dataFimInput.value = formatDateBR(new Date());

        popularSelectIndice(faixa.querySelector('.faixa-indice'));
        parcelaCard.querySelector('.faixas-container').appendChild(faixa);
        applyMasks(faixa);
    }

    /** Adiciona uma nova parcela ao formulário, opcionalmente com dados pré-preenchidos. */
    function adicionarParcela(prefillData = null) {
        parcelaSeq++;
        const id = `p${parcelaSeq}`;
        const template = document.getElementById('template-parcela-card');
        const parcela = template.content.cloneNode(true).firstElementChild;
        parcela.id = `parcela-card-${id}`;
        parcela.dataset.parcelaId = id;

        parcelasContainer.appendChild(parcela);

        if (prefillData) {
            parcela.querySelector('.parcela-descricao').value = prefillData.descricao;
            parcela.querySelector('.parcela-valor').value = prefillData.valor;
            parcela.querySelector('.parcela-data').value = prefillData.data;

            prefillData.faixas.forEach(faixaData => {
                const faixaTemplate = document.getElementById('template-faixa-row');
                const faixa = faixaTemplate.content.cloneNode(true).firstElementChild;
                popularSelectIndice(faixa.querySelector('.faixa-indice'));
                faixa.querySelector('.faixa-indice').value = faixaData.indice;
                faixa.querySelector('.faixa-data-inicio').value = faixaData.data_inicio;
                faixa.querySelector('.faixa-data-fim').value = faixaData.data_fim;
                faixa.querySelector('.faixa-juros-tipo').value = faixaData.juros_tipo;
                faixa.querySelector('.faixa-juros-taxa').value = faixaData.juros_taxa_mensal;
                faixa.querySelector('.faixa-pro-rata').checked = faixaData.pro_rata;
                faixa.querySelector('.faixa-selic-exclusiva').checked = faixaData.modo_selic_exclusiva;
                parcela.querySelector('.faixas-container').appendChild(faixa);
            });
        } else {
            adicionarFaixa(parcela);
        }

        applyMasks(parcela);
        reindexarParcelas();
    }

    /** Lógica de replicação de parcelas. */
    function confirmarReplicacao() {
        const lastCard = parcelasContainer.querySelector('.parcela-card:last-child');
        if (!lastCard) { alert("Não há nenhuma parcela para replicar."); return; }

        const tipo = document.getElementById('replicacao-tipo').value;
        const qtd = parseInt(document.getElementById('replicacao-quantidade').value, 10) || 0;
        const periodo = document.getElementById('replicacao-periodo').value;

        if (qtd <= 0) { alert("A quantidade de novas parcelas deve ser maior que zero."); return; }

        const base = {
            descricao: lastCard.querySelector('.parcela-descricao').value,
            valor: lastCard.querySelector('.parcela-valor').value,
            data: lastCard.querySelector('.parcela-data').value,
            faixas: Array.from(lastCard.querySelectorAll('.faixa-row')).map(f => ({
                indice: f.querySelector('.faixa-indice').value,
                data_inicio: f.querySelector('.faixa-data-inicio').value,
                data_fim: f.querySelector('.faixa-data-fim').value,
                juros_tipo: f.querySelector('.faixa-juros-tipo').value,
                juros_taxa_mensal: f.querySelector('.faixa-juros-taxa').value,
                pro_rata: f.querySelector('.faixa-pro-rata').checked,
                modo_selic_exclusiva: f.querySelector('.faixa-selic-exclusiva').checked,
            }))
        };

        let lastDate = parseDateBR(base.data);
        if (!lastDate) { alert("A data da última parcela é inválida."); return; }

        for (let i = 0; i < qtd; i++) {
            const prefill = JSON.parse(JSON.stringify(base)); // Deep copy
            if (tipo === 'sucessiva') {
                lastDate = periodo === 'anual' ? addYears(lastDate, 1) : addMonths(lastDate, 1);
                prefill.data = formatDateBR(lastDate);
            }
            adicionarParcela(prefill);
        }
        bootstrap.Modal.getInstance(document.getElementById('modalReplicacao')).hide();
    }

    // =========================================================================
    // COLETA DE DADOS E ENVIO PARA O BACKEND
    // =========================================================================
    function coletarDadosDoFormulario() {
        const payload = {
            global: {
                numero_processo: document.getElementById('calc-numero-processo').value,
                data_transito_em_julgado: dateToISO(document.getElementById('calc-data-transito').value),
                observacoes: document.getElementById('calc-observacoes').value,
            },
            parcelas: [],
            extras: {
                multa_percentual: document.getElementById('multa-percentual').value || "0",
                multa_sobre_juros: document.getElementById('multa-sobre-juros').checked,
                honorarios_percentual: document.getElementById('honorarios-percentual').value || "0",
            }
        };

        parcelasContainer.querySelectorAll('.parcela-card').forEach(p => {
            const parcela = {
                descricao: p.querySelector('.parcela-descricao').value,
                valor_original: p.querySelector('.parcela-valor').value,
                data_evento: dateToISO(p.querySelector('.parcela-data').value),
                faixas: Array.from(p.querySelectorAll('.faixa-row')).map(f => ({
                    indice: f.querySelector('.faixa-indice').value,
                    data_inicio: dateToISO(f.querySelector('.faixa-data-inicio').value),
                    data_fim: dateToISO(f.querySelector('.faixa-data-fim').value),
                    juros_tipo: f.querySelector('.faixa-juros-tipo').value,
                    juros_taxa_mensal: f.querySelector('.faixa-juros-taxa').value,
                    pro_rata: f.querySelector('.faixa-pro-rata').checked,
                    modo_selic_exclusiva: f.querySelector('.faixa-selic-exclusiva').checked,
                }))
            };
            payload.parcelas.push(parcela);
        });
        return payload;
    }

    function renderizarResultado(data) {
        resultadoContainer.innerHTML = '';
        if (!data || !data.resumo) {
            resultadoContainer.innerHTML = '<div class="alert alert-danger">Ocorreu um erro ao processar o resultado.</div>';
            return;
        }
        const resumo = data.resumo;
        const resultadoHtml = `
            <div class="alert alert-success text-center">
                <h4 class="alert-heading">Cálculo Concluído!</h4>
                <p class="h2 mb-0">${formatCurrency(resumo.total_geral)}</p>
                <p class="mb-0">Valor Total Atualizado</p>
            </div>
            <h5 class="mt-4">Resumo Detalhado</h5>
            <table class="table table-sm table-bordered"><tbody>
                <tr><td>(+) Valor Principal Original</td><td class="text-end">${formatCurrency(resumo.principal)}</td></tr>
                <tr><td>(+) Correção Monetária Total</td><td class="text-end">${formatCurrency(resumo.correcao)}</td></tr>
                <tr><td>(+) Juros Totais</td><td class="text-end">${formatCurrency(resumo.juros)}</td></tr>
                <tr><td>(+) Multas</td><td class="text-end">${formatCurrency(resumo.multas)}</td></tr>
                <tr><td>(+) Honorários</td><td class="text-end">${formatCurrency(resumo.honorarios)}</td></tr>
                <tr class="table-primary fw-bold"><td>(=) Total Geral Devido</td><td class="text-end">${formatCurrency(resumo.total_geral)}</td></tr>
            </tbody></table>
            <h5 class="mt-4">Memória de Cálculo</h5>
            <pre class="bg-light p-3 rounded" style="white-space: pre-wrap; font-size: 0.8em;">${data.memoria_texto || 'Memória de cálculo não gerada.'}</pre>
        `;
        resultadoContainer.innerHTML = resultadoHtml;
    }

    async function enviarCalculo() {
        const payload = coletarDadosDoFormulario();
        btnCalcular.disabled = true;
        btnCalcular.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Calculando...';
        resultadoContainer.innerHTML = '<div class="text-center p-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Processando...</p></div>';
        try {
            const response = await fetch(CALC_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (response.ok && result.status === 'success') {
                renderizarResultado(result.data);
            } else {
                throw new Error(result.message || 'Erro desconhecido no servidor.');
            }
        } catch (error) {
            console.error("Erro ao calcular:", error);
            resultadoContainer.innerHTML = `<div class="alert alert-danger"><strong>Erro:</strong> ${error.message}</div>`;
        } finally {
             btnCalcular.disabled = false;
             btnCalcular.innerHTML = '<i class="bi bi-cpu me-1"></i> Calcular';
        }
    }

    // =========================================================================
    // INICIALIZAÇÃO E DELEGAÇÃO DE EVENTOS
    // =========================================================================
    await carregarCatalogoIndices();

    // Navegação
    btnNext.addEventListener('click', () => navigateStep(1));
    btnPrev.addEventListener('click', () => navigateStep(-1));
    stepperLinks.forEach(link => {
        link.addEventListener('click', () => {
            currentStep = parseInt(link.dataset.step, 10);
            updateWizardUI();
        });
    });
    btnCalcular.addEventListener('click', enviarCalculo);

    // Ações principais (não dinâmicas)
    document.getElementById('btn-add-parcela').addEventListener('click', adicionarParcela);
    document.getElementById('btn-confirmar-replicacao').addEventListener('click', confirmarReplicacao);

    // DELEGAÇÃO DE EVENTOS para elementos dinâmicos
    wizard.addEventListener('click', (e) => {
        const removeParcelaBtn = e.target.closest('.btn-remove-parcela');
        if (removeParcelaBtn) {
            removeParcelaBtn.closest('.parcela-card').remove();
            reindexarParcelas();
        }
        const addFaixaBtn = e.target.closest('.btn-add-faixa');
        if (addFaixaBtn) {
            adicionarFaixa(addFaixaBtn.closest('.parcela-card'));
        }
        const removeFaixaBtn = e.target.closest('.btn-remove-faixa');
        if (removeFaixaBtn) {
            removeFaixaBtn.closest('.faixa-row').remove();
        }
        const sidebarLink = e.target.closest('#parcelas-sidebar a');
        if (sidebarLink) {
            e.preventDefault();
            document.querySelector(sidebarLink.getAttribute('href'))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });

    // Delegação para atualizações de UI em tempo real
    wizard.addEventListener('input', (e) => {
        if (e.target.matches('.parcela-descricao, .parcela-valor')) {
            reindexarParcelas();
        }
    });

    wizard.addEventListener('change', (e) => {
        if (e.target.matches('.parcela-data')) {
            const parcelaCard = e.target.closest('.parcela-card');
            const firstFaixaInicio = parcelaCard.querySelector('.faixa-data-inicio');
            if (firstFaixaInicio) {
                firstFaixaInicio.value = e.target.value;
            }
        }
    });

    document.getElementById('replicacao-tipo').addEventListener('change', function() {
        document.getElementById('replicacao-sucessiva-options').classList.toggle('d-none', this.value !== 'sucessiva');
    });

    // Inicia o wizard
    adicionarParcela();
    updateWizardUI();
    applyMasks(wizard);
});
