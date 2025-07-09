import requests
import json

def consultar_processo_tjpr(numero_processo_completo):
    """
    Consulta um processo na API do TJPR.
    O número do processo deve estar no formato com pontuação.
    """
    print(f"Iniciando consulta para o processo: {numero_processo_completo}...")

    # 1. Preparação dos Dados
    url = "https://www.tjpr.jus.br/documents/d/planejamento/processos_tjpr?download=true"
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Python-Requests-Client' # Boa prática para identificar o cliente
    }
    # Remove toda a pontuação para enviar na requisição
    numero_processo_limpo = ''.join(filter(str.isdigit, numero_processo_completo))

    # 2. Construção da Requisição (JSON Body)
    body = {
        "query": {
            "term": {
                "Processos": numero_processo_limpo
            }
        }
    }

    print(f"Número sem pontuação enviado: {numero_processo_limpo}")
    print("Enviando requisição POST para a API do TJPR...")

    # 3. Execução e Análise
    try:
        response = requests.post(url, headers=headers, data=json.dumps(body), timeout=30)
        # Lança um erro para status HTTP 4xx ou 5xx
        response.raise_for_status()

        # A API retorna uma lista de resultados em JSON
        resultados = response.json()

        if not resultados:
            print("\n--- RESULTADO ---")
            print("A API retornou uma resposta vazia. O processo pode não existir, ser sigiloso, ou ter sido arquivado antes de 2022.")
            return

        # Filtra a resposta para garantir que o processo é exatamente o que foi solicitado
        resultado_final = [p for p in resultados if p.get("Processos") == numero_processo_limpo]

        print("\n--- RESULTADO ---")
        if resultado_final:
            print("Processo encontrado:")
            # Imprime o JSON de forma legível
            print(json.dumps(resultado_final, indent=2, ensure_ascii=False))
        else:
            print(f"O processo {numero_processo_limpo} não foi encontrado na resposta, embora a API tenha retornado outros dados.")

    except requests.exceptions.HTTPError as http_err:
        print(f"\nERRO: Ocorreu um erro HTTP: {http_err}")
        print(f"Status Code: {response.status_code}")
        print(f"Resposta do servidor: {response.text}")
    except requests.exceptions.RequestException as err:
        print(f"\nERRO: Falha na comunicação com o servidor: {err}")
    except json.JSONDecodeError:
        print("\nERRO: Falha ao decodificar a resposta JSON.")
        print(f"A resposta recebida não é um JSON válido: {response.text}")


# --- INÍCIO DA EXECUÇÃO ---
# Processo a ser consultado
processo_alvo = "0007033-89.2025.8.16.0019"
consultar_processo_tjpr(processo_alvo)