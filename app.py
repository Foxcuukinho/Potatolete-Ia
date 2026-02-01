from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
import requests
from bs4 import BeautifulSoup
import json

app = Flask(__name__)
CORS(app)

# Configurar API Key do Gemini usando variável de ambiente
# No Render: Configure em Environment Variables
# Localmente: Crie um arquivo .env ou export API_KEY="sua_chave"
API_KEY = os.environ.get('API_KEY')

if not API_KEY:
    raise ValueError("⚠️ API_KEY não configurada! Configure a variável de ambiente API_KEY")

genai.configure(api_key=API_KEY)

# Função de pesquisa na web usando DuckDuckGo (não precisa de API key)
def search_web(query):
    """Pesquisa na web e retorna resultados relevantes"""
    try:
        # Usar DuckDuckGo HTML para pesquisa
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        for result in soup.find_all('div', class_='result')[:5]:  # Pegar top 5 resultados
            title_elem = result.find('a', class_='result__a')
            snippet_elem = result.find('a', class_='result__snippet')
            
            if title_elem and snippet_elem:
                results.append({
                    'title': title_elem.get_text(strip=True),
                    'snippet': snippet_elem.get_text(strip=True),
                    'url': title_elem.get('href', '')
                })
        
        return results if results else None
    except Exception as e:
        print(f"Erro na pesquisa: {e}")
        return None

# ====================================
# INSTRUÇÕES/PERSONALIDADE DA POTATOLETE IA
# Customize aqui como você quer que ela se comporte!
# ====================================
INSTRUCOES_SISTEMA = """
Você é a Potatolete IA, uma assistente virtual amigável, útil e divertida.

PRIORIDADE MÁXIMA:
- SEMPRE responda a pergunta do usuário de forma ÚTIL e COMPLETA primeiro
- Depois de dar a resposta útil, você pode adicionar uma piada sobre tolete/sigma/beta/aura

QUANDO USAR PESQUISA:
- Se a pergunta é sobre algo atual, notícias, jogos, informações que mudam
- Se você não tem certeza da resposta
- Se o usuário pedir explicitamente para pesquisar
- SEMPRE que precisar de informações atualizadas ou específicas

PERSONALIDADE:
- Seja útil, inteligente e prestativa
- Adicione humor sobre tolete, sigma, beta, aura de forma LEVE e NATURAL
- Não exagere nas brincadeiras - apenas uma por resposta
- SEM EMOJI

REGRAS:
- Sempre responda em português brasileiro
- SEMPRE dê uma resposta útil e informativa PRIMEIRO
- Use os resultados de pesquisa quando disponíveis para dar respostas precisas
- Se o usuário pedir para ser sério ou útil, SEJA 100% SÉRIO e esqueça as brincadeiras
- Seja objetiva e clara
- Cite fontes quando usar informações de pesquisa

FORMATO DE RESPOSTA IDEAL:
1. Responda a pergunta de forma útil e clara
2. (Opcional) Adicione UMA piada leve no final relacionada ao contexto

EXPERTISE:
- Programação (Python, JavaScript, HTML, CSS, etc)
- Dúvidas gerais, tecnologia, jogos
- Escrita e criatividade
- Resolução de problemas
- Pesquisa e informações atualizadas

Lembre-se: UTILIDADE primeiro, diversão depois!
"""

# Criar modelo SEM ferramentas de busca (vamos fazer manual)
modelo = genai.GenerativeModel(
    'gemini-2.0-flash-exp',
    system_instruction=INSTRUCOES_SISTEMA
)

# Criar modelo com instruções do sistema
modelo = genai.GenerativeModel(
    'gemini-1.5-flash',
    system_instruction=INSTRUCOES_SISTEMA
)

# Armazenar sessões de chat (em produção, use Redis ou banco de dados)
chat_sessions = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message')
        session_id = data.get('session_id', 'default')
        
        if not message:
            return jsonify({'error': 'Mensagem vazia'}), 400
        
        # Criar ou recuperar sessão de chat
        if session_id not in chat_sessions:
            chat_sessions[session_id] = modelo.start_chat(history=[])
        
        chat = chat_sessions[session_id]
        
        # Detectar se precisa de pesquisa (palavras-chave)
        keywords_pesquisa = ['pesquisa', 'pesquise', 'busque', 'procure', 'qual', 'como pegar', 
                            'onde', 'quando', 'notícia', 'atual', 'hoje', 'agora', 'recente']
        
        precisa_pesquisa = any(keyword in message.lower() for keyword in keywords_pesquisa)
        
        # Se detectar necessidade de pesquisa, fazer busca
        search_results = None
        if precisa_pesquisa:
            search_results = search_web(message)
        
        # Preparar mensagem com contexto de pesquisa se houver
        if search_results:
            context = "\n\n[RESULTADOS DA PESQUISA NA WEB]:\n"
            for i, result in enumerate(search_results, 1):
                context += f"\n{i}. {result['title']}\n{result['snippet']}\n"
            
            message_with_context = f"{message}\n{context}\nUse essas informações para responder de forma precisa e útil."
            response = chat.send_message(message_with_context)
        else:
            # Enviar mensagem normal sem pesquisa
            response = chat.send_message(message)
        
        return jsonify({
            'response': response.text,
            'searched': search_results is not None,
            'success': True
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.route('/api/reset', methods=['POST'])
def reset_chat():
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        
        if session_id in chat_sessions:
            del chat_sessions[session_id]
        
        return jsonify({'success': True, 'message': 'Chat resetado'})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
