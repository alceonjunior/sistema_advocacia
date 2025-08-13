/**
 * Script de controle para a Página de Cálculo Judicial (Versão Simplificada)
 * Gerencia a manipulação de parcelas e faixas, e a chamada da API de cálculo.
 *
 * Versão: 5.0.0 - Corrigido Erro de Inicialização
 * Autor: Gemini Senior Dev
 */
document.addEventListener("DOMContentLoaded", () => {
    const Calculadora = {
        // Deixamos a declaração dos elementos vazia aqui.
        elements: {},

        state: {
            parcelaCounter: 0,
            faixaCounter: 0,
            lastResultPayload: null,
        },

        // **CORREÇÃO PRINCIPAL**: Criamos uma função para popular os elementos.
        // Esta função será chamada dentro de init(), garantindo que o DOM está pronto.
        setupElements() {
            this.elements = {
                container: document.getElementById('calculadora-container'),
                btnCalcular: document.getElementById('btn-calcular'),
                resultadoWrapper: document.getElementById('resultado-wrapper'),
                resultadoContainer: document.getElementById('resultado-container'),
                parcelasContainer: document.getElementById('parcelas-container'),
                parcelasSidebar: document.getElementById('parcelas-sidebar'),
                parcelasPlaceholder: document.getElementById('parcelas-placeholder'),
            };
        },

        init() {
            // 1. Popula o objeto de elementos. Agora é seguro fazer isso.
            this.setupElements();

            // 2. Aborta se o container principal não existir.
            if (!this.elements.container) {
                 console.error("Container principal da calculadora não encontrado.");
                 return;
            }

            // 3. O resto da inicialização continua.
            this.bindEvents();
            this.addParcela(); // Adiciona a primeira parcela ao carregar.
        },

        utils: {
            formatBRL(value, withSymbol = false) {
                const number = parseFloat(value) || 0;
                const options = { minimumFractionDigits: 2, maximumFractionDigits: 2 };
                if (withSymbol) {
                    options.style = 'currency';
                    options.currency = 'BRL';
                }
                return number.toLocaleString('pt-BR', options);
            },
            parseBRL(str) {
                if (typeof str !== 'string' || !str) return 0.00;
                const number = str.replace(/[R$\s.]/g, '').replace(',', '.');
                return isNaN(parseFloat(number)) ? 0.00 : parseFloat(number);
            },
        },

        addParcela(data = {}) {
            this.state.parcelaCounter++;
            const newId = this.state.parcelaCounter;
            const today = new Date().toISOString().split('T')[0];

            const cardTemplate = document.getElementById('template-parcela-card');
            if (!cardTemplate) {
                console.error("Template #template-parcela-card não encontrado.");
                return;
            }

            const newCard = cardTemplate.content.cloneNode(true).firstElementChild;
            newCard.dataset.parcelaId = newId;

            const title = data.descricao || `Parcela ${newId}`;
            newCard.querySelector('.parcela-title').textContent = title;
            newCard.querySelector('.parcela-descricao').value = title;
            newCard.querySelector('.parcela-valor').value = this.utils.formatBRL(data.valor_original || 1000);
            newCard.querySelector('.parcela-data').value = data.data_evento || today;

            this.elements.parcelasContainer.appendChild(newCard);
            this.elements.parcelasPlaceholder.style.display = 'none';

            this.addFaixa(newCard, { data_inicio: data.data_evento || today });
        },

        addFaixa(parcelaCard, data = {}) {
            this.state.faixaCounter++;
            const today = new Date().toISOString().split('T')[0];
            const faixaTemplate = document.getElementById('template-faixa-row');
            if (!faixaTemplate) {
                 console.error("Template #template-faixa-row não encontrado.");
                 return;
            }

            const newFaixa = faixaTemplate.content.cloneNode(true).firstElementChild;

            const select = newFaixa.querySelector('.faixa-indice');
            select.innerHTML = '<option value="">Selecione...</option>';
            if (typeof indiceOptions !== 'undefined') {
                indiceOptions.forEach(opt => select.add(new Option(opt, opt)));
                select.value = data.indice || (indiceOptions.length > 0 ? indiceOptions[0] : '');
            }

            newFaixa.querySelector('.faixa-data-inicio').value = data.data_inicio || today;
            newFaixa.querySelector('.faixa-data-fim').value = data.data_fim || today;

            parcelaCard.querySelector('.faixas-container').appendChild(newFaixa);
        },

        removeElement(element) {
            element.remove();
            if (this.elements.parcelasContainer.querySelectorAll('.parcela-card').length === 0) {
                this.elements.parcelasPlaceholder.style.display = 'block';
            }
        },

        async handleCalcular() {
            const payload = this.gatherData();
            if (payload.parcelas.length === 0) {
                alert("Adicione pelo menos uma parcela para calcular.");
                return;
            }

            this.state.lastResultPayload = payload;
            this.elements.resultadoContainer.innerHTML = `<div class="text-center p-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-2 text-muted">Calculando, por favor aguarde...</p></div>`;
            this.elements.resultadoWrapper.style.display = 'block';

            try {
                const response = await fetch(simularApiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify(payload)
                });
                if (!response.ok) throw new Error((await response.json()).message || 'Erro no servidor');

                const result = await response.json();
                if (result.status !== 'success') throw new Error(result.message);

                this.renderResults(result.data);
            } catch (error) {
                this.elements.resultadoContainer.innerHTML = `<div class="alert alert-danger"><strong>Erro ao calcular:</strong> ${error.message}</div>`;
            } finally {
                this.elements.resultadoWrapper.scrollIntoView({ behavior: 'smooth' });
            }
        },

        gatherData() {
            const payload = { parcelas: [] };
            this.elements.parcelasContainer.querySelectorAll('.parcela-card').forEach(pCard => {
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
                    });
                });
                payload.parcelas.push(parcela);
            });
            return payload;
        },

        renderResults(data) {
            const f = this.utils.formatBRL;
            let html = `<h4 class="mb-3">Resumo Geral</h4>
                        <table class="table table-sm table-bordered">
                            <tbody>
                                <tr><td>(+) Valor Principal Original</td><td class="text-end">${f(data.resumo.principal, true)}</td></tr>
                                <tr><td>(+) Correção Monetária</td><td class="text-end">${f(data.resumo.correcao, true)}</td></tr>
                                <tr><td>(+) Juros</td><td class="text-end">${f(data.resumo.juros, true)}</td></tr>
                                <tr class="table-primary fw-bold"><td>(=) Total Geral</td><td class="text-end">${f(data.resumo.total_geral, true)}</td></tr>
                            </tbody>
                        </table>
                        <h4 class="mt-4 mb-3">Detalhamento por Parcela</h4>`;
            data.parcelas.forEach((p, index) => {
                html += `<div class="card mb-3">
                            <div class="card-header bg-light"><strong>Parcela ${index + 1}: ${p.descricao}</strong></div>
                            <div class="table-responsive">
                            <table class="table table-striped table-hover mb-0">
                                <thead><tr><th>Memória de Cálculo</th><th class="text-end">Valor Original</th><th class="text-end">Correção</th><th class="text-end">Juros</th><th class="text-end">Valor Final</th></tr></thead>
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
                        </div>`;
            });
            html += `<div class="mt-4"><h5 class="mb-3">Memória de Cálculo Detalhada (Texto)</h5><pre class="bg-light p-3 rounded small"><code>${data.memoria_texto}</code></pre></div>`;
            this.elements.resultadoContainer.innerHTML = html;
        },

        bindEvents() {
            if (this.elements.btnCalcular) {
                this.elements.btnCalcular.addEventListener('click', () => this.handleCalcular());
            }

            if (this.elements.container) {
                this.elements.container.addEventListener('click', (e) => {
                    const target = e.target.closest('button');
                    if (!target) return;

                    if (target.id === 'btn-add-parcela') {
                        this.addParcela();
                    } else if (target.classList.contains('btn-add-faixa')) {
                        this.addFaixa(target.closest('.parcela-card'));
                    } else if (target.classList.contains('btn-remove-parcela')) {
                        this.removeElement(target.closest('.parcela-card'));
                    } else if (target.classList.contains('btn-remove-faixa')) {
                        this.removeElement(target.closest('.faixa-row'));
                    }
                });

                this.elements.container.addEventListener('blur', (e) => {
                    if (e.target.matches('.parcela-valor, .faixa-juros-taxa')) {
                        e.target.value = this.utils.formatBRL(this.utils.parseBRL(e.target.value));
                    }
                }, true);
            }
        },
    };

    Calculadora.init();
});