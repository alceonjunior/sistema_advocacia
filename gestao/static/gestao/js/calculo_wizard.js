/*
 * Script completo e funcional para o Wizard de Cálculo Judicial
 * Versão: 2.6 (Com coleta de dados robusta e feedback de erro aprimorado)
 */
document.addEventListener('DOMContentLoaded', async () => {
    // =========================================================================
    // CONFIGURAÇÃO E VARIÁVEIS GLOBAIS
    // =========================================================================
    const API_INDICES_CATALOGO = window.API_INDICES_CATALOGO || "/api/indices/catalogo/";
    const CALC_ENDPOINT = window.CALC_ENDPOINT || "/api/calculos/simular/";

    let INDICE_CATALOGO = [];
    let parcelaSeq = 0;
    let currentStep = 1;

    const wizard = document.getElementById('calculadora-wizard');
    if (!wizard) return;

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
    // FUNÇÕES UTILITÁRIAS
    // =========================================================================
    function applyMasks(context) {
        if (typeof $ === 'undefined' || typeof $.fn.mask !== 'function') return;
        const scope = context || document;
        $(scope).find('[data-mask="money"]').mask('#.##0,00', { reverse: true });
        $(scope).find('[data-mask="date"]').mask('00/00/0000');
    }

    function getNextDayForInput(dateStr) {
        if (!dateStr || !/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return '';
        const [day, month, year] = dateStr.split('/');
        const date = new Date(year, month - 1, day);
        date.setDate(date.getDate() + 1);
        return formatDateBR(date);
    }

    function dateToISO(dateStr) {
        if (!dateStr || !/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return null;
        const [day, month, year] = dateStr.split('/');
        return `${year}-${month}-${day}`;
    }

    function formatCurrency(value) {
        const num = Number(value) || 0;
        return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function parseDateBR(dateStr) {
        if (!dateStr || !/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return null;
        const [day, month, year] = dateStr.split('/');
        return new Date(year, month - 1, day);
    }

    function formatDateBR(date) {
        if (!(date instanceof Date) || isNaN(date.getTime())) return "";
        return date.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit', year: 'numeric'});
    }

    function addMonths(date, months) { const d = new Date(date); d.setMonth(d.getMonth() + months); return d; }
    function addYears(date, years) { const d = new Date(date); d.setFullYear(d.getFullYear() + years); return d; }

    // =========================================================================
    // LÓGICA DA INTERFACE DO WIZARD (UI)
    // =========================================================================
    function updateWizardUI() {
        stepperLinks.forEach(link => {
            const step = parseInt(link.dataset.step, 10);
            link.classList.toggle('active', step === currentStep);
        });
        stepContents.forEach(content => {
            content.classList.toggle('d-none', parseInt(content.dataset.step, 10) !== currentStep);
        });
        btnPrev.style.display = currentStep > 1 ? 'inline-flex' : 'none';
        btnNext.style.display = currentStep < stepperLinks.length ? 'inline-flex' : 'none';
        btnCalcular.style.display = currentStep === stepperLinks.length ? 'inline-flex' : 'none';
    }

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

    function popularSelectIndice(selectElement) {
        selectElement.innerHTML = '<option value="">Selecione um índice...</option>';
        const groupedIndices = INDICE_CATALOGO.reduce((acc, idx) => {
            if (!idx || !idx.label) return acc;
            const group = idx.group || 'Outros';
            if (!acc[group]) acc[group] = [];
            acc[group].push(idx);
            return acc;
        }, {});

        for (const groupName in groupedIndices) {
            const optgroup = document.createElement('optgroup');
            optgroup.label = groupName;
            groupedIndices[groupName]
                .sort((a,b) => a.label.localeCompare(b.label, 'pt-BR'))
                .forEach(idx => optgroup.appendChild(new Option(idx.label, idx.key)));
            selectElement.appendChild(optgroup);
        }
    }

    // =========================================================================
    // MANIPULAÇÃO DINÂMICA DE PARCELAS E FAIXAS (CRUD)
    // =========================================================================
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

    function adicionarFaixa(parcelaCard) {
        const template = document.getElementById('template-faixa-row');
        const faixa = template.content.cloneNode(true).firstElementChild;
        const lastFaixa = parcelaCard.querySelector('.faixa-row:last-child');
        const dataInicioInput = faixa.querySelector('.faixa-data-inicio');
        if (lastFaixa) {
            const lastEndDate = lastFaixa.querySelector('.faixa-data-fim').value;
            dataInicioInput.value = getNextDayForInput(lastEndDate);
        } else {
            const dataValor = parcelaCard.querySelector('.parcela-data').value;
            if (dataValor) dataInicioInput.value = dataValor;
        }
        faixa.querySelector('.faixa-data-fim').value = formatDateBR(new Date());
        popularSelectIndice(faixa.querySelector('.faixa-indice'));
        parcelaCard.querySelector('.faixas-container').appendChild(faixa);
        applyMasks(faixa);
    }

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
            const prefill = JSON.parse(JSON.stringify(base));
            if (tipo === 'sucessiva') {
                lastDate = periodo === 'anual' ? addYears(lastDate, 1) : addMonths(lastDate, 1);
                prefill.data = formatDateBR(lastDate);
            }
            adicionarParcela(prefill);
        }
        bootstrap.Modal.getInstance(document.getElementById('modalReplicacao')).hide();
    }

    // =========================================================================
    // COLETA, ENVIO E RENDERIZAÇÃO
    // =========================================================================
    function coletarDadosDoFormulario() {
        const form = document.getElementById('wizard-form-main'); // O formulário principal que engloba tudo
        const payload = {
            global: {},
            parcelas: [],
            extras: {}
        };

        // Coleta de dados básicos da Etapa 1
        payload.global.numero_processo = form.querySelector('#calc-numero-processo')?.value || '';
        payload.global.data_transito_em_julgado = form.querySelector('#calc-data-transito')?.value || null;
        payload.global.parte_autora = form.querySelector('#calc-parte-autora')?.value || '';
        payload.global.parte_re = form.querySelector('#calc-parte-re')?.value || '';
        payload.global.observacoes = form.querySelector('#calc-observacoes')?.value || '';

        // Coleta de dados das parcelas da Etapa 2
        form.querySelectorAll('.parcela-card').forEach(p => {
            const parcela = {
                descricao: p.querySelector('.parcela-descricao')?.value || '',
                valor_original: p.querySelector('.parcela-valor')?.value || '0,00',
                data_evento: dateToISO(p.querySelector('.parcela-data')?.value),
                faixas: []
            };
            p.querySelectorAll('.faixa-row').forEach(f => {
                parcela.faixas.push({
                    indice: f.querySelector('.faixa-indice')?.value || '',
                    data_inicio: dateToISO(f.querySelector('.faixa-data-inicio')?.value),
                    data_fim: dateToISO(f.querySelector('.faixa-data-fim')?.value),
                    juros_tipo: f.querySelector('.faixa-juros-tipo')?.value || 'NENHUM',
                    juros_taxa_mensal: f.querySelector('.faixa-juros-taxa')?.value || '0,00',
                    pro_rata: f.querySelector('.faixa-pro-rata')?.checked || false,
                    modo_selic_exclusiva: f.querySelector('.faixa-selic-exclusiva')?.checked || false,
                });
            });
            payload.parcelas.push(parcela);
        });

        // Coleta de dados extras da Etapa 3
        payload.extras.multa_percentual = form.querySelector('#multa-percentual')?.value || '0,00';
        payload.extras.multa_sobre_juros = form.querySelector('#multa-sobre-juros')?.checked || false;
        payload.extras.honorarios_percentual = form.querySelector('#honorarios-percentual')?.value || '0,00';

        return payload;
    }


    function renderizarResultado(data, rascunho_pk) {
        resultadoContainer.innerHTML = '';
        if (!data || !data.memoria_calculo) {
            resultadoContainer.innerHTML = '<div class="alert alert-danger">Ocorreu um erro ao processar o resultado.</div>';
            return;
        }

        const { resumo_total, total_geral, detalhe_parcelas } = data.memoria_calculo;
        const dados_basicos = data.form_data.global;

        // Constrói o HTML do resultado detalhado
        let parcelasHtml = detalhe_parcelas.map((parcela, index) => `
            <div class="mb-4 p-3 border rounded">
                <h6 class="border-bottom pb-2 mb-2">
                    <strong>Parcela ${index + 1}:</strong> ${parcela.descricao}
                </h6>
                <table class="table table-sm table-borderless">
                    <tbody>
                        <tr>
                            <td>Valor Original em ${new Date(parcela.data_valor + 'T00:00:00').toLocaleDateString('pt-BR')}</td>
                            <td class="text-end">${parcela.valor_original}</td>
                        </tr>
                        <tr>
                            <td>(+) Correção Monetária</td>
                            <td class="text-end">${(parseFloat(parcela.valor_apos_correcao.replace('.', '').replace(',', '.')) - parseFloat(parcela.valor_original.replace('.', '').replace(',', '.')) - parseFloat(parcela.juros_aplicados.replace('.', '').replace(',', '.'))).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</td>
                        </tr>
                        <tr>
                            <td>(+) Juros Aplicados</td>
                            <td class="text-end">${parcela.juros_aplicados}</td>
                        </tr>
                        <tr class="fw-bold">
                            <td>Subtotal da Parcela</td>
                            <td class="text-end">${parcela.valor_final}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `).join('');

        const resultadoHtml = `
            <div class="p-3">
                <h4 class="mb-3 border-bottom pb-2">Demonstrativo do Cálculo</h4>

                <div class="mb-4">
                    <p><strong>Processo:</strong> ${dados_basicos.numero_processo || 'Não informado'}</p>
                    <p><strong>Parte Autora:</strong> ${dados_basicos.parte_autora || 'Não informado'}</p>
                    <p><strong>Parte Ré:</strong> ${dados_basicos.parte_re || 'Não informado'}</p>
                </div>

                <h5 class="mt-4">Resumo Geral</h5>
                <table class="table table-bordered">
                    <tbody>
                        ${resumo_total.map(item => `
                            <tr>
                                <td>${item.label}</td>
                                <td class="text-end fw-bold">${formatCurrency(item.value)}</td>
                            </tr>
                        `).join('')}
                        <tr class="table-success fs-5">
                            <td class="fw-bold">(=) Total Geral Devido</td>
                            <td class="text-end fw-bold">${formatCurrency(total_geral)}</td>
                        </tr>
                    </tbody>
                </table>

                <h5 class="mt-4">Memória de Cálculo por Parcela</h5>
                ${parcelasHtml}
            </div>
        `;
        resultadoContainer.innerHTML = resultadoHtml;

        // Habilita o botão de PDF
        const btnPdf = document.getElementById('btn-export-pdf');
        const actionButtons = document.getElementById('action-buttons-resultado');
        if(btnPdf && actionButtons && rascunho_pk) {
            // ATENÇÃO: A URL deve ser construída corretamente
            btnPdf.href = `/calculos/rascunho/${rascunho_pk}/pdf/`;
            actionButtons.style.display = 'block';
        }
    }

    async function enviarCalculo() {

            const payload = coletarDadosDoFormulario();
        btnCalcular.disabled = true;
        btnCalcular.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Calculando...';
        resultadoContainer.innerHTML = '<div class="text-center p-5"><div class="spinner-border text-primary"></div><p class="mt-2">Processando...</p></div>';


        try {
            const response = await fetch(CALC_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (response.ok && result.status === 'success') {
                // Passa os dados e o novo rascunho_pk para a renderização
                renderizarResultado(result.data, result.rascunho_pk);
            } else {
                throw new Error(result.message || `Erro ${response.status} do servidor.`);
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

    btnNext.addEventListener('click', () => navigateStep(1));
    btnPrev.addEventListener('click', () => navigateStep(-1));
    stepperLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            currentStep = parseInt(e.target.dataset.step, 10);
            updateWizardUI();
        });
    });
    btnCalcular.addEventListener('click', enviarCalculo);

    document.getElementById('btn-add-parcela').addEventListener('click', () => adicionarParcela());
    document.getElementById('btn-confirmar-replicacao').addEventListener('click', confirmarReplicacao);

    wizard.addEventListener('click', (e) => {
        const target = e.target.closest('button');
        if (!target) return;

        if (target.id === 'btn-print' || target.id === 'btn-export-pdf') {
            // Ação de Imprimir / Salvar como PDF
            window.print();
        } else if (target.id === 'btn-export-csv') {
            alert('Funcionalidade de exportação para CSV/Excel em desenvolvimento.');
        } else if (target.classList.contains('btn-remove-parcela')) {
            target.closest('.parcela-card').remove();
            reindexarParcelas();
        } else if (target.classList.contains('btn-add-faixa')) {
            adicionarFaixa(target.closest('.parcela-card'));
        } else if (target.classList.contains('btn-remove-faixa')) {
            target.closest('.faixa-row').remove();
        }
    });


    wizard.addEventListener('input', (e) => {
        if (e.target.matches('.parcela-descricao, .parcela-valor')) {
            reindexarParcelas();
        }
    });

    wizard.addEventListener('change', (e) => {
        if (e.target.matches('.parcela-data')) {
            const parcelaCard = e.target.closest('.parcela-card');
            const firstFaixaInicio = parcelaCard.querySelector('.faixa-data-inicio');
            if (firstFaixaInicio && !firstFaixaInicio.value) {
                firstFaixaInicio.value = e.target.value;
            }
        }
    });

    document.getElementById('replicacao-tipo').addEventListener('change', function() {
        document.getElementById('replicacao-sucessiva-options').classList.toggle('d-none', this.value !== 'sucessiva');
    });

    adicionarParcela();
    updateWizardUI();
    applyMasks(wizard);
});