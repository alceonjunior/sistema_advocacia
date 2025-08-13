/**
 * Script de controle para o Wizard de Cálculo Judicial.
 * Gerencia a navegação, validação, manipulação de parcelas e faixas,
 * comunicação com a API de cálculo e renderização dos resultados.
 *
 * Versão: 3.0.0 - Definitiva e Robusta
 * Autor: Gemini Senior Dev
 */
(() => {
    // Garante que o script só execute após o carregamento completo do DOM
    document.addEventListener("DOMContentLoaded", () => {

        const Wizard = {
            // 1. Elementos da UI (Interface do Usuário)
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
                formPDF: document.createElement('form'),
            },

            // 2. Estado do Wizard (Variáveis de controle)
            state: {
                currentStep: 1,
                totalSteps: 4,
                parcelaCounter: 0,
                faixaCounter: 0,
                lastResultPayload: null,
                lastResultData: null,
            },

            // 3. Ponto de Entrada Principal (Onde tudo começa)
            init() {
                // Etapa crucial: Verifica se os elementos básicos existem na página.
                // Se o wizard não for encontrado, o script para e avisa no console.
                if (!this.elements.wizard) {
                    console.error("Elemento principal do wizard (#calculadora-wizard) não encontrado. O script não será executado.");
                    return;
                }

                // Prepara o formulário invisível para exportar o PDF.
                this.setupPdfForm();

                // Pré-preenche os dados do processo, se houver.
                this.prefillStep1();

                // Inicializa a primeira parcela se o container estiver vazio.
                if (this.elements.parcelasContainer.querySelectorAll('.parcela-card').length === 0) {
                    this.addParcela();
                }

                // Atualiza o estado dos botões.
                this.updateButtons();

                // LIGA OS EVENTOS: Esta é a etapa mais importante.
                // Ela só é chamada no final, garantindo que tudo já foi criado e está pronto para receber interações.
                this.bindEvents();
            },

            // 4. Métodos de Ação e Lógica

            /**
             * Alterna a visibilidade dos passos (etapas) do wizard.
             * @param {number} step - O número do passo a ser exibido.
             */
            showStep(step) {
                if (step < 1 || step > this.state.totalSteps) return;
                this.state.currentStep = step;

                // Esconde todos os passos e mostra apenas o atual.
                this.elements.steps.forEach(el => el.classList.add('d-none'));
                this.elements.wizard.querySelector(`.wizard-step[data-step="${step}"]`).classList.remove('d-none');

                // Atualiza o indicador de passo ativo na barra de navegação superior.
                this.elements.stepper.querySelectorAll('.nav-link').forEach(link => {
                    link.classList.toggle('active', parseInt(link.dataset.step, 10) === step);
                });

                this.updateButtons();
                window.scrollTo(0, 0); // Rola a página para o topo.
            },

            /**
             * Habilita/desabilita e mostra/esconde os botões de navegação conforme o passo atual.
             */
            updateButtons() {
                this.elements.btnPrev.disabled = this.state.currentStep === 1;
                this.elements.btnNext.classList.toggle('d-none', this.state.currentStep >= this.state.totalSteps - 1);
                this.elements.btnCalc.classList.toggle('d-none', this.state.currentStep !== this.state.totalSteps - 1);
            },

            /**
             * Sincroniza a seleção do card de parcela com o item ativo na barra lateral.
             * @param {string|number} activeId - O ID da parcela a ser marcada como ativa.
             */
            updateSidebarActive(activeId) {
                if (!this.elements.parcelasSidebar) return;
                this.elements.parcelasSidebar.querySelectorAll('.list-group-item').forEach(item => {
                    item.classList.toggle('active', item.dataset.targetParcelaId === activeId.toString());
                });
            },

            /**
             * Valida os campos obrigatórios do passo atual antes de avançar.
             * @param {number} stepToValidate - O número do passo a ser validado.
             * @returns {boolean} - Retorna true se for válido, false caso contrário.
             */
            validateStep(stepToValidate) {
                this.elements.wizard.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                let isValid = true;
                let firstInvalidElement = null;

                if (stepToValidate === 2) { // Validação específica para o passo das parcelas
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

            /**
             * Pré-preenche os dados básicos (Passo 1) se vier de uma página de processo.
             */
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

            /**
             * Adiciona um novo card de parcela à tela.
             * @param {object} data - Dados opcionais para pré-preencher a parcela.
             */
            addParcela(data = {}) {
                this.state.parcelaCounter++;
                const newId = this.state.parcelaCounter;
                const today = new Date().toISOString().split('T')[0];

                // Clona o template do card de parcela
                const cardTemplate = document.getElementById('template-parcela-card');
                const newCard = cardTemplate.content.cloneNode(true).firstElementChild;
                newCard.dataset.parcelaId = newId;

                // Preenche os dados do card
                const title = data.descricao || `Parcela ${newId}`;
                newCard.querySelector('.parcela-title').textContent = title;
                newCard.querySelector('.parcela-descricao').value = title;
                newCard.querySelector('.parcela-valor').value = data.valor_original ? this.utils.formatBRL(data.valor_original) : '1.000,00';
                newCard.querySelector('.parcela-data').value = data.data_evento || today;

                this.elements.parcelasContainer.appendChild(newCard);
                this.elements.parcelasPlaceholder.classList.add('d-none'); // Esconde a mensagem de "nenhuma parcela"

                // Clona e preenche o item correspondente na barra lateral
                const sidebarTemplate = document.getElementById('template-parcela-sidebar-item');
                const newSidebarItem = sidebarTemplate.content.cloneNode(true).firstElementChild;
                newSidebarItem.dataset.targetParcelaId = newId;
                newSidebarItem.querySelector('.parcela-title').textContent = title;
                newSidebarItem.querySelector('.parcela-valor-original').textContent = this.utils.formatBRL(data.valor_original || 1000, true);

                this.elements.parcelasSidebar.appendChild(newSidebarItem);

                // Adiciona uma faixa de cálculo padrão para a nova parcela
                if (data.faixas && data.faixas.length > 0) {
                    data.faixas.forEach(faixaData => this.addFaixa(newCard, faixaData));
                } else {
                    this.addFaixa(newCard, { data_inicio: data.data_evento || today });
                }

                this.updateSidebarActive(newId);
                newCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            },

            /**
             * Adiciona uma nova faixa de cálculo (correção/juros) a um card de parcela.
             * @param {HTMLElement} parcelaCard - O elemento do card da parcela.
             * @param {object} data - Dados opcionais para pré-preencher a faixa.
             */
            addFaixa(parcelaCard, data = {}) {
                this.state.faixaCounter++;
                const today = new Date().toISOString().split('T')[0];
                const faixaTemplate = document.getElementById('template-faixa-row');
                const newFaixa = faixaTemplate.content.cloneNode(true).firstElementChild;

                // Popula o select de índices
                const select = newFaixa.querySelector('.faixa-indice');
                select.innerHTML = '<option value="">Selecione...</option>';
                indiceOptions.forEach(opt => select.add(new Option(opt, opt)));

                // Preenche os dados da faixa com valores padrão para garantir a validação
                select.value = data.indice || (indiceOptions.length > 0 ? indiceOptions[0] : '');
                newFaixa.querySelector('.faixa-data-inicio').value = data.data_inicio || today;
                newFaixa.querySelector('.faixa-data-fim').value = data.data_fim || today;
                newFaixa.querySelector('.faixa-juros-tipo').value = data.juros_tipo || 'NENHUM';
                newFaixa.querySelector('.faixa-juros-taxa').value = this.utils.formatBRL(data.juros_taxa_mensal || 0);
                newFaixa.querySelector('.faixa-pro-rata').checked = data.pro_rata !== false;
                newFaixa.querySelector('.faixa-selic-exclusiva').checked = data.modo_selic_exclusiva === true;

                parcelaCard.querySelector('.faixas-container').appendChild(newFaixa);
            },

            /**
             * Remove um elemento (parcela ou faixa) da tela.
             * @param {HTMLElement} elementToRemove - O elemento a ser removido.
             */
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

            // Demais funções (gatherData, simulateCalculation, etc.) permanecem aqui...
            // O código delas não precisa ser alterado.
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
                if (!this.validateStep(2)) return;

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

                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.message || `Erro ${response.status}`);
                    }

                    const result = await response.json();

                    if (result.status === 'success') {
                        this.state.lastResultData = result.data;
                        this.renderResults(result.data);
                    } else {
                        throw new Error(result.message || "Ocorreu um erro desconhecido no cálculo.");
                    }
                } catch (error) {
                     this.elements.resultadoContainer.innerHTML = `<div class="alert alert-danger"><strong>Erro:</strong> ${error.message}</div>`;
                }
            },

            renderResults(data) {
                const f = (val, symbol) => this.utils.formatBRL(val, symbol);
                let html = `
                    <h4 class="mb-3">Resumo Geral</h4>
                    <table class="table table-sm table-bordered">
                        <tbody>
                            <tr><td>(+) Valor Principal Original</td><td class="text-end">${f(data.resumo.principal, true)}</td></tr>
                            <tr><td>(+) Correção Monetária</td><td class="text-end">${f(data.resumo.correcao, true)}</td></tr>
                            <tr><td>(+) Juros</td><td class="text-end">${f(data.resumo.juros, true)}</td></tr>
                            <tr class="table-primary fw-bold"><td>(=) Total Geral</td><td class="text-end">${f(data.resumo.total_geral, true)}</td></tr>
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
                                    <td class="text-end">${f(p.valor_original, true)}</td>
                                    <td class="text-end">${f(p.correcao_total, true)}</td>
                                    <td class="text-end">${f(p.juros_total, true)}</td>
                                    <td class="text-end fw-bold">${f(p.valor_final, true)}</td>
                                </tr>
                            </tbody>
                        </table>
                        </div>
                    </div>
                    `;
                });

                html += `<div class="mt-4"><h5 class="mb-3">Memória de Cálculo Detalhada (Texto)</h5><pre class="bg-light p-3 rounded small"><code>${data.memoria_texto}</code></pre></div>`;

                this.elements.resultadoContainer.innerHTML = html;
            },

            setupPdfForm() {
                this.elements.formPDF.method = 'POST';
                this.elements.formPDF.action = typeof exportPdfUrl !== 'undefined' ? exportPdfUrl : '#';
                this.elements.formPDF.target = '_blank';
                this.elements.formPDF.innerHTML = `
                    <input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}">
                    <input type="hidden" name="payload">
                `;
                document.body.appendChild(this.elements.formPDF);
            },

            // 5. Utilitários (Funções de ajuda)
            utils: {
                formatBRL(value, withSymbol = false) {
                    const number = parseFloat(value) || 0;
                    const options = {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                    };
                    if (withSymbol) {
                        options.style = 'currency';
                        options.currency = 'BRL';
                    }
                    return number.toLocaleString('pt-BR', options);
                },
                parseBRL(str) {
                    if (typeof str !== 'string' || !str) return 0.00;
                    const number = str.replace(/[R$\s.]/g, '').replace(',', '.');
                    const parsed = parseFloat(number);
                    return isNaN(parsed) ? 0.00 : parsed;
                },
            },

            // 6. Bind de Eventos (Conexão das funções com os cliques e inputs)
            bindEvents() {
                // Navegação principal
                this.elements.btnNext.addEventListener('click', () => {
                    if (this.validateStep(this.state.currentStep)) {
                        this.showStep(this.state.currentStep + 1);
                    }
                });
                this.elements.btnPrev.addEventListener('click', () => this.showStep(this.state.currentStep - 1));
                this.elements.btnCalc.addEventListener('click', () => this.simulateCalculation());

                // Usa delegação de eventos para elementos que são criados dinamicamente
                this.elements.wizard.addEventListener('click', (e) => {
                    const button = e.target.closest('button');
                    const link = e.target.closest('a');
                    const target = button || link;

                    if (!target) return;

                    // Ações nos cards de parcela
                    const parcelaCard = target.closest('.parcela-card');
                    if (parcelaCard) {
                        if (target.classList.contains('btn-add-faixa')) this.addFaixa(parcelaCard);
                        if (target.classList.contains('btn-clone-parcela')) this.duplicateParcela(parcelaCard);
                        if (target.classList.contains('btn-remove-parcela')) this.removeElement(parcelaCard);
                    }
                    if (target.classList.contains('btn-remove-faixa')) this.removeElement(target.closest('.faixa-row'));

                    // Ações na sidebar
                    const sidebarItem = target.closest('.list-group-item[data-target-parcela-id]');
                    if (sidebarItem) {
                        e.preventDefault();
                        const id = sidebarItem.dataset.targetParcelaId;
                        this.updateSidebarActive(id);
                        this.elements.parcelasContainer.querySelector(`[data-parcela-id="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }

                    // Ações gerais
                    if (target.id === 'btn-add-parcela') this.addParcela();
                });

                // Eventos de input para atualizar a UI em tempo real
                this.elements.wizard.addEventListener('input', (e) => {
                    const input = e.target;

                    const parcelaCard = input.closest('.parcela-card');
                    if (parcelaCard) {
                        const id = parcelaCard.dataset.parcelaId;
                        const sidebarItem = this.elements.parcelasSidebar.querySelector(`[data-target-parcela-id="${id}"]`);
                        if (sidebarItem) {
                            if (input.classList.contains('parcela-descricao')) {
                                sidebarItem.querySelector('.parcela-title').textContent = input.value || `Parcela ${id}`;
                            }
                            if (input.classList.contains('parcela-valor')) {
                                sidebarItem.querySelector('.parcela-valor-original').textContent = this.utils.formatBRL(this.utils.parseBRL(input.value), true);
                            }
                        }
                    }

                    if (input.classList.contains('faixa-selic-exclusiva')) {
                        const faixaRow = input.closest('.faixa-row');
                        const jurosTipo = faixaRow.querySelector('.faixa-juros-tipo');
                        const jurosTaxa = faixaRow.querySelector('.faixa-juros-taxa');
                        jurosTipo.disabled = input.checked;
                        jurosTaxa.disabled = input.checked;
                        if (input.checked) jurosTipo.value = 'NENHUM';
                    }
                });

                // Evento de formatação ao sair do campo de valor
                this.elements.wizard.addEventListener('blur', (e) => {
                    if (e.target.matches('.parcela-valor, .faixa-juros-taxa')) {
                         const valorNumerico = this.utils.parseBRL(e.target.value);
                         e.target.value = this.utils.formatBRL(valorNumerico, false);
                    }
                }, true);
            },
        };

        // Inicia o Wizard
        Wizard.init();
    });
})();