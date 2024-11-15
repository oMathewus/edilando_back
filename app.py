from flask import Flask, request, jsonify
from twocaptcha import TwoCaptcha
import requests
import logging
import os
from datetime import datetime
from bs4 import BeautifulSoup
import time
import json

app = Flask(__name__)

# Adicionando CORS manualmente
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')  # Permitir qualquer origem
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    return response

class ConsultaABR:
    def __init__(self, api_key_2captcha):
        self.session = requests.Session()
        self.solver = TwoCaptcha(api_key_2captcha)
        self.base_url = 'https://consultanumero.abrtelecom.com.br'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': self.base_url,
            'Referer': f'{self.base_url}/consultanumero/consulta/consultaHistoricoRecenteCtg',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        self.setup_logging()

    def setup_logging(self):
        """Configura o sistema de logs"""
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f'logs/consulta_abr_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] - %(message)s',
            handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)

    def solve_captcha(self):
        """Resolve o reCAPTCHA usando 2captcha"""
        self.logger.info("Iniciando resolução do captcha...")
        try:
            result = self.solver.recaptcha(
                sitekey='6LetGEImAAAAAIji8OYruian_LlJwIW9E3ZC-0ps',
                url=f'{self.base_url}/consultanumero/consulta/consultaHistoricoRecenteCtg',
                invisible=0
            )
            self.logger.info("Captcha resolvido com sucesso")
            return result['code']
        except Exception as e:
            self.logger.error(f"Erro ao resolver captcha: {str(e)}")
            return None

    def consultar_numeros(self, numeros):
        """Consulta números usando o array de telefones"""
        self.logger.info(f"Iniciando consulta de {len(numeros)} números")
        
        try:
            # Primeiro acesso para obter cookies
            self.logger.info("Fazendo primeiro acesso para obter cookies...")
            response_get = self.session.get(
                f'{self.base_url}/consultanumero/consulta/consultaHistoricoRecenteCtg',
                headers=self.headers
            )
            
            if response_get.status_code != 200:
                self.logger.error(f"Erro no acesso inicial: {response_get.status_code}")
                return {"erro": f"Falha no acesso inicial: {response_get.status_code}"}

            self.logger.debug(f"Cookies obtidos: {dict(self.session.cookies)}")

            # Resolve o captcha
            captcha_response = self.solve_captcha()
            if not captcha_response:
                return {"erro": "Falha ao resolver captcha"}

            # Prepara o payload
            payload = {
                'dataInicial': '01/09/2008',
                'dataFinal': time.strftime('%d/%m/%Y'),
                'g-recaptcha-response': captcha_response,
                'quantidade': str(len(numeros))
            }

            # Adiciona os números ao payload como array
            telefones = []
            for numero in numeros:
                telefones.append(('telefone[]', numero))

            # Cria a lista de tuples para envio
            data = []
            for key, value in payload.items():
                data.append((key, value))
            data.extend(telefones)

            self.logger.info("Enviando requisição POST...")

            # Faz a requisição POST
            response = self.session.post(
                f'{self.base_url}/consultanumero/consulta/executaConsultaHistoricoRecente',
                data=data,
                headers=self.headers,
                allow_redirects=True
            )

            if response.status_code == 200:
                self.logger.info("Processando resposta...")
                soup = BeautifulSoup(response.text, 'html.parser')

                # Procura a tabela de resultados
                table = soup.find('table', {'id': 'resultado'})
                if not table:
                    self.logger.error("Tabela de resultados não encontrada")
                    return {"erro": "Tabela não encontrada"}

                # Processa os resultados
                results = []
                rows = table.find_all('tr')[1:]  # Pula o cabeçalho
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 5:
                        result = {
                            'telefone': cols[0].text.strip(),
                            'prestadora': cols[1].text.strip(),
                            'razao_social': cols[2].text.strip(),
                            'data': cols[3].text.strip(),
                            'mensagem': cols[4].text.strip()
                        }
                        results.append(result)

                return results

            else:
                self.logger.error(f"Erro na requisição: {response.status_code}")
                return {"erro": f"Erro na requisição: {response.status_code}"}

        except Exception as e:
            self.logger.exception("Erro durante a consulta")
            return {"erro": str(e)}

@app.route('/consultar', methods=['POST'])
def consultar():
    try:
        numeros = request.json.get('numeros')  # Obtendo o array de números do corpo da requisição
        consulta = ConsultaABR("92216252652b1da75b38161df725cc12")
        resultados = consulta.consultar_numeros(numeros)

        if "erro" in resultados:
            return jsonify(resultados), 500

        return jsonify(resultados), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)  # Alterando a porta para 3000

