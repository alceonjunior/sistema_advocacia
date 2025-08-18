document.addEventListener('DOMContentLoaded', () => {
    // Estado da Aplicação
    let parcelas = [];
    let history = []; // Para o "undo"
    let autoPreviewTimer;
    const INDICES_CATALOGO = JSON.parse(document.getElementById('indices-catalogo-data').textContent);

    // Seletores do DOM
    const container = document.getElementById('calculo-pro-container');
    const tableBody = document.querySelector('#parcelas-table tbody');
    const emptyState = document.getElementById('empty-state');
    const statusText = document.getElementById('status-text');

    // Funções de Utilidade
    const formatCurrency = (value) => {
        const num = parseFloat(value) || 0;
        return num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };

    const parseCurrency = (value) => {
        if (typeof value !== 'string') return '0.00';
        return value.replace(/\./g, '').replace(',', '.') || '0.00';
    };

    const formatDate = (isoDate) => {
        if (!isoDate || !/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) return '';
        const [year, month, day] = isoDate.split('-');
        return `${day}/${month}/${year}`;
    };

    const parseDate = (brDate) => {
        if (!brDate || !/^\d{2}\/\d{2}\/\d{4}$/.test(brDate)) return '';
        const [day, month, year] = brDate.split('/');
        return `${year}-${month}-${day}`;
    };

    const updateStatus = (text, isError = false) => {
        statusText.textContent = text;
        statusText.classList.toggle('text-danger', isError);
        statusText.classList.toggle('text-muted', !isError);
    };

    // Renderização da Tabela
    const renderTable = () => {
        tableBody.innerHTML = '';
        emptyState.style.display = parcelas.length === 0 ? 'block' : 'none';

        parcelas.forEach((p, index) => {
            const template = document.getElementById('parcela-row-template').content.cloneNode(true);
            const row = template.querySelector('tr');
            row.dataset.id = p.id;

            row.querySelector('.row-index').textContent = index + 1;
            row.querySelector('[data-field="descricao"]').textContent = p.descricao;
            row.querySelector('[data-field="vencimento"]').textContent = formatDate(p.vencimento);
            row.querySelector('[data-field="principal"]').textContent = formatCurrency(p.principal);
            row.querySelector('[data-field="juros"]').textContent = formatCurrency(p.juros);
            row.querySelector('[data-field="multa"]').textContent = formatCurrency(p.multa);

            const indiceSelect = row.querySelector('[data-field="indice"]');
            INDICES_CATALOGO.indices.forEach(idx => {
                indiceSelect.add(new Option(idx.label, idx.key));
            });
            indiceSelect.value = p.indice;

            tableBody.appendChild(row);
        });
        updateStatus(`Pronto. ${parcelas.length} parcela(s).`);
    };

    // Lógica de Estado (Adicionar, Atualizar, etc.)
    const saveState = () => {
        history.push(JSON.stringify(parcelas));
        if (history.length > 2) history.shift(); // Mantém apenas 2 níveis de histórico
    };

    const addParcela = () => {
        saveState();
        const newId = `P${Date.now()}`;
        parcelas.push({
            id: newId,
            descricao: `Nova Parcela`,
            vencimento: new Date().toISOString().split('T')[0],
            principal: '0.00',
            indice: 'IPCA',
            juros: '1.00',
            multa: '2.00',
        });
        renderTable();
        triggerAutoPreview();
    };

    const updateParcelaField = (id, field, value) => {
        const parcela = parcelas.find(p => p.id === id);
        if (!parcela) return;

        saveState();

        if (['principal', 'juros', 'multa'].includes(field)) {
            parcela[field] = parseCurrency(value);
        } else if (field === 'vencimento') {
            parcela[field] = parseDate(value);
        } else {
            parcela[field] = value;
        }
        triggerAutoPreview();
    };

    // API Calls
    const triggerAutoPreview = () => {
        clearTimeout(autoPreviewTimer);
        updateStatus('Calculando...');
        autoPreviewTimer = setTimeout(async () => {
            const payload = {
                parametros: {}, // Adicionar parâmetros globais se houver
                parcelas: parcelas.map(p => ({...p, principal: parseCurrency(p.principal)}))
            };
            try {
                const response = await fetch('/api/calculos/preview/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();
                if (result.ok) {
                    updateSummary(result.totais);
                    updateParcelasValores(result.parcelas);
                    updateStatus(`Prévia atualizada.`);
                } else {
                    updateStatus(result.erro || 'Erro na prévia.', true);
                }
            } catch (error) {
                updateStatus('Erro de comunicação.', true);
            }
        }, 400);
    };

    // Atualização da UI pós-cálculo
    const updateSummary = (totais) => {
        document.getElementById('summary-principal').textContent = `R$ ${formatCurrency(totais.principal)}`;
        document.getElementById('summary-correcao').textContent = `R$ ${formatCurrency(totais.correcao)}`;
        document.getElementById('summary-juros').textContent = `R$ ${formatCurrency(totais.juros)}`;
        document.getElementById('summary-multa').textContent = `R$ ${formatCurrency(totais.multa)}`;
        document.getElementById('summary-total').textContent = `R$ ${formatCurrency(totais.atualizado)}`;
    };

    const updateParcelasValores = (parcelasResult) => {
        parcelasResult.forEach(res => {
            const row = tableBody.querySelector(`tr[data-id="${res.id}"]`);
            if(row) {
                row.querySelector('.valor-atualizado').textContent = `R$ ${formatCurrency(res.atualizado)}`;
            }
        });
    };

    // Event Listeners
    document.getElementById('btn-add-parcela').addEventListener('click', addParcela);

    tableBody.addEventListener('focusout', (e) => {
        if (e.target.matches('[contenteditable="true"]')) {
            const row = e.target.closest('tr');
            const id = row.dataset.id;
            const field = e.target.dataset.field;
            updateParcelaField(id, field, e.target.textContent);
        }
    });

    tableBody.addEventListener('change', (e) => {
        if (e.target.matches('select[data-field="indice"]')) {
            const row = e.target.closest('tr');
            const id = row.dataset.id;
            updateParcelaField(id, 'indice', e.target.value);
        }
    });

    // Inicialização
    container.style.opacity = 1;
    renderTable();
});