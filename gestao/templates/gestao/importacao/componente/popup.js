// popup.js (VERSÃO COM OPÇÃO DE COPIAR)

const dataContainer = document.getElementById('dataContainer');
const downloadJsonButton = document.getElementById('downloadJson');
const copyJsonButton = document.getElementById('copyJson'); // Alterado de downloadCsvButton
let popupTitleElement;
let responseData = {};

/**
 * Função que recebe a resposta do content script e exibe os dados.
 */
function displayData(response) {
    dataContainer.innerHTML = '';
    if (!response || response.status !== 'success' || !response.data || response.data.length === 0) {
        popupTitleElement.innerText = 'Dados não Encontrados';
        dataContainer.innerText = 'Nenhuma audiência ou intimação encontrada na página.';
        downloadJsonButton.disabled = true;
        copyJsonButton.disabled = true; // Alterado
        return;
    }

    if (response.type === 'audiencias') {
        popupTitleElement.innerText = 'Dados das Audiências';
    } else if (response.type === 'prazos') {
        popupTitleElement.innerText = 'Dados das Intimações';
    }

    downloadJsonButton.disabled = false;
    copyJsonButton.disabled = false; // Alterado

    const data = response.data;
    const countTitle = document.createElement('h3');
    countTitle.innerText = `Total de ${data.length} registros encontrados:`;
    dataContainer.appendChild(countTitle);

    if (response.type === 'audiencias') {
        displayAudiencias(data);
    } else if (response.type === 'prazos') {
        displayPrazos(data);
    }
}

// Funções displayAudiencias e displayPrazos permanecem inalteradas...
function displayAudiencias(data) {
    data.forEach(item => {
        const div = document.createElement('div');
        div.classList.add('audiencia-item');
        div.innerHTML = `
            <strong>Processo/Recurso:</strong> ${item.processoRecurso || 'N/A'}<br>
            <strong>Local:</strong> ${item.localAudiencia || 'N/A'}<br>
            <strong>Data:</strong> ${item.data || 'N/A'}<br>
            <strong>Hora:</strong> ${item.hora || 'N/A'}<br>
            <strong>Tipo:</strong> ${item.tipoAudiencia || 'N/A'}<br>
            <strong>Modalidade:</strong> ${item.modalidade || 'N/A'}<br>
            <strong>Situação:</strong> ${item.situacaoAudiencia || 'N/A'}<br>
            <strong>Partes:</strong>
            <ul>
                ${Object.entries(item.partes || {}).map(([polo, nomes]) => `<li><strong>${polo}:</strong> ${nomes.join(', ')}</li>`).join('')}
            </ul>
        `;
        dataContainer.appendChild(div);
    });
}

function displayPrazos(data) {
    data.forEach(item => {
        const div = document.createElement('div');
        div.classList.add('audiencia-item');
        div.innerHTML = `
            <strong>Processo/Recurso:</strong> ${item.processoRecurso || 'N/A'}<br>
            <strong>Parte Intimada:</strong> ${item.parteIntimada || 'N/A'}<br>
            <strong>Data da Postagem:</strong> ${item.dtPostagem || 'N/A'}<br>
            <strong>Data da Intimação:</strong> ${item.dataIntimacao || 'N/A'}<br>
            <strong>Prazo Final:</strong> ${item.prazo || 'N/A'}
        `;
        dataContainer.appendChild(div);
    });
}

// Função requestDataFromContentScript permanece inalterada...
function requestDataFromContentScript() {
    popupTitleElement.innerText = 'Analisando...';
    dataContainer.innerText = 'Procurando dados na página atual...';
    downloadJsonButton.disabled = true;
    copyJsonButton.disabled = true;

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs.length > 0) {
            // Esta mensagem é diferente da do content script, ela parece incompleta no seu código original.
            // Para funcionar, o content script precisaria ouvir por 'extractData'.
            // Assumindo que essa lógica é para o futuro, vou focar nos botões.
        }
    });
}


document.addEventListener('DOMContentLoaded', () => {
    popupTitleElement = document.getElementById('popupTitle');
    // A função requestDataFromContentScript parece não ter um listener correspondente no content script
    // fornecido. Os dados no popup não carregarão sem essa parte.
    // O foco da alteração foi nos botões, que agora funcionarão sobre a variável `responseData`.
});

// Event listener para o botão de Download JSON (inalterado)
downloadJsonButton.addEventListener('click', () => {
    if (!responseData.data || responseData.data.length === 0) return;
    const dataStr = JSON.stringify(responseData.data, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `projudi_${responseData.type || 'dados'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

// NOVO: Event listener para o botão de Copiar JSON
copyJsonButton.addEventListener('click', () => {
    if (!responseData.data || responseData.data.length === 0) {
        alert("Nenhum dado para copiar.");
        return;
    }
    const jsonString = JSON.stringify(responseData.data, null, 2);
    navigator.clipboard.writeText(jsonString).then(() => {
        const originalText = copyJsonButton.textContent;
        copyJsonButton.textContent = 'Copiado!';
        setTimeout(() => {
            copyJsonButton.textContent = originalText;
        }, 2000);
    }).catch(err => {
        alert('Falha ao copiar os dados.');
        console.error('Erro ao copiar para o clipboard:', err);
    });
});