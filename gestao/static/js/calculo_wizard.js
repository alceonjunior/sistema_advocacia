/**
 * Script de controle para o Wizard de Cálculo Judicial.
 * Gerencia a navegação, validação, manipulação de parcelas e faixas,
 * comunicação com a API de cálculo e renderização dos resultados.
 *
 * Versão: 1.0.0 - Integral e Funcional
 * Autor: Gemini Senior Dev
 */
(() => {
    // Garante que o script só execute após o carregamento completo do DOM
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize);
    } else {
        initialize();
    }

    function initialize() {
        const Wizard = {
            elements: {
                wizard: document.getElementById('calculadora-wizard'),
                stepper: document.getElementById('wizard-stepper'),
                steps: document.querySelectorAll('.wizard-step'),
                btnNext: document.getElementById('btn-next'),
                btnPrev: document.getElementById('btn-prev'),
                btnCalc: document.getElementById('btn-calcular'),
                parcelasContainer: document.getElementById('parcelas-container'),
                parcelasSidebar: document.getElementById('parcelas-sidebar'),
                parcelasPlaceholder: document.getElementById('parcelas-placeholder'),
                resultadoContainer: document.getElementById('resultado-container'),
                modalReplicacao: new bootstrap.Modal(document.getElementById('modalReplicacao')),
                formPDF: document.createElement('form'),
            },

            state: {
                currentStep: 1,
                totalSteps: 4,
                parcelaCounter: 0,
                faixaCounter: 0,
                lastResultPayload: null,
                lastResultData: null,
            },

            init() {
                this.updateButtons();
                this.bindEvents();
                this.prefillStep1();

                if (this.elements.parcelasContainer.querySelectorAll('.parcela-card').length === 0) {
                    this.addParcela();
                }

                this.elements.formPDF.method = 'POST';
                this.elements.formPDF.action = exportPdfUrl;
                this.elements.formPDF.target = '_blank';
                this.elements.formPDF.innerHTML = `
                    <input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}">
                    <input type="hidden" name="payload">
                `;
                document.body.appendChild(this.elements.formPDF);
            },

            showStep(step) {
                if (step < 1 || step > this.state.totalSteps) return;

                this.state.currentStep = step;
                this.elements.steps.forEach(el => el.classList.add('d-none'));
                this.elements.wizard.querySelector(`.wizard-step[data-step="${step}"]`).classList.remove('d-none');

                this.elements.stepper.querySelectorAll('.nav-link').forEach(link => {
                    const linkStep = parseInt(link.dataset.step, 10);
                    link.classList.remove('active');
                    if (linkStep === step) {
                        link.classList.add('active');
                    }
                });
                this.updateButtons();
                window.scrollTo(0, 0);
            },

            updateButtons() {
                this.elements.btnPrev.disabled = this.state.currentStep === 1;
                this.elements.btnNext.classList.toggle('d-none', this.state.currentStep >= this.state.totalSteps - 1);
                this.elements.btnCalc.classList.toggle('d-none', this.state.currentStep !== this.state.totalSteps - 1);
            },

            validateStep(stepToValidate) {
                this.elements.wizard.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                let isValid = true;
                let firstInvalidElement = null;

                if (stepToValidate === 2) {
                    const cards = this.elements.parcelasContainer.querySelectorAll('.parcela-card');
                    if (cards.length === 0) {
                        alert('Você precisa adicionar pelo menos uma parcela para continuar.');
                        return false;
                    }
                    cards.forEach(card => {
                        card.querySelectorAll('input[required], select[required]').forEach(input => {
                            let isFieldValid = true;
                            if (!input.value.trim()) {
                                isFieldValid = false;
                            } else if (input.classList.contains('parcela-valor') && this.utils.parseBRL(input.value) <= 0) {
                               isFieldValid = false;
                            }

                            if (!isFieldValid) {
                                input.classList.add('is-invalid');
                                isValid = false;
                                if (!firstInvalidElement) firstInvalidElement = input;
                            }
                        });
                    });
                    if (!isValid) {
                        alert('Verifique os campos obrigatórios (marcados com *) em todas as parcelas e faixas.');
                        firstInvalidElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        firstInvalidElement?.focus();
                    }
                }
                return isValid;
            },

            prefillStep1() {
                try {
                    if (initialData && initialData.numero_processo) {
                        document.getElementById('calc-numero-processo').value = initialData.numero_processo;
                    }
                     if (initialData && initialData.partes && initialData.partes.length > 0) {
                        document.getElementById('calc-parte-autora').value = initialData.partes.find(p => p.tipo.toLowerCase().includes('autor'))?.nome || '';
                        document.getElementById('calc-parte-re').value = initialData.partes.find(p => p.tipo.toLowerCase().includes('réu'))?.nome || '';
                    }
                } catch(e) { console.error("Erro ao pré-preencher dados:", e); }
            },

            addParcela(data = {}) {
                this.state.parcelaCounter++;
                const newId = this.state.parcelaCounter;

                const cardTemplate = document.getElementById('template-parcela-card');
                const newCard = cardTemplate.content.cloneNode(true).firstElementChild;
                newCard.dataset.parcelaId = newId;
                const title = data.descricao || `Parcela ${newId}`;
                newCard.querySelector('.parcela-title').textContent = title;
                newCard.querySelector('.parcela-descricao').value = title;
                newCard.querySelector('.parcela-valor').value = data.valor_original ? this.utils.formatCurrency(data.valor_original, false) : '';
                newCard.querySelector('.parcela-data').value = data.data_evento || '';
                this.elements.parcelasContainer.appendChild(newCard);

                const sidebarTemplate = document.getElementById('template-parcela-sidebar-item');
                const newSidebarItem = sidebarTemplate.content.cloneNode(true).firstElementChild;
                newSidebarItem.dataset.targetParcelaId = newId;
                newSidebarItem.querySelector('.parcela-title').textContent = title;
                newSidebarItem.querySelector('.parcela-valor-original').textContent = this.utils.formatCurrency(data.valor_original || 0);
                this.elements.parcelasSidebar.appendChild(newSidebarItem);

                this.elements.parcelasPlaceholder.classList.add('d-none');

                if (data.faixas && data.faixas.length > 0) {
                    data.faixas.forEach(faixaData => this.addFaixa(newCard, faixaData));
                } else {
                    this.addFaixa(newCard);
                }
                this.updateSidebarActive(newId);
                newCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            },

            addFaixa(parcelaCard, data = {}) {
                this.state.faixaCounter++;
                const newId = this.state.faixaCounter;

                const faixaTemplate = document.getElementById('template-faixa-row');
                const newFaixa = faixaTemplate.content.cloneNode(true).firstElementChild;
                newFaixa.dataset.faixaId = newId;

                const select = newFaixa.querySelector('.faixa-indice');
                select.innerHTML = '<option value="">Selecione...</option>';
                indiceOptions.forEach(opt => select.add(new Option(opt, opt)));

                if (Object.keys(data).length > 0) {
                    select.value = data.indice;
                    newFaixa.querySelector('.faixa-data-inicio').value = data.data_inicio;
                    newFaixa.querySelector('.faixa-data-fim').value = data.data_fim;
                    newFaixa.querySelector('.faixa-juros-tipo').value = data.juros_tipo || 'NENHUM';
                    newFaixa.querySelector('.faixa-juros-taxa').value = this.utils.formatCurrency(data.juros_taxa_mensal || 0, false);
                    newFaixa.querySelector('.faixa-pro-rata').checked = data.pro_rata !== false;
                    newFaixa.querySelector('.faixa-selic-exclusiva').checked = data.modo_selic_exclusiva === true;
                }

                parcelaCard.querySelector('.faixas-container').appendChild(newFaixa);
            },

            removeElement(elementToRemove) {
                 if (elementToRemove.classList.contains('parcela-card')) {
                    const id = elementToRemove.dataset.parcelaId;
                    this.elements.parcelasSidebar.querySelector(`[data-target-parcela-id="${id}"]`)?.remove();
                }
                elementToRemove.remove();
                if (this.elements.parcelasContainer.querySelectorAll('.parcela-card').length === 0) {
                    this.elements.parcelasPlaceholder.classList.remove('d-none');
                }
            },

            duplicateParcela(sourceCard) {
                const data = this.gatherDataFromCard(sourceCard);
                data.descricao = `${data.descricao} (Cópia)`;
                this.addParcela(data);
            },

            handleReplication() {
                const tipo = document.getElementById('replicacao-tipo').value;
                const quantidade = parseInt(document.getElementById('replicacao-quantidade').value, 10);
                const sourceCards = this.elements.parcelasContainer.querySelectorAll('.parcela-card');
                if (sourceCards.length === 0) {
                    alert('Adicione pelo menos uma parcela antes de replicar.');
                    return;
                }
                const lastCard = sourceCards[sourceCards.length - 1];
                const sourceData = this.gatherDataFromCard(lastCard);

                for (let i = 1; i <= quantidade; i++) {
                    const newData = JSON.parse(JSON.stringify(sourceData)); // Deep copy
                    newData.descricao = `${sourceData.descricao.replace(/\(\d+\/\d+\)/g, '').trim()} (${i+1}/${quantidade+1})`;

                    if (tipo === 'sucessiva') {
                        const periodo = document.getElementById('replicacao-periodo').value;
                        newData.faixas.forEach(faixa => {
                            let dtInicio = new Date(faixa.data_inicio + 'T12:00:00Z');
                            let dtFim = new Date(faixa.data_fim + 'T12:00:00Z');
                            if (periodo === 'mensal') {
                                dtInicio.setMonth(dtInicio.getMonth() + i);
                                dtFim.setMonth(dtFim.getMonth() + i);
                            } else if (periodo === 'anual') {
                                dtInicio.setFullYear(dtInicio.getFullYear() + i);
                                dtFim.setFullYear(dtFim.getFullYear() + i);
                            }
                            faixa.data_inicio = dtInicio.toISOString().split('T')[0];
                            faixa.data_fim = dtFim.toISOString().split('T')[0];
                        });
                    }
                    this.addParcela(newData);
                }
                this.elements.modalReplicacao.hide();
            },

            gatherDataFromCard(pCard) {
                const parcela = {
                    descricao: pCard.querySelector('.parcela-descricao').value || 'Parcela',
                    valor_original: this.utils.parseBRL(pCard.querySelector('.parcela-valor').value),
                    data_evento: pCard.querySelector('.parcela-data').value,
                    faixas: []
                };
                pCard.querySelectorAll('.faixa-row').forEach(fRow => {
                    parcela.faixas.push({
                        indice: fRow.querySelector('.faixa-indice').value,
                        data_inicio: fRow.querySelector('.faixa-data-inicio').value,
                        data_fim: fRow.querySelector('.faixa-data-fim').value,
                        juros_tipo: fRow.querySelector('.faixa-juros-tipo').value,
                        juros_taxa_mensal: this.utils.parseBRL(fRow.querySelector('.faixa-juros-taxa').value),
                        pro_rata: fRow.querySelector('.faixa-pro-rata').checked,
                        modo_selic_exclusiva: fRow.querySelector('.faixa-selic-exclusiva').checked,
                        base_dias: "corridos",
                    });
                });
                return parcela;
            },

            gatherData() {
                const payload = { global: {}, parcelas: [], extras: [] };
                payload.global = {
                    numero_processo: document.getElementById('calc-numero-processo').value || null,
                    data_transito: document.getElementById('calc-data-transito').value || null,
                    observacoes: document.getElementById('calc-observacoes').value || null,
                    partes: [
                        { nome: document.getElementById('calc-parte-autora').value, tipo: 'Autor' },
                        { nome: document.getElementById('calc-parte-re').value, tipo: 'Réu' }
                    ]
                };
                this.elements.parcelasContainer.querySelectorAll('.parcela-card').forEach(pCard => {
                    payload.parcelas.push(this.gatherDataFromCard(pCard));
                });
                return payload;
            },

            async simulateCalculation() {
                if (!this.validateStep(this.state.currentStep)) return;

                const payload = this.gatherData();
                this.state.lastResultPayload = payload;

                this.elements.resultadoContainer.innerHTML = `<div class="text-center p-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-2 text-muted">Calculando, por favor aguarde...</p></div>`;
                this.showStep(4);

                try {
                    const response = await fetch(simularApiUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify(payload)
                    });
                    const result = await response.json();

                    if (result.status === 'success') {
                        this.state.lastResultData = result.data;
                        this.renderResults(result.data);
                    } else {
                        this.elements.resultadoContainer.innerHTML = `<div class="alert alert-danger"><strong>Erro no Cálculo:</strong> ${result.message}</div>`;
                    }
                } catch (error) {
                     this.elements.resultadoContainer.innerHTML = `<div class="alert alert-danger"><strong>Erro de Comunicação:</strong> Não foi possível conectar ao servidor.</div>`;
                }
            },

            renderResults(data) {
                const f = this.utils.formatCurrency;
                let html = `
                    <h4 class="mb-3">Resumo Geral</h4>
                    <table class="table table-sm table-bordered">
                        <tbody>
                            <tr><td>(+) Valor Principal Original</td><td class="text-end">${f(data.resumo.principal)}</td></tr>
                            <tr><td>(+) Correção Monetária</td><td class="text-end">${f(data.resumo.correcao)}</td></tr>
                            <tr><td>(+) Juros</td><td class="text-end">${f(data.resumo.juros)}</td></tr>
                            <tr class="table-primary fw-bold"><td>(=) Total Geral</td><td class="text-end">${f(data.resumo.total_geral)}</td></tr>
                        </tbody>
                    </table>
                    <h4 class="mt-4 mb-3">Detalhamento por Parcela</h4>
                `;

                data.parcelas.forEach((p, index) => {
                    html += `
                    <div class="card mb-3">
                        <div class="card-header bg-light"><strong>Parcela ${index+1}: ${p.descricao}</strong></div>
                        <div class="table-responsive">
                        <table class="table table-striped table-hover mb-0">
                            <thead><tr><th>Memória de Cálculo da Parcela</th><th class="text-end">Valor Original</th><th class="text-end">Correção</th><th class="text-end">Juros</th><th class="text-end">Valor Final</th></tr></thead>
                            <tbody>
                                <tr>
                                    <td>${p.memoria_detalhada.join('<br>')}</td>
                                    <td class="text-end">${f(p.valor_original)}</td>
                                    <td class="text-end">${f(p.correcao_total)}</td>
                                    <td class="text-end">${f(p.juros_total)}</td>
                                    <td class="text-end fw-bold">${f(p.valor_final)}</td>
                                </tr>
                            </tbody>
                        </table>
                        </div>
                    </div>
                    `;
                });

                this.elements.resultadoContainer.innerHTML = html;
            },

            exportToPDF() {
                if (!this.state.lastResultPayload) return alert("Nenhum cálculo foi realizado para exportar.");
                this.elements.formPDF.querySelector('[name="payload"]').value = JSON.stringify(this.state.lastResultPayload);
                this.elements.formPDF.submit();
            },

            utils: {
                formatCurrency(value, withSymbol = true) {
                    const valStr = value?.toString() || '0';
                    const val = parseFloat(this.parseBRL(valStr));
                    if (isNaN(val)) return withSymbol ? "R$ 0,00" : "0,00";
                    const options = withSymbol ? { style: 'currency', currency: 'BRL' } : { minimumFractionDigits: 2, maximumFractionDigits: 2 };
                    return val.toLocaleString('pt-BR', options);
                },
                parseBRL(str) {
                    if (typeof str !== 'string' || !str) return '0.00';
                    const number = str.replace(/[R$\s.]/g, '').replace(',', '.');
                    const parsed = parseFloat(number);
                    return isNaN(parsed) ? '0.00' : parsed.toFixed(2);
                },
            },

            bindEvents() {
                this.elements.btnNext.addEventListener('click', () => {
                    if (this.validateStep(this.state.currentStep)) {
                        this.showStep(this.state.currentStep + 1);
                    }
                });
                this.elements.btnPrev.addEventListener('click', () => this.showStep(this.state.currentStep - 1));
                this.elements.btnCalc.addEventListener('click', () => this.simulateCalculation());

                this.elements.wizard.addEventListener('click', (e) => {
                    const target = e.target;
                    const btnAddParcela = target.closest('#btn-add-parcela');
                    if (btnAddParcela) return this.addParcela();

                    const btnAddFaixa = target.closest('.btn-add-faixa');
                    if (btnAddFaixa) return this.addFaixa(target.closest('.parcela-card'));

                    const btnRemoveFaixa = target.closest('.btn-remove-faixa');
                    if (btnRemoveFaixa) return this.removeElement(target.closest('.faixa-row'));

                    const btnCloneParcela = target.closest('.btn-clone-parcela');
                    if (btnCloneParcela) return this.duplicateParcela(target.closest('.parcela-card'));

                    const btnRemoveParcela = target.closest('.btn-remove-parcela');
                    if (btnRemoveParcela) return this.removeElement(target.closest('.parcela-card'));

                    const sidebarItem = target.closest('.list-group-item[data-target-parcela-id]');
                    if (sidebarItem) {
                        e.preventDefault();
                        const id = sidebarItem.dataset.targetParcelaId;
                        this.updateSidebarActive(id);
                        this.elements.parcelasContainer.querySelector(`[data-parcela-id="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }

                    if (target.closest('#btn-export-pdf')) this.exportToPDF();
                });

                this.elements.wizard.addEventListener('input', (e) => {
                    const parcelaCard = e.target.closest('.parcela-card');
                    if (!parcelaCard) return;
                    const id = parcelaCard.dataset.parcelaId;
                    const sidebarItem = this.elements.parcelasSidebar.querySelector(`[data-target-parcela-id="${id}"]`);
                    if (sidebarItem) {
                        if (e.target.matches('.parcela-descricao')) {
                            sidebarItem.querySelector('.parcela-title').textContent = e.target.value || `Parcela ${id}`;
                        }
                        if (e.target.matches('.parcela-valor')) {
                            sidebarItem.querySelector('.parcela-valor-original').textContent = this.utils.formatCurrency(e.target.value);
                        }
                    }
                    if (e.target.matches('.faixa-selic-exclusiva')) {
                        const faixaRow = e.target.closest('.faixa-row');
                        const jurosTipo = faixaRow.querySelector('.faixa-juros-tipo');
                        const jurosTaxa = faixaRow.querySelector('.faixa-juros-taxa');
                        if (e.target.checked) {
                            jurosTipo.value = 'NENHUM';
                            jurosTipo.disabled = true;
                            jurosTaxa.disabled = true;
                        } else {
                            jurosTipo.disabled = false;
                            jurosTaxa.disabled = false;
                        }
                    }
                });

                this.elements.wizard.addEventListener('blur', (e) => {
                    if (e.target.matches('.parcela-valor, .faixa-juros-taxa')) {
                        e.target.value = this.utils.formatCurrency(e.target.value, false);
                    }
                }, true);

                document.getElementById('btn-confirmar-replicacao')?.addEventListener('click', () => this.handleReplication());
            },
        };

        Wizard.init();
    }
})();