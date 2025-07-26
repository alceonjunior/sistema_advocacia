// contentScript.js (VERSÃO FINAL COM FALLBACK PARA COPIAR)

/**
 * Função principal que roda quando o script é carregado no frame.
 * Decide se deve injetar o botão de extração.
 */
function initialize() {
    // Evita injetar o botão múltiplas vezes
    if (document.getElementById('extratorProjudiButton')) {
        return;
    }

    let pageType = 'unknown';
    let extractFunction = null;

    if (document.forms['intimacaoAdvogadoForm']) {
        pageType = 'prazos';
        extractFunction = extractPrazosData;
    } else if (document.forms['audienciaForm']) {
        pageType = 'audiencias';
        extractFunction = extractAudienciasData;
    }

    if (pageType !== 'unknown') {
        console.log(`Página de ${pageType} detectada. Injetando botão.`);
        injectActionButtton(pageType, extractFunction);
    }
}

/**
 * Cria e injeta o botão "Salvar Dados da Página" na interface do Projudi.
 * @param {string} pageType - O tipo de página ('audiencias' ou 'prazos').
 * @param {Function} extractFunction - A função de extração a ser usada.
 */
function injectActionButtton(pageType, extractFunction) {
    const targetLocation = document.querySelector('.buttonBar .buttons');
    if (!targetLocation) {
        console.error("Não foi possível encontrar o local para injetar o botão.");
        return;
    }

    const actionButton = document.createElement('input');
    actionButton.id = 'extratorProjudiButton';
    actionButton.type = 'button';
    actionButton.value = 'Salvar Dados da Página';
    actionButton.className = 'button';
    actionButton.style.marginLeft = '10px';
    actionButton.style.backgroundColor = '#2a643b';
    actionButton.style.color = 'white';

    actionButton.onclick = () => {
        actionButton.disabled = true;
        actionButton.value = 'Extraindo...';

        try {
            const data = extractFunction();

            if (data && data.length > 0) {
                actionButton.value = `Dados extraídos!`;
                showChoiceModal(pageType, data);
            } else {
                actionButton.value = 'Nenhum dado encontrado.';
            }
        } catch (error) {
            console.error('Erro na extração:', error);
            actionButton.value = 'Erro ao extrair!';
        }

        setTimeout(() => {
            actionButton.disabled = false;
            actionButton.value = 'Salvar Dados da Página';
        }, 4000);
    };

    targetLocation.appendChild(actionButton);
}

/**
 * Função de fallback para copiar texto para a área de transferência, usando o método legado.
 * @param {string} text - O texto a ser copiado.
 * @returns {boolean} - Retorna true se a cópia foi bem-sucedida.
 */
function copyTextToClipboardFallback(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    // Torna o elemento invisível e o remove da viewport para não atrapalhar a interface
    textArea.style.position = 'fixed';
    textArea.style.top = '-9999px';
    textArea.style.left = '-9999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        const successful = document.execCommand('copy');
        return successful;
    } catch (err) {
        console.error('Erro no fallback de cópia:', err);
        return false;
    } finally {
        document.body.removeChild(textArea);
    }
}


/**
 * Exibe um modal com as opções de salvar ou copiar os dados.
 * @param {string} type - O tipo de dados ('audiencias' ou 'prazos').
 * @param {Array} data - Os dados extraídos.
 */
