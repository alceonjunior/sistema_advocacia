// background.js (VERSÃO AJUSTADA)

chrome.runtime.onInstalled.addListener(() => {
  console.log("Extrator Projudi instalado.");
});

// Ouve as mensagens do content script para iniciar o download do arquivo JSON.
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'download_json') {
        // Prepara e inicia o download do JSON
        const jsonContent = JSON.stringify(request.data, null, 2);
        const jsonUrl = 'data:application/json;charset=utf-8,' + encodeURIComponent(jsonContent);

        chrome.downloads.download({
            url: jsonUrl,
            filename: `projudi_${request.type}_pagina_atual.json`,
            saveAs: true
        });
    }
    // Retorna true para indicar que a resposta pode ser assíncrona (boa prática).
    return true;
});