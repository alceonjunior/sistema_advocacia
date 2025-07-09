# gestao/nfse_service.py
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from django.conf import settings
from .models import Servico, EscritorioConfiguracao, NotaFiscalServico, LancamentoFinanceiro


class NFSEService:
    """
    Serviço para lidar com a geração e envio de RPS para conversão em NFS-e.
    """

    def __init__(self):
        # Em um cenário real, estas URLs viriam do settings.py
        self.URL_HOMOLOGACAO = "https://url.da.prefeitura.para/teste/ws"  # Substituir pela URL real de teste
        self.escritorio = EscritorioConfiguracao.objects.first()

    def _construir_xml_rps(self, servico, lancamento):
        """
        Constrói o payload XML para um RPS (Recibo Provisório de Serviços)
        seguindo a estrutura do manual da ABRASF.
        """
        # Limpa e formata os dados
        prestador_cnpj = ''.join(filter(str.isdigit, self.escritorio.cnpj or ''))
        tomador_cpf_cnpj = ''.join(filter(str.isdigit, servico.cliente.cpf_cnpj or ''))
        valor_servico = f"{lancamento.valor:.2f}"

        # --- ESTRUTURA XML BASEADA NO MANUAL (PÁGINAS 26-31) ---
        # A tag principal pode variar (Ex: EnviarLoteRpsEnvio, GerarNfseEnvio)
        # Usaremos o envio de RPS síncrono para este exemplo.
        root = ET.Element('GerarNfseEnvio', xmlns="http://www.abrasf.org.br/nfse.xsd")
        rps = ET.SubElement(root, 'Rps')

        # Bloco InfDeclaracaoPrestacaoServico (substituído por InfRps)
        inf_rps = ET.SubElement(rps, 'InfDeclaracaoPrestacaoServico')

        ET.SubElement(inf_rps, 'RpsSubstituido').text = ''  # Não estamos substituindo

        # Bloco Servico
        servico_node = ET.SubElement(inf_rps, 'Servico')
        valores_node = ET.SubElement(servico_node, 'Valores')
        ET.SubElement(valores_node, 'ValorServicos').text = valor_servico
        ET.SubElement(valores_node, 'IssRetido').text = '2'  # 1=Sim, 2=Não

        ET.SubElement(servico_node, 'ItemListaServico').text = servico.codigo_servico_municipal
        ET.SubElement(servico_node, 'Discriminacao').text = servico.descricao
        # Código IBGE da cidade onde o serviço foi prestado (ex: Ponta Grossa)
        ET.SubElement(servico_node, 'CodigoMunicipio').text = '4119905'

        # Bloco Prestador (Emissor)
        prestador_node = ET.SubElement(inf_rps, 'Prestador')
        ET.SubElement(prestador_node, 'Cnpj').text = prestador_cnpj
        ET.SubElement(prestador_node, 'InscricaoMunicipal').text = self.escritorio.inscricao_municipal

        # Bloco Tomador (Cliente)
        tomador_node = ET.SubElement(inf_rps, 'Tomador')
        identificacao_tomador = ET.SubElement(tomador_node, 'IdentificacaoTomador')
        cpf_cnpj_tomador = ET.SubElement(identificacao_tomador, 'CpfCnpj')
        if len(tomador_cpf_cnpj) == 11:
            ET.SubElement(cpf_cnpj_tomador, 'Cpf').text = tomador_cpf_cnpj
        else:
            ET.SubElement(cpf_cnpj_tomador, 'Cnpj').text = tomador_cpf_cnpj

        ET.SubElement(tomador_node, 'RazaoSocial').text = servico.cliente.nome_completo

        endereco_tomador = ET.SubElement(tomador_node, 'Endereco')
        ET.SubElement(endereco_tomador, 'Logradouro').text = servico.cliente.logradouro
        ET.SubElement(endereco_tomador, 'Numero').text = servico.cliente.numero
        ET.SubElement(endereco_tomador, 'Bairro').text = servico.cliente.bairro
        # O código do município do cliente deveria vir do cadastro do cliente
        ET.SubElement(endereco_tomador, 'CodigoMunicipio').text = "CODIGO_IBGE_DO_CLIENTE"
        ET.SubElement(endereco_tomador, 'Uf').text = servico.cliente.estado
        ET.SubElement(endereco_tomador, 'Cep').text = ''.join(filter(str.isdigit, servico.cliente.cep or ''))

        # Retorna o XML como uma string formatada
        return ET.tostring(root, encoding='unicode', method='xml')

    def enviar_rps_para_emissao(self, servico_pk):
        servico = Servico.objects.get(pk=servico_pk)
        lancamento = servico.lancamentos.first()

        if not all([self.escritorio, self.escritorio.cnpj, self.escritorio.inscricao_municipal]):
            return {'status': 'erro',
                    'mensagem': 'Dados do escritório (emissor) incompletos. Verifique o CNPJ e a Inscrição Municipal no cadastro.'}
        if not all([servico.cliente, servico.cliente.cpf_cnpj, servico.cliente.logradouro]):
            return {'status': 'erro', 'mensagem': 'Dados do cliente (destinatário) incompletos.'}
        if not lancamento:
            return {'status': 'erro', 'mensagem': 'Serviço não possui um lançamento financeiro para gerar a nota.'}
        if not servico.codigo_servico_municipal:
            return {'status': 'erro', 'mensagem': 'O "Código do Serviço (LC 116/03)" é obrigatório para emissão.'}

        xml_rps = self._construir_xml_rps(servico, lancamento)

        # =======================================================
        # PONTO CRÍTICO: ASSINATURA DIGITAL
        # =======================================================
        # Em um ambiente real, o XML acima seria assinado aqui usando uma biblioteca
        # como 'signxml' ou similar, e o certificado digital A1 ou A3 da empresa.
        # Exemplo conceitual:
        # from signxml import XMLSigner
        # signed_xml = XMLSigner(...).sign(xml_rps, cert=CERT_PATH, key=KEY_PATH)
        # =======================================================

        nf = NotaFiscalServico.objects.create(
            servico=servico, status='PROCESSANDO', xml_enviado=xml_rps
        )

        try:
            # Em modo de produção, a linha abaixo seria descomentada
            # headers = {'Content-Type': 'application/xml; charset=utf-8'}
            # response = requests.post(self.URL_HOMOLOGACAO, data=xml_rps.encode('utf-8'), headers=headers)

            # =======================================================
            # SIMULAÇÃO DE TESTE REAL
            # =======================================================
            print("--- XML A SER ENVIADO PARA O WEBSERVICE (APÓS ASSINATURA) ---")
            print(xml_rps)
            print("----------------------------------------------------------")

            # Simulamos que a requisição foi feita e deu sucesso
            nf.status = 'ACEITO'
            nf.numero_nfse = str(nf.pk).zfill(15)
            nf.codigo_verificacao = f'SIMULACAO-TESTE-{datetime.now().timestamp()}'
            nf.data_emissao_nfse = datetime.now()
            nf.xml_recebido = "<Retorno><Sucesso>Lote recebido e processado.</Sucesso></Retorno>"  # Simula resposta
            nf.mensagem_retorno = "RPS enviado com sucesso (SIMULAÇÃO)."
            nf.save()

            return {'status': 'sucesso', 'mensagem': f'NFS-e (simulada) {nf.numero_nfse} emitida com sucesso!'}

        except Exception as e:
            nf.status = 'ERRO'
            nf.mensagem_retorno = str(e)
            nf.save()
            return {'status': 'erro', 'mensagem': f'Ocorreu um erro na comunicação: {str(e)}'}