function showChoiceModal(type, data) {
    // Remove modal anterior, se existir, para evitar duplicação
    const existingModal = document.getElementById('projudiExtractorModal');
    if (existingModal) existingModal.remove();

    // Cria o container do modal
    const modal = document.createElement('div');
    modal.id = 'projudiExtractorModal';
    modal.style.position = 'fixed';
    modal.style.top = '50%';
    modal.style.left = '50%';
    modal.style.transform = 'translate(-50%, -50%)';
    modal.style.backgroundColor = 'white';
    modal.style.border = '1px solid #ccc';
    modal.style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)';
    modal.style.padding = '25px';
    modal.style.zIndex = '10001';
    modal.style.borderRadius = '8px';
    modal.style.fontFamily = 'Arial, sans-serif';

    // Cria o fundo escurecido (overlay)
    const overlay = document.createElement('div');
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.width = '100%';
    overlay.style.height = '100%';
    overlay.style.backgroundColor = 'rgba(0,0,0,0.5)';
    overlay.style.zIndex = '10000';
    overlay.onclick = () => {
        modal.remove();
        overlay.remove();
    };

    // Conteúdo do Modal
    modal.innerHTML = `<h3 style="margin-top:0; padding-bottom:10px; border-bottom:1px solid #eee;">Ação Desejada</h3><p>Foram encontrados ${data.length} registros. O que você deseja fazer?</p>`;

    // Botão Salvar JSON
    const saveBtn = document.createElement('button');
    saveBtn.textContent = 'Salvar JSON';
    saveBtn.className = 'button';
    saveBtn.onclick = () => {
        chrome.runtime.sendMessage({ action: 'download_json', type: type, data: data });
        overlay.click(); // Fecha o modal
    };

    // Botão Copiar JSON
    const copyBtn = document.createElement('button');
    copyBtn.textContent = 'Copiar para Clipboard';
    copyBtn.className = 'button';
    copyBtn.style.marginLeft = '10px';

    copyBtn.onclick = () => {
        const jsonString = JSON.stringify(data, null, 2);

        // Tenta a API moderna de Clipboard primeiro
        navigator.clipboard.writeText(jsonString).then(() => {
            copyBtn.textContent = 'Copiado com Sucesso!';
            copyBtn.style.backgroundColor = '#2a643b';
            copyBtn.style.color = 'white';
            setTimeout(() => overlay.click(), 1500);
        }).catch(err => {
            console.warn('API de Clipboard moderna falhou. Tentando método alternativo.', err);
            // Se falhar, tenta o método de fallback
            if (copyTextToClipboardFallback(jsonString)) {
                copyBtn.textContent = 'Copiado com Sucesso!';
                copyBtn.style.backgroundColor = '#2a643b';
                copyBtn.style.color = 'white';
                setTimeout(() => overlay.click(), 1500);
            } else {
                // Se ambos os métodos falharem, exibe o erro final
                copyBtn.textContent = 'Erro ao Copiar!';
                copyBtn.style.backgroundColor = '#d9534f'; // Cor de erro
                copyBtn.style.color = 'white';
                console.error('Falha ao copiar em ambos os métodos.');
            }
        });
    };

    modal.appendChild(saveBtn);
    modal.appendChild(copyBtn);
    document.body.appendChild(overlay);
    document.body.appendChild(modal);
}

// Roda a inicialização após um pequeno delay para garantir que a página esteja pronta.
setTimeout(initialize, 1000);


// ===================================================================
// FUNÇÕES EXTRATORAS DE DADOS
// (Estas funções não foram alteradas)
// ===================================================================
function extractAudienciasData() {
    const tableBody = document.querySelector('table.resultTable tbody');
    if (!tableBody) return [];
    const audiencias = [];
    const rows = tableBody.querySelectorAll('tr.even, tr.odd');
    rows.forEach(row => {
        const cols = row.querySelectorAll(':scope > td');
        if (cols.length >= 7) {
            try {
                const processoRecurso = (cols[0]?.querySelector('em')?.innerText || '').trim();
                const partesElem = cols[1]; const polos = {};
                if (partesElem) { partesElem.querySelectorAll('table.form tr').forEach(parteRow => { const labelElem = parteRow.querySelector('td:first-child font'); const valueElem = parteRow.querySelector('td:last-child ul'); if (labelElem && valueElem) { let label = (labelElem.innerText || '').trim().replace(':', ''); let values = Array.from(valueElem.querySelectorAll('li')).map(li => (li.innerText || '').trim()); if (label) polos[label] = values; } }); }
                const localAudiencia = (cols[2]?.innerText || '').trim();
                const dataHoraString = (cols[3]?.innerText || '').trim();
                let data = '', hora = '';
                if (dataHoraString.includes(' ')) { const parts = dataHoraString.split(' ', 2); data = parts[0] || ''; hora = parts[1] || ''; } else { data = dataHoraString; }
                const tipoAudiencia = (cols[4]?.innerText || '').trim();
                const modalidade = (cols[5]?.innerText || '').trim();
                const situacaoAudiencia = (cols[6]?.innerText || '').trim();
                audiencias.push({ processoRecurso, partes: polos, localAudiencia, data, hora, tipoAudiencia, modalidade, situacaoAudiencia });
            } catch (e) { console.error("Erro ao processar linha de audiência:", row, e); }
        }
    });
    return audiencias;
}

function extractPrazosData() {
    const tableBody = document.querySelector('table.resultTable tbody');
    if (!tableBody) return [];
    const prazos = [];
    const rows = tableBody.querySelectorAll('tr.even, tr.odd');
    rows.forEach(row => {
        const cols = row.querySelectorAll(':scope > td');
        if (cols.length >= 7) {
            try {
                const processoRecurso = (cols[1]?.querySelector('em')?.innerText || '').trim();
                const parteIntimada = (cols[2]?.innerText || '').trim();
                const dtPostagem = (cols[3]?.innerText || '').trim();
                const dataIntimacao = (cols[4]?.innerText || '').trim();
                const prazo = (cols[5]?.innerText || '').trim();
                prazos.push({ processoRecurso, parteIntimada, dtPostagem, dataIntimacao, prazo });
            } catch (e) { console.error("Erro ao processar linha de prazo:", row, e); }
        }
    });
    return prazos;
}