# CHATBOT E GERADOR DE POSTS PARA REDES SOCIAIS
# VERSÃO COMPLETA (MERGE)
# Funcionalidades:
# - Geração Avançada de Imagem (Estilo, Qualidade, Filtro)
# - Download de Post .zip (txt + png)
# - Chatbot Assistente
# - Sistema de Cache local
# - Persistência de Histórico e Analytics no Firebase
# - Aba de Histórico com Busca, Filtros e Favoritos (em HTML colorido)
# - Exportar Histórico para CSV
# - Editor de Texto Inline

import gradio as gr
import requests
import os
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
import io # Necessário para BytesIO
from io import BytesIO
from huggingface_hub import InferenceClient
from pathlib import Path
import hashlib
import tempfile
import textwrap
import zipfile # Necessário para ZIP
import csv # Necessário para CSV

# Importar firebase-admin
import firebase_admin
from firebase_admin import credentials, firestore

# API Key vem dos Secrets (configurado em Settings)
HUGGINGFACE_API_KEY = os.environ.get("Capoeira")

# Verificar se API key existe
if not HUGGINGFACE_API_KEY:
    print("⚠️ API Key do Hugging Face não configurada! Certifique-se de que a variável de ambiente 'Capoeira' está definida.")

# URLs e modelos
BASE_URL = "https://router.huggingface.co/v1"
MODELO_TEXTO = "meta-llama/Llama-3.1-8B-Instruct"
MODELO_TRADUCA = "Helsinki-NLP/opus-mt-pt-en"

MODELOS_IMAGEM = [
    {
        "nome": "FLUX.1-schnell",
        "id": "black-forest-labs/FLUX.1-schnell",
        "descricao": "Rápido e boa qualidade",
        "tempo_medio": "10-15s"
    },
    {
        "nome": "FLUX.1-dev",
        "id": "black-forest-labs/FLUX.1-dev",
        "descricao": "Melhor qualidade, mais lento",
        "tempo_medio": "20-30s"
    },
    {
        "nome": "Stable Diffusion XL",
        "id": "stabilityai/stable-diffusion-xl-base-1.0",
        "descricao": "Alternativa confiável",
        "tempo_medio": "15-20s"
    }
]

# Headers para requisições
headers = {
    "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
    "Content-Type": "application/json"
}

# Opções da interface
NICHOS_DISPONIVEIS = [
    "Fitness e Vida Saudável",
    "Alimentação e Nutrição",
    "Motivação e Desenvolvimento Pessoal",
    "Negócios e Empreendedorismo",
    "Viagens e Turismo",
    "Tecnologia e Inovação",
    "Finanças Pessoais e Investimentos",
    "Cultura Pop e Entretenimento",
    "Meio Ambiente e Sustentabilidade",
    "Educação",
    "Produtividade",
    "Entretenimento",
    "Relacionamentos & Comunicação",
    "Espiritualidade & Filosofia",
    "Dicas Jurídicas e de Segurança Pública"
]

ESTILOS_DISPONIVEIS = [
    "Inspirador e motivacional",
    "Educativo e informativo",
    "Divertido e descontraído",
    "Profissional e técnico",
    "Controverso e de Debate",
    "Curiosidades (Fatos Rápidos)",
    "Tutorial/Passo a Passo",
]

ESTILOS_DE_IMAGEM = {
    "Nenhum (Automático)": "standard photography, high quality, 4k",
    "Fotografia Vintage": "vintage photography, retro style, film grain, analog",
    "Quente (Vintage)": "warm tones, vintage filter, retro, analog film look",
    "Frio (Moderno)": "cool tones, modern aesthetic, clean, desaturated blues",
    "Estilo Studio Ghibli": "Studio Ghibli style, poetic, soft, pastel colors, magical atmosphere, nostalgic portrait, fantasy scene",
    "Estilo Simpsons": "Simpsons style, iconic visual, strong black outlines, solid colors, humorous daily scene",
    "Estilo Pixar": "Pixar style, 3D digital animation, striking expressions, friendly characters",
    "Estilo Tim Burton": "Tim Burton style, dark aesthetic, thin lines, gothic environment, mysterious characters",
    "Estilo Attack on Titan": "Attack on Titan anime style, intense and dark lines, action scene",
    "Estilo RPG Clássico": "Classic RPG style, epic aesthetic, fantasy book cover",
    "Estilo 8-bit e 16-bit": "8-bit and 16-bit retro visual, nostalgic games",
    "Estilo Animação Anos 2000": "2000s animation style (Samurai Jack inspired), modern and stylized",
    "Arte Digital (Cinemático)": "cinematic, dramatic lighting, fantasy art, concept art",
    "Arte Digital (Neon)": "neonoir, cyberpunk, glowing lights, futuristic city",
    "Minimalista": "minimalist, clean background, simple, elegant",
}

FILTROS_IMAGEM = {
    "Nenhum": "",
    "Preto e Branco": "black and white, monochrome, high contrast",
    "Sépia": "sepia tone, vintage, warm tint, old photo",
    "Cinemático (Azulado)": "cinematic look, teal and orange, cool tones, movie still",
    "Quente (Vintage)": "warm tones, vintage filter, retro, analog film look",
    "Frio (Moderno)": "cool tones, modern aesthetic, clean, desaturated blues",
}

FORMATO_CONFIGS = {
    "Instagram (Post)": {"tamanho": "100-150 palavras", "estrutura": "gancho inicial + desenvolvimento + call-to-action", "tom_adicional": "próximo, empático e motivador", "max_tokens": 350, "limite_palavras_ia": "150 palavras", "hashtags": "Incluir 4-5 hashtags relevantes no final. Incluir no máximo 3 emojis relevantes no texto."},
    "Twitter/X (Curto)": {"tamanho": "Até 280 caracteres", "estrutura": "frase de impacto + link/hashtag", "tom_adicional": "direto e conciso, ideal for tweets", "max_tokens": 150, "limite_palavras_ia": "280 caracteres", "hashtags": "Incluir no máximo 2 hashtags."},
    "LinkedIn (Artigo)": {"tamanho": "250-400 palavras", "estrutura": "título chamativo + desenvolvimento profissional + reflexão", "tom_adicional": "profissional e autoritário, focado em insights", "max_tokens": 700, "limite_palavras_ia": "400 palavras", "hashtags": "Incluir 3-4 hashtags profissionais no final."},
    "WhatsApp": {"tamanho": "100-150 palavras", "estrutura": "texto fluido com formatação do WhatsApp (*negrito*, _itálico_)", "tom_adicional": "direto e engajante", "max_tokens": 350, "limite_palavras_ia": "150 palavras", "hashtags": "Incluir 2-3 hashtags relevantes no final, se apropriado."}
}

# Cores de fundo para o histórico, baseadas no Nicho
NICHOS_CORES = {
    "Fitness e Vida Saudável": "#064e3b", # Dark Green/Teal
    "Alimentação e Nutrição": "#166534", # Dark Green
    "Motivação e Desenvolvimento Pessoal": "#1e3a8a", # Dark Blue
    "Negócios e Empreendedorismo": "#312e81", # Dark Indigo
    "Viagens e Turismo": "#047857", # Dark Teal
    "Tecnologia e Inovação": "#1d4ed8", # Strong Blue
    "Finanças Pessoais e Investimentos": "#0f172a", # Darkest Slate
    "Cultura Pop e Entretenimento": "#581c87", # Dark Purple
    "Meio Ambiente e Sustentabilidade": "#15803d", # Medium Green
    "Educação": "#4338ca", # Indigo
    "Produtividade": "#374151", # Dark Gray
    "Entretenimento": "#7e22ce", # Purple
    "Relacionamentos & Comunicação": "#1e40af", # Medium Blue
    "Espiritualidade & Filosofia": "#4c1d95", # Deep Purple
    "Dicas Jurídicas e de Segurança Pública": "#1e293b", # Dark Slate
    "default": "#334155" # Default Slate
}

# Variáveis globais
db = None
post_history = []
analytics = {}
CACHE_DIR = Path("post_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Nomes de arquivo padrão para download
CSV_FILENAME = "posthistpeacechatbot001.csv"
ZIP_FILENAME = "postpeacechatbot001.zip"


# ============================================
# FUNÇÕES DE PERSISTÊNCIA (FIREBASE)
# ============================================

def _inicializar_firestore():
    """
    Inicializa o Firebase Admin SDK usando as credenciais
    armazenadas nos Secrets do Hugging Face Spaces.
    """
    global db, analytics
    
    secret_name = "FIREBASE_SERVICE_ACCOUNT_JSON"
    secret_json_string = os.environ.get(secret_name)

    if not secret_json_string:
        print(f"❌ Erro de Configuração do Firebase: Secret '{secret_name}' não encontrado.")
        print("Usando apenas histórico de sessão (temporário).")
        db = None
        analytics = {"status": "Não conectado"}
        return

    if not firebase_admin._apps:
        try:
            service_account_info = json.loads(secret_json_string)
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("✅ Firestore inicializado com sucesso.")
            # Inicializar/Carregar Analytics do Firestore
            _carregar_analytics_firestore()
        except Exception as e:
            print(f"❌ Erro ao inicializar Firestore. Usando histórico de sessão. Detalhe: {e}")
            db = None
            analytics = {"status": f"Erro de conexão: {e}"}

def _adicionar_post_firestore(entry):
    if db:
        try:
            db.collection('posts').add(entry)
            return True
        except Exception as e:
            print(f"❌ Erro ao adicionar post ao Firestore: {e}")
            return False
    return False

def _obter_historico_firestore():
    if db:
        try:
            # Correção do bug "Data/Hora"
            posts_query = db.collection('posts').order_by('DataHora', direction=firestore.Query.DESCENDING).limit(100)
            posts_stream = posts_query.stream()
            history = [post.to_dict() for post in posts_stream]
            return history
        except Exception as e:
            print(f"❌ Erro ao obter histórico do Firestore: {e}")
            return []
    return []

def atualizar_historico(entry):
    """Salva no Firestore e atualiza o cache de sessão local."""
    global post_history
    _adicionar_post_firestore(entry)
    # Adiciona no início da lista local
    post_history.insert(0, entry)
    # Garante que a lista local não cresça indefinidamente
    if len(post_history) > 100:
        post_history = post_history[:100]
    return post_history

def carregar_historico_inicial():
    """Carrega o histórico do Firestore ao iniciar o app."""
    global post_history
    historico_db = _obter_historico_firestore()
    if historico_db:
        post_history = historico_db
    # Retorna formatado para o componente de UI
    return _formatar_historico_para_html(post_history)

# ============================================
# FUNÇÕES DE ANALYTICS
# ============================================

def _carregar_analytics_firestore():
    """Carrega o documento único de analytics do Firestore."""
    global analytics
    if db:
        try:
            doc_ref = db.collection('analytics').document('summary')
            doc = doc_ref.get()
            if doc.exists:
                analytics = doc.to_dict()
                print("✅ Analytics carregados do Firestore.")
            else:
                # Se não existir, inicializa
                analytics = {
                    "total_posts": 0,
                    "posts_por_nicho": {},
                    "posts_por_estilo": {},
                    "total_palavras": 0,
                    "total_imagens": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "total_favoritos": 0
                }
                doc_ref.set(analytics)
                print("Analytics inicializados no Firestore.")
        except Exception as e:
            print(f"❌ Erro ao carregar Analytics: {e}")
            analytics = {"status": f"Erro: {e}"}

def _salvar_analytics_firestore():
    """Salva o estado atual de analytics no Firestore."""
    if db:
        try:
            db.collection('analytics').document('summary').set(analytics)
            print("Analytics salvos no Firestore.")
        except Exception as e:
            print(f"❌ Erro ao salvar Analytics: {e}")

def atualizar_analytics(nicho, estilo, palavras, imagem_gerada, cache_hit, favorito):
    """Atualiza as métricas de analytics (agora salva no Firestore)."""
    global analytics
    
    analytics['total_posts'] = analytics.get('total_posts', 0) + 1
    analytics['total_palavras'] = analytics.get('total_palavras', 0) + palavras
    
    if imagem_gerada:
        analytics['total_imagens'] = analytics.get('total_imagens', 0) + 1
        
    if cache_hit:
        analytics['cache_hits'] = analytics.get('cache_hits', 0) + 1
    else:
        analytics['cache_misses'] = analytics.get('cache_misses', 0) + 1
        
    if favorito:
        analytics['total_favoritos'] = analytics.get('total_favoritos', 0) + 1

    # Atualizar contadores de nicho e estilo
    nicho_counts = analytics.get('posts_por_nicho', {})
    nicho_counts[nicho] = nicho_counts.get(nicho, 0) + 1
    analytics['posts_por_nicho'] = nicho_counts
    
    estilo_counts = analytics.get('posts_por_estilo', {})
    estilo_counts[estilo] = estilo_counts.get(estilo, 0) + 1
    analytics['posts_por_estilo'] = estilo_counts
    
    # Salvar no Firestore
    _salvar_analytics_firestore()

def gerar_relatorio_analytics():
    """Formata os dados de analytics para exibição no Gradio como Markdown."""
    global analytics
    if not analytics or 'status' in analytics or analytics.get("total_posts", 0) == 0:
        return "📊 Nenhum post gerado ainda."
        
    # Ordenar os dicionários por valor (mais usados primeiro)
    posts_por_nicho_sorted = dict(sorted(analytics.get('posts_por_nicho', {}).items(), key=lambda item: item[1], reverse=True))
    posts_por_estilo_sorted = dict(sorted(analytics.get('posts_por_estilo', {}).items(), key=lambda item: item[1], reverse=True))

    total_reqs = analytics.get('cache_hits', 0) + analytics.get('cache_misses', 0)
    taxa_cache_hit = (analytics.get('cache_hits', 0) / total_reqs * 100) if total_reqs > 0 else 0
    
    nicho_top = max(analytics["posts_por_nicho"].items(), key=lambda x: x[1]) if analytics.get("posts_por_nicho") else ("N/A", 0)
    estilo_top = max(analytics["posts_por_estilo"].items(), key=lambda x: x[1]) if analytics.get("posts_por_estilo") else ("N/A", 0)

    relatorio = f"""📊 **RELATÓRIO DE ANALYTICS**
**Geral:**
• Total de posts: {analytics['total_posts']}
• Total de palavras: {analytics['total_palavras']:,}
• Total de imagens: {analytics['total_imagens']}
• Total de favoritos: {analytics.get('total_favoritos', 0)}
• Média de palavras/post: {analytics['total_palavras'] // analytics['total_posts'] if analytics['total_posts'] > 0 else 0}

**Performance:**
• Cache hits: {analytics['cache_hits']}
• Cache misses: {analytics['cache_misses']}
• Taxa de cache: {taxa_cache_hit:.1f}%

**Preferências:**
• Nicho mais usado: {nicho_top[0]} ({nicho_top[1]} posts)
• Estilo mais usado: {estilo_top[0]} ({estilo_top[1]} posts)
"""
    return relatorio

def resetar_analytics():
    """Reseta os dados de analytics no Firestore e localmente."""
    global analytics
    analytics = {
        "total_posts": 0,
        "posts_por_nicho": {},
        "posts_por_estilo": {},
        "total_palavras": 0,
        "total_imagens": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "total_favoritos": 0
    }
    _salvar_analytics_firestore()
    # Limpar cache local
    for f in CACHE_DIR.glob('*'):
        f.unlink()
    print("Analytics e Cache resetados.")
    return gerar_relatorio_analytics()


# ============================================
# FUNÇÕES DE CACHE
# ============================================

def criar_cache_key(tema, nicho, estilo, formato):
    """Cria uma chave de hash SHA-256 para os inputs."""
    input_string = f"{tema}-{nicho}-{estilo}-{formato}".encode('utf-8')
    return hashlib.sha256(input_string).hexdigest()

def salvar_no_cache(key, data):
    """Salva os dados (texto e imagem) em cache."""
    cache_file = CACHE_DIR / f"{key}.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({"texto": data["texto"], "imagem_path": data.get("imagem_path")}, f)

def buscar_no_cache(key):
    """Busca dados do cache. Retorna (texto, imagem_path) ou (None, None)."""
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            texto = data.get("texto")
            imagem_path = data.get("imagem_path")
            imagem = None
            
            if imagem_path:
                img_cache_file = CACHE_DIR / imagem_path
                if img_cache_file.exists():
                    imagem = Image.open(img_cache_file)
                else:
                    return None, None
            
            return texto, imagem
        except Exception as e:
            print(f"Erro ao ler cache {key}: {e}")
            return None, None
    return None, None

def salvar_imagem_cache(key, imagem_pil):
    """Salva a imagem PIL no diretório de cache e retorna o nome do arquivo."""
    if not imagem_pil:
        return None
    
    try:
        imagem_path = f"{key}_img.png"
        imagem_pil.save(CACHE_DIR / imagem_path)
        return imagem_path
    except Exception as e:
        print(f"Erro ao salvar imagem no cache: {e}")
        return None

# ============================================
# HELPER FUNCTIONS
# ============================================

def _formatar_historico_para_html(history_list):
    """Formata a lista de histórico (dicionários) para exibição em HTML."""
    if not history_list:
        return "<p style='text-align: center; color: #64748b;'>🔍 Nenhum post encontrado.</p>"

    # Cor do texto clara padrão para fundos escuros
    cor_texto_clara = "#f1f5f9" # Light slate/gray
    
    html = "<div style='max-height: 600px; overflow-y: auto; padding-right: 10px;'>"
    for i, post in enumerate(history_list):
        favorito_icon = "⭐" if post.get("Favorito") else "☆"
        nicho = post.get("Nicho", "default")
        # Pega a cor do nicho, ou a cor 'default' se o nicho não for encontrado
        cor_fundo = NICHOS_CORES.get(nicho, NICHOS_CORES["default"])
        
        try:
            data_str = post.get("DataHora", "")
            if isinstance(data_str, str) and data_str:
                try:
                    data = datetime.fromisoformat(data_str).strftime("%d/%m/%Y %H:%M")
                except ValueError:
                     data = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
            else:
                 data = "Data Indisponível"
        except Exception as e:
            print(f"Erro ao formatar data: {e}, Data original: {post.get('DataHora')}")
            data = "Data Inválida"

        # Texto completo, formatado para HTML
        texto_completo = post.get('Texto', 'Texto não salvo.').replace('\n', '<br>')
        
        # Stats
        stats = post.get("Stats", {})
        palavras = stats.get('palavras', 0)
        caracteres = stats.get('caracteres', 0)
        hashtags = stats.get('hashtags', 0)

        # CORREÇÃO: Aplicado 'cor_texto_clara' a todos os spans de texto
        html += f"""
        <div style='border: 1px solid {cor_fundo}; padding: 16px; margin: 12px 0;
                     border-radius: 8px; background-color: {cor_fundo}; color: {cor_texto_clara}; 
                     box-shadow: 0 4px 6px rgba(0,0,0,0.1); cursor: default;'>
            <div style='display: flex; justify-content: space-between; margin-bottom: 8px;'>
                <strong style='font-size: 16px; color: {cor_texto_clara};'>{favorito_icon} {post.get('Tema', 'Sem título')}</strong>
                <span style='color: {cor_texto_clara}; font-size: 12px;'>{data}</span>
            </div>
            <div style='color: {cor_texto_clara}; font-size: 13px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.2);'>
                <span style='color: {cor_texto_clara};'>📁 Nicho: {post.get('Nicho', 'N/A')}</span> |
                <span style='color: {cor_texto_clara};'>🎨 Estilo: {post.get('Estilo', 'N/A')}</span> |
                <span style='color: {cor_texto_clara};'>📄 Formato: {post.get('Formato', 'N/A')}</span>
            </div>
            
            <div style='font-size: 14px; color: {cor_texto_clara}; margin-bottom: 12px; max-height: 200px; overflow-y: auto; 
                        padding: 10px; background-color: rgba(0,0,0,0.15); border-radius: 6px; white-space: pre-wrap; word-wrap: break-word;'>
                {texto_completo}
            </div>
            
            <div style='display: flex; gap: 16px; font-size: 12px; color: {cor_texto_clara};'>
                <span style='color: {cor_texto_clara};'>📊 Palavras: {palavras}</span>
                <span style='color: {cor_texto_clara};'>📏 Caracteres: {caracteres}</span>
                <span style='color: {cor_texto_clara};'>#️⃣ Hashtags: {hashtags}</span>
            </div>
        </div>
        """
    html += "</div>"
    return html


def criar_alerta(tipo, mensagem):
    """Cria alerta HTML colorido"""
    cores = {
        'success': {'bg': '#d1fae5', 'border': '#10b981', 'icon': '✅'},
        'error': {'bg': '#fee2e2', 'border': '#ef4444', 'icon': '❌'},
        'warning': {'bg': '#fef3c7', 'border': '#f59e0b', 'icon': '⚠️'},
        'info': {'bg': '#dbeafe', 'border': '#3b82f6', 'icon': 'ℹ️'}
    }
    cor = cores.get(tipo, cores['info'])
    return f"""
    <div style="background-color: {cor['bg']}; border-left: 4px solid {cor['border']};
    padding: 16px; border-radius: 8px; margin: 8px 0;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 24px;">{cor['icon']}</span>
            <span style="font-size: 14px; color: #1f2937;">{mensagem}</span>
        </div>
    </div>
    """

def copiar_feedback(texto):
    # Esta função agora só retorna o alerta, o JS faz a cópia.
    if texto:
        return criar_alerta('success', '✅ Texto copiado!')
    return criar_alerta('warning', '⚠️ Nada para copiar')

def print_like_dislike(x: gr.LikeData):
    """Função de callback para o evento 'like' do chatbot."""
    print(f"Mensagem {x.index} foi marcada como: {x.value}, Liked: {x.liked}")

def limpar_cache():
    """Remove todos os arquivos de cache"""
    try:
        count = 0
        for arquivo in CACHE_DIR.glob("*"):
            if arquivo.is_file(): # Garante que só apagamos arquivos
                arquivo.unlink()
                count += 1
        print(f"{count} arquivos de cache removidos.")
        return True
    except Exception as e:
        print(f"Erro ao limpar cache: {e}")
        return False

def limpar_cache_feedback():
    """Limpa cache e retorna feedback"""
    if limpar_cache():
        return criar_alerta('success', '🗑️ Cache limpo com sucesso!')
    return criar_alerta('error', '❌ Erro ao limpar cache')

def limpar_tudo():
    """Limpa todos os inputs da UI, incluindo filtros de histórico, para seus valores padrão."""
    analytics_data = gerar_relatorio_analytics()
    return (
        # Aba Gerador
        "", # tema_input
        NICHOS_DISPONIVEIS[0], # nicho_input
        ESTILOS_DISPONIVEIS[0], # estilo_input
        list(FORMATO_CONFIGS.keys())[0], # formato_input
        True, # usar_cache_checkbox
        False, # favorito_checkbox
        False, # gerar_img_checkbox
        "", # descricao_img_input
        "Nenhum (Automático)", # estilo_img_input
        "Balanceada", # qualidade_img_input
        "Nenhum", # filtro_img_input
        "", # texto_output
        None, # imagem_output
        criar_alerta('info', '🧹 Interface limpa!'), # status_output
        0, # palavras_output
        0, # caracteres_output
        0, # hashtags_output
        None, # download_zip_output
        None, # download_csv_file
        analytics_data, # analytics_display
        # Botão Refinar
        True, # editor_locked (State)
        gr.Textbox(interactive=False), # texto_output
        gr.Button(value="✏️ Refinar Post"), # refinar_btn
        # Aba Histórico
        "", # busca_query_input
        "Todos", # filtro_nicho_hist
        "Todos", # filtro_estilo_hist
        "Todos", # filtro_formato_hist
        False # filtro_favoritos_hist
    )


def recarregar_e_formatar_historico(query, nicho, estilo, formato, favoritos_apenas):
    """
    Chamado após a geração de um post, para atualizar a visualização HTML do histórico
    mantendo os filtros atuais.
    """
    return filtrar_historico_local(query, nicho, estilo, formato, favoritos_apenas)

def interpretar_erro_api(erro_str):
    """Interpreta erros comuns da API para o usuário em Português."""
    erro_str_lower = erro_str.lower()
    print(f"Interpretando erro: {erro_str}")

    if "402" in erro_str_lower or "payment required" in erro_str_lower or "exceeded your monthly included credits" in erro_str_lower:
        return ("Erro 402: Limite de créditos excedido. Você excedeu seus créditos mensais da API do Hugging Face. "
                "Considere assinar o plano PRO para mais créditos.")
    
    if "503" in erro_str_lower or "model is loading" in erro_str_lower or "service temporarily unavailable" in erro_str_lower:
        return ("Erro 503: Modelo indisponível. O modelo está carregando ou temporariamente indisponível. "
                "Por favor, tente novamente em alguns segundos.")

    if "429" in erro_str_lower or "too many requests" in erro_str_lower:
        return ("Erro 429: Muitas requisições. O limite de taxa foi atingido. "
                "Por favor, aguarde um momento e tente novamente.")

    if "timeout" in erro_str_lower or "timed out" in erro_str_lower:
        return ("Erro de Timeout: A conexão expirou. O modelo demorou muito para responder. "
                "Tente novamente.")
    
    if "authorization" in erro_str_lower or "401" in erro_str_lower:
            return ("Erro 401: Autenticação falhou. A Chave da API (Secret 'Capoeira') pode estar inválida ou ausente.")

    return f"Erro inesperado: {erro_str[:200]}..."

# ============================================
# FUNÇÕES DE FILTRO E HISTÓRICO
# ============================================

def filtrar_historico_local(query, nicho, estilo, formato, favoritos_apenas):
    """Filtra a lista global `post_history` e retorna HTML formatado."""
    global post_history
    
    resultados = post_history
    
    if query:
        query_lower = query.lower()
        resultados = [
            post for post in resultados 
            if query_lower in post.get("Tema", "").lower() or query_lower in post.get("Texto", "").lower()
        ]
        
    if nicho != "Todos":
        resultados = [post for post in resultados if post.get("Nicho") == nicho]
        
    if estilo != "Todos":
        resultados = [post for post in resultados if post.get("Estilo") == estilo]
        
    if formato != "Todos":
        resultados = [post for post in resultados if post.get("Formato") == formato]
        
    if favoritos_apenas:
        resultados = [post for post in resultados if post.get("Favorito") == True]
        
    # Formata para HTML
    return _formatar_historico_para_html(resultados)

def exportar_historico_csv():
    """Exporta o `post_history` global para um arquivo CSV."""
    global post_history
    if not post_history:
        print("Nenhum histórico para exportar.")
        return None
        
    filepath = CACHE_DIR / CSV_FILENAME
        
    try:
        # Escrever diretamente no arquivo com encoding UTF-8
        with open(filepath, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # Cabeçalhos
            headers = ["DataHora", "Tema", "Nicho", "Estilo", "Formato", "Favorito", "Status", "Palavras", "Caracteres", "Hashtags", "Texto"]
            writer.writerow(headers)
            
            # Escrever linhas
            for post in post_history:
                stats = post.get("Stats", {})
                row = [
                    post.get("DataHora", ""),
                    post.get("Tema", ""),
                    post.get("Nicho", ""),
                    post.get("Estilo", ""),
                    post.get("Formato", ""),
                    post.get("Favorito", False),
                    post.get("Status", ""),
                    stats.get("palavras", 0),
                    stats.get("caracteres", 0),
                    stats.get("hashtags", 0),
                    post.get("Texto", "")
                ]
                writer.writerow(row)
                
        print(f"Arquivo CSV salvo em: {filepath}")
        return str(filepath) # Retorna o caminho estático
            
    except Exception as e:
        print(f"❌ Erro ao exportar CSV: {e}")
        return None

# ============================================
# FUNÇÕES DE GERAÇÃO
# ============================================

def gerar_texto(tema, nicho, estilo, formato):
    """
    Gera texto usando API do Hugging Face com base no formato escolhido.
    """
    
    if not HUGGINGFACE_API_KEY:
        return "❌ Erro de Configuração: API Key não está definida."

    config = FORMATO_CONFIGS.get(formato, FORMATO_CONFIGS["Instagram (Post)"])
    
    url = f"{BASE_URL}/chat/completions"

    payload = {
        "model": MODELO_TEXTO,
        "messages": [
            {
                "role": "system",
                "content": f"Você é um criador de conteúdo especializado em {nicho} e na criação de posts no formato {formato}."
            },
            {
                "role": "user",
                "content": f"""Crie uma legenda criativa para {formato} sobre: {tema}

Requisitos:
- Estilo: {estilo}
- Tamanho: {config['limite_palavras_ia']} ({config['tamanho']})
- Estrutura: {config['estrutura']}
- Tom: {config['tom_adicional']}
- {config['hashtags']}

Escreva apenas o conteúdo, sem introduções ou explicações."""
            }
        ],
        "max_tokens": config['max_tokens'],
        "temperature": 0.7,
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            resultado = response.json()
            if 'choices' in resultado and resultado['choices']:
                texto = resultado['choices'][0]['message']['content'].strip()
                return texto
            else:
                return f"❌ Erro na resposta da API: Resposta vazia ou inesperada.\n{resultado}"
        else:
            return f"❌ {interpretar_erro_api(f'Erro {response.status_code}: {response.text}')}"

    except Exception as e:
        return f"❌ {interpretar_erro_api(str(e))}"

def traduzir_texto(texto_pt):
    """Traduz texto de Português (PT) para Inglês (EN) usando API do Hugging Face.
    """
    if not HUGGINGFACE_API_KEY:
        return texto_pt

    url = f"https://api-inference.huggingface.co/models/{MODELO_TRADUCA}"
    payload = {"inputs": texto_pt}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            resultado = response.json()
            if resultado and isinstance(resultado, list) and 'translation_text' in resultado[0]:
                texto_en = resultado[0]['translation_text']
                return texto_en
            else:
                return texto_pt # Fallback
        else:
            return texto_pt # Fallback
    except Exception as e:
        print(f"Falha na tradução (fallback para PT): {e}")
        return texto_pt # Fallback

def otimizar_prompt_imagem(descricao_pt, estilo_escolhido, filtro_escolhido):
    """Combina as escolhas do usuário em um prompt otimizado (em Português)."""
    
    estilo = ESTILOS_DE_IMAGEM.get(estilo_escolhido, ESTILOS_DE_IMAGEM["Nenhum (Automático)"])
    filtro = FILTROS_IMAGEM.get(filtro_escolhido, FILTROS_IMAGEM["Nenhum"])
    
    prompt_final = f"{descricao_pt}, {estilo}, {filtro}, best quality, 4k"
    
    prompt_final = prompt_final.replace(", ,", ",").replace(", ,", ",")
    return prompt_final

def criar_negative_prompt():
    """Cria um prompt negativo padrão para evitar resultados ruins."""
    return "low quality, blurry, (deformed hands:1.3), (bad anatomy:1.loca3), (mutilated:1.2), (extra limbs:1.2), watermark, text, signature, ugly, tiling"

def gerar_imagem_robusta(descricao_pt, estilo_escolhido, qualidade, filtro_escolhido, progress=None):
    """
    Gera imagem com sistema robusto de fallback e controle de qualidade.
    Retorna: (PIL.Image, str_mensagem_status)
    """
    
    # 1. Configs de Qualidade (CORRIGIDO)
    configs_qualidade = {
        "Rápida": {
            "modelos": [MODELOS_IMAGEM[0]],  # Só FLUX-schnell
            "steps": 10 # CORRIGIDO: Era 20, o máximo é 16. 10 é seguro e rápido.
        },
        "Balanceada": {
            "modelos": MODELOS_IMAGEM[:2],  # FLUX schnell + dev
            "steps": 25 # Mantém 25 (para o FLUX.1-dev)
        },
        "Alta": {
            "modelos": MODELOS_IMAGEM,  # Todos os 3
            "steps": 30 # Mantém 30 (para SDXL e FLUX.1-dev)
        }
    }
    config = configs_qualidade.get(qualidade, configs_qualidade["Balanceada"])
    
    # 2. Otimizar e Traduzir Prompt
    if progress: progress(0.55, desc="🌍 Otimizando e traduzindo prompt...")
    prompt_otimizado_pt = otimizar_prompt_imagem(descricao_pt, estilo_escolhido, filtro_escolhido)
    prompt_final_en = traduzir_texto(prompt_otimizado_pt)
    negative_prompt = criar_negative_prompt()

    # 3. Tentar cada modelo na lista de qualidade
    for i, modelo_config in enumerate(config['modelos']):
        try:
            if progress:
                prog_val = 0.6 + (i * 0.1) # Ajustar progresso
                progress(prog_val, desc=f"🎨 Tentando {modelo_config['nome']}...")
            
            print(f"Tentando gerar imagem com {modelo_config['nome']}...")

            # --- INÍCIO DA CORREÇÃO ---
            # Pega o 'steps' do perfil de qualidade
            steps_para_usar = config['steps'] 
            
            # FLUX.1-schnell tem um limite MÁXIMO de 16 steps.
            # Se este modelo for tentado, devemos forçar os steps para um valor seguro.
            if modelo_config['id'] == "black-forest-labs/FLUX.1-schnell":
                # Se o perfil for "Rápida", ele já é 10.
                # Se for "Balanceada" (25) ou "Alta" (30), reduzimos para 16 (limite máx).
                steps_para_usar = min(config['steps'], 16)
                print(f"Ajustando steps para {steps_para_usar} para o modelo FLUX.1-schnell.")
            # --- FIM DA CORREÇÃO ---

            client = InferenceClient(api_key=HUGGINGFACE_API_KEY)
            
            imagem = client.text_to_image(
                prompt=prompt_final_en,
                model=modelo_config['id'],
                negative_prompt=negative_prompt,
                num_inference_steps=steps_para_usar # CORRIGIDO
            )
            
            print(f"✅ Imagem gerada com {modelo_config['nome']}")
            mensagem = f"✅ Imagem gerada com {modelo_config['nome']}"
            
            return (imagem, mensagem) # Retorna (PIL.Image, str)

        except Exception as e:
            print(f"❌ Falha com {modelo_config['nome']}: {str(e)}")
            
            if i < len(config['modelos']) - 1:
                print(f"⏭️ Tentando próximo modelo...")
                continue
            else:
                mensagem = f"❌ {interpretar_erro_api(str(e))}"
                return (None, mensagem)

    return (None, "❌ Erro inesperado ao gerar imagem")


# ============================================
# FUNÇÃO DO CHATBOT
# ============================================
def responder_chat(message, chat_history):
    """
    Função principal de lógica do chatbot. Recebe a nova mensagem e o histórico,
    retorna a string de resposta da IA.
    """
    if not HUGGINGFACE_API_KEY:
        return "❌ Erro de Configuração: API Key não está definida."

    url = f"{BASE_URL}/chat/completions"
    
    system_prompt = "Você é um assistente virtual prestativo e amigável, especializado em marketing de mídias sociais e criação de conteúdo, mas pode responder sobre qualquer tópico. Seja direto e útil."
    
    # Constrói o payload de mensagens
    messages = [{"role": "system", "content": system_prompt}]
    # Adiciona o histórico existente
    messages.extend(chat_history)
    # Adiciona a nova mensagem do usuário
    messages.append({"role": "user", "content": message})

    payload = {
        "model": MODELO_TEXTO,
        "messages": messages,
        "max_tokens": 1500,
        "temperature": 0.7,
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            resultado = response.json()
            if 'choices' in resultado and resultado['choices']:
                texto = resultado['choices'][0]['message']['content'].strip()
                return texto
            else:
                return f"❌ Erro na resposta da API: Resposta vazia ou inesperada.\n{resultado}"
        else:
            return f"❌ {interpretar_erro_api(f'Erro {response.status_code}: {response.text}')}"

    except Exception as e:
        return f"❌ {interpretar_erro_api(str(e))}"

def chatbot_respond(message, chat_history):
    """
    Função wrapper para a UI do Gradio.
    Recebe a mensagem e o histórico, chama a lógica do bot,
    e retorna o histórico atualizado.
    """
    # 1. Adiciona a mensagem do usuário ao histórico
    chat_history.append({"role": "user", "content": message})
    # 2. Obtém a resposta do bot (string)
    bot_response_str = responder_chat(message, chat_history)
    # 3. Adiciona a resposta do bot ao histórico
    chat_history.append({"role": "assistant", "content": bot_response_str})
    # 4. Retorna a caixa de texto vazia e o histórico atualizado
    return "", chat_history

# ============================================
# FUNÇÕES DE DOWNLOAD
# ============================================

def preparar_download_zip(texto, imagem_pil):
    """
    Prepara um arquivo ZIP em memória contendo post.txt e imagem.png.
    Retorna o caminho do arquivo temporário para o gr.File.
    """
    if not texto and not imagem_pil:
        print("Nada para baixar.")
        return None
        
    filepath = CACHE_DIR / ZIP_FILENAME

    try:
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. Adicionar o texto (garantindo UTF-8)
            if texto:
                zf.writestr("post.txt", texto.encode('utf-8'))
            
            # 2. Adicionar a imagem
            if imagem_pil:
                # Criar um buffer em memória para a imagem
                img_buffer = io.BytesIO()
                imagem_pil.save(img_buffer, format="PNG")
                # Voltar ao início do buffer da imagem
                img_buffer.seek(0)
                zf.writestr("imagem.png", img_buffer.getvalue())

        print(f"Arquivo ZIP salvo em: {filepath}")
        return str(filepath) # Retorna o caminho estático

    except Exception as e:
        print(f"❌ Erro ao criar arquivo ZIP: {e}")
        return None

# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def toggle_editor_interactivity(is_locked):
    """Alterna a interatividade do Textbox de saída e o texto do botão."""
    new_locked_state = not is_locked
    if new_locked_state:
        button_text = "✏️ Refinar Post"
    else:
        button_text = "🔒 Travar Edição"
    
    return new_locked_state, gr.Textbox(interactive=not new_locked_state), gr.Button(value=button_text)

def gerar_post_interface(tema, nicho, estilo, formato, usar_cache, favorito_checkbox,
                         descricao_imagem, gerar_img,
                         estilo_img_input, qualidade_img_input, filtro_img_input,
                         progress=gr.Progress()):
    """
    Função principal unificada, com Cache, Analytics, Favoritos e Geração Avançada.
    Retorna 10 valores para a UI.
    """
    
    analytics_display = gerar_relatorio_analytics() # Carregar estado atual
    
    progress(0, desc="🚀 Iniciando...")
    time.sleep(0.3)
    
    progress(0.1, desc="✅ Validando...")
    if not tema or len(tema.strip()) < 3:
        status_final = criar_alerta('error', '⚠️ Digite um tema válido!')
        # Retorna 10 valores
        return ("", None, status_final, 0, 0, 0, analytics_display, True, gr.Textbox(interactive=False), gr.Button(value="✏️ Refinar Post"))
    time.sleep(0.3)

    # 1. Lógica de Cache
    cache_key = criar_cache_key(tema, nicho, estilo, formato)
    if usar_cache:
        progress(0.2, desc="🔍 Buscando no cache...")
        texto, imagem = buscar_no_cache(cache_key)
        
        if texto:
            print("✅ Cache hit!")
            progress(1.0, desc="🎉 Encontrado no cache!")
            status_final = criar_alerta('success', '🎉 Post carregado do cache!')
            
            palavras = len(texto.split())
            caracteres = len(texto)
            hashtags = texto.count('#')

            atualizar_analytics(nicho, estilo, palavras, (imagem is not None), cache_hit=True, favorito=favorito_checkbox)
            analytics_display = gerar_relatorio_analytics() # Recarregar
            
            history_entry = {
                "DataHora": datetime.now(ZoneInfo("America/Bahia")).strftime("%Y-%m-%d %H:%M:%S"),
                "Tema": tema, "Nicho": nicho, "Estilo": estilo, "Formato": formato,
                "Texto": texto,
                "Status": "Carregado do Cache",
                "Favorito": favorito_checkbox,
                "Stats": {"palavras": palavras, "caracteres": caracteres, "hashtags": hashtags}
            }
            atualizar_historico(history_entry)
            
            return (texto, imagem, status_final, palavras, caracteres, hashtags, analytics_display, True, gr.Textbox(interactive=False), gr.Button(value="✏️ Refinar Post"))
    
    print("Cache miss ou cache desativado.")
    progress(0.3, desc="🤖 Gerando texto (Llama 3.1)...")
    
    # 2. Gerar Texto
    texto = gerar_texto(tema, nicho, estilo, formato)  
    
    if texto.startswith("❌"):
        status_final = criar_alerta('error', f'{texto}')
        return (texto, None, status_final, 0, 0, 0, analytics_display, True, gr.Textbox(interactive=False), gr.Button(value="✏️ Refinar Post"))
    
    progress(0.5, desc="✅ Texto pronto!")
    time.sleep(0.5)
    
    # 3. Gerar Imagem
    imagem = None
    status_imagem = ""
    if gerar_img:
        descricao_pt = descricao_imagem or f"{tema} imagem"
        
        (imagem, status_imagem) = gerar_imagem_robusta(
            descricao_pt,  
            estilo_img_input,  
            qualidade_img_input,  
            filtro_img_input,  
            progress
        )
        
        if imagem:
            status_final = criar_alerta('success', f'🎉 Post completo gerado! ({status_imagem})')
        else:
            status_final = criar_alerta('warning', f'✅ Texto OK, mas imagem falhou: {status_imagem}')
    else:
        progress(0.7, desc="⏭️ Pulando geração de imagem...")
        status_final = criar_alerta('success', '✅ Texto gerado (sem imagem)!')
    
    time.sleep(0.5)
    
    # 4. Estatísticas
    progress(0.9, desc="📊 Calculando estatísticas...")
    palavras = len(texto.split())
    caracteres = len(texto)
    hashtags = texto.count('#')
    time.sleep(0.3)
    
    # 5. Salvar no Cache
    if usar_cache:
        progress(0.95, desc="💾 Salvando no cache...")
        imagem_path_cache = salvar_imagem_cache(cache_key, imagem)
        cache_data = {
            "texto": texto,
            "imagem_path": imagem_path_cache
        }
        salvar_no_cache(cache_key, cache_data)
        
    # 6. Atualizar Histórico (Firestore)
    history_entry = {
        "DataHora": datetime.now(ZoneInfo("America/Bahia")).strftime("%Y-%m-%d %H:%M:%S"),
        "Tema": tema, "Nicho": nicho, "Estilo": estilo, "Formato": formato,
        "Texto": texto, # Salva o texto completo
        "Status": status_imagem or "Texto Gerado",
        "Favorito": favorito_checkbox,
        "Stats": {"palavras": palavras, "caracteres": caracteres, "hashtags": hashtags}
    }
    atualizar_historico(history_entry)
    
    # 7. Atualizar Analytics (Firestore)
    atualizar_analytics(nicho, estilo, palavras, (imagem is not None), cache_hit=False, favorito=favorito_checkbox)
    analytics_display = gerar_relatorio_analytics() # Recarregar
    
    progress(1.0, desc="🎉 Pronto!")
    
    return (texto, imagem, status_final, palavras, caracteres, hashtags, analytics_display, True, gr.Textbox(interactive=False), gr.Button(value="✏️ Refinar Post"))


# ============================================
# INTERFACE GRADIO
# ============================================

CSS = """
h3 {
    background-color: #f0f4f8;
    padding: 8px 12px;
    border-radius: 8px;
    color: #1f2937;
    font-weight: 600;
    margin-top: 10px;
}
"""

custom_theme = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="gray",
    neutral_hue="stone",
    font=["Helvetica", "Georgia", "sans-serif"]
)

# Inicializar Firestore e carregar Analytics ANTES de construir a UI
_inicializar_firestore()

with gr.Blocks(theme=custom_theme, title="Gerador de Posts e Chatbot (Completo)", css=CSS) as demo:

    gr.Markdown("""
    # 🚀 Gerador de Posts e Assistente de Mídias Sociais (Versão 4.1)
    ### Desenvolvido com Hugging Face, Gradio, Llama 3.1 e Firebase
    """)
    
    with gr.Tabs() as main_tabs:
        with gr.TabItem("✨ Gerar Post", id=0):
            with gr.Row():
                with gr.Column(scale=1):
                    # MELHORIA: gr.Accordion
                    with gr.Accordion("⚙️ 1. Configurações do Texto", open=True):
                        nicho_input = gr.Dropdown(
                            choices=NICHOS_DISPONIVEIS,
                            label="🎯 Nicho",
                            value=NICHOS_DISPONIVEIS[0],
                            interactive=True
                        )
            
                        estilo_input = gr.Radio(
                            choices=ESTILOS_DISPONIVEIS,
                            label="🎨 Estilo",
                            value=ESTILOS_DISPONIVEIS[0],
                            interactive=True
                        )
            
                        tema_input = gr.Textbox(
                            label="📝 Tema do Post",
                            placeholder="Ex: Transforme seu corpo, transforme sua vida"
                        )

                        formato_input = gr.Radio(
                            choices=list(FORMATO_CONFIGS.keys()),
                            label="📄 Formato de Saída",
                            value=list(FORMATO_CONFIGS.keys())[0],
                            interactive=True
                        )
                    
                    with gr.Accordion("🎨 2. Configurações da Imagem (Opcional)", open=False):
                        gerar_img_checkbox = gr.Checkbox(
                            label="Gerar imagem?",
                            value=False
                        )
            
                        descricao_img_input = gr.Textbox(
                            label="📸 Descrição da imagem (em Português)",
                            placeholder="Ex: Pessoa correndo ao nascer do sol",
                            visible=False
                        )
                        
                        estilo_img_input = gr.Dropdown(
                            label="🖼️ Estilo da Imagem",
                            choices=list(ESTILOS_DE_IMAGEM.keys()),
                            value="Nenhum (Automático)",
                            visible=False,
                            interactive=True
                        )
                        
                        qualidade_img_input = gr.Radio(
                            label="⏱️ Qualidade da Imagem",
                            choices=["Rápida", "Balanceada", "Alta"],
                            value="Balanceada",
                            visible=False,
                            interactive=True
                        )
                        
                        filtro_img_input = gr.Dropdown(
                            label="🌈 Filtro da Imagem",
                            choices=list(FILTROS_IMAGEM.keys()),
                            value="Nenhum",
                            visible=False,
                            interactive=True
                        )
            
                        def toggle_descricao_img(gerar):
                            return (
                                gr.Textbox(visible=gerar),
                                gr.Dropdown(visible=gerar),
                                gr.Radio(visible=gerar),
                                gr.Dropdown(visible=gerar)
                            )
            
                        gerar_img_checkbox.change(
                            toggle_descricao_img,
                            inputs=[gerar_img_checkbox],
                            outputs=[descricao_img_input, estilo_img_input, qualidade_img_input, filtro_img_input]
                        )
                    
                    with gr.Accordion("⚡ Performance e Ações", open=True):
                        with gr.Group():
                            gr.Markdown("### ⚡ Performance")
                            usar_cache_checkbox = gr.Checkbox(
                                label="Usar cache",
                                value=True,
                                info="Reutiliza resultados anteriores (mais rápido)"
                            )
                            limpar_cache_btn = gr.Button(
                                "🗑️ Limpar Cache",
                                size="sm",
                                variant="secondary"
                            )
                        
                        gr.Markdown("") # Espaçamento
                        favorito_checkbox = gr.Checkbox(label="⭐ Favoritar este post?", value=False)
                        
                        gr.Markdown("") # Espaçamento
                        gerar_btn = gr.Button("✨ Gerar Post", variant="primary")
                
                with gr.Column(scale=1):
                    gr.Markdown("### 📋 3. Resultado")
        
                    status_output = gr.HTML(
                        label="Status",
                        value=criar_alerta('info', 'Pronto para gerar!')
                    )
        
                    texto_output = gr.Textbox(
                        label="Texto Gerado",
                        lines=10,
                        interactive=False,
                        show_copy_button=True,
                        elem_id="output_post"
                    )
                    
                    gr.Markdown("") # Espaçamento
                    editor_locked = gr.State(True)
                    refinar_btn = gr.Button("✏️ Refinar Post")
                    
                    with gr.Row():
                        copiar_btn = gr.Button("📋 Copiar Texto", variant="secondary")
                        limpar_btn = gr.Button("🧹 Limpar Tudo", variant="stop")
        
                    gr.Markdown("") # Espaçamento
                    imagem_output = gr.Image(
                        label="Imagem Gerada",
                        type="pil"
                    )
                    
                    gr.Markdown("") # Espaçamento
                    gr.Markdown("### 📥 4. Download")
                    download_zip_btn = gr.Button(
                        "Baixar Post (.zip)",
                        variant="secondary",
                    )
                    download_zip_output = gr.File(
                        label="Download (ZIP)",
                        visible=True
                    )
                    
                    gr.Markdown("") # Espaçamento
                    gr.Markdown("### 📊 Estatísticas do Texto")
                    with gr.Row():
                        palavras_output = gr.Number(label="📝 Palavras", value=0, interactive=False)
                        caracteres_output = gr.Number(label="📏 Caracteres", value=0, interactive=False)
                        hashtags_output = gr.Number(label="#️⃣ Hashtags", value=0, interactive=False)

            gr.Markdown("") # Espaçamento
            gr.Markdown("### 💡 Experimente estes exemplos:")
            
            example_inputs = [
                nicho_input, estilo_input, tema_input, formato_input, # Texto
                gerar_img_checkbox, usar_cache_checkbox, # Checkboxes
                descricao_img_input, estilo_img_input, qualidade_img_input, filtro_img_input # Imagem
            ]
            gr.Examples(
                examples=[
                    [
                        NICHOS_DISPONIVEIS[2], ESTILOS_DISPONIVEIS[0], "Frases marcantes de pessoas importantes", "Instagram (Post)",
                        True, True, "Um retrato de uma pessoa influente, estilo vintage", "Fotografia Vintage", "Balanceada", "Sépia"
                    ],
                    [
                        NICHOS_DISPONIVEIS[1], ESTILOS_DISPONIVEIS[2], "Receita rápida de smoothie verde", "WhatsApp",
                        True, True, "Um smoothie verde vibrante com frutas ao lado", "Nenhum (Automático)", "Rápida", "Nenhum"
                    ],
                    [
                        NICHOS_DISPONIVEIS[5], ESTILOS_DISPONIVEIS[3], "O futuro da IA em 2025", "LinkedIn (Artigo)",
                        True, True, "Um cérebro digital abstrato com luzes de neon", "Arte Digital (Neon)", "Alta", "Frio (Moderno)"
                    ],
                    [
                        NICHOS_DISPONIVEIS[9], ESTILOS_DISPONIVEIS[6], "Tutorial: 5 exercícios para fazer em casa", "Instagram (Post)",
                        False, True, "", "Nenhum (Automático)", "Balanceada", "Nenhum" # Exemplo sem imagem
                    ],
                    [
                        NICHOS_DISPONIVEIS[12], ESTILOS_DISPONIVEIS[1], "Como começar a investir com pouco dinheiro", "LinkedIn (Artigo)",
                        True, True, "Um cofrinho de porco ao lado de moedas e um gráfico crescente", "Minimalista", "Balanceada", "Nenhum"
                    ],
                ],
                inputs=example_inputs,
                outputs=example_inputs
            )
            
        with gr.TabItem("💬 Chatbot Assistente", id=1):
            gr.Markdown("### 🤖 Peace Chatbot")
            gr.Markdown("Faça perguntas sobre mídias sociais, IA, peça ideias rápidas ou qualquer outro tópico.")
            
            chatbot_para_interface = gr.Chatbot(
                height=500,  
                type="messages"
            )
            
            with gr.Column():
                with gr.Row():
                    chat_input = gr.Textbox(
                        show_label=False,
                        placeholder="Digite sua mensagem aqui...",
                        scale=7
                    )
                    submit_btn = gr.Button("Enviar", variant="primary", scale=1)
                
                clear_btn = gr.ClearButton(
                    [chat_input, chatbot_para_interface],
                    value="🧹 Limpar Chat"
                )

            gr.Examples(
                examples=[
                    "O que é um 'gancho' para Instagram?",  
                    "Me dê 3 ideias de post para um nicho de 'Fitness'",  
                    "Qual a diferença entre um post para Instagram e um para LinkedIn?"
                ],
                inputs=[chat_input]
            )

            # Conectar eventos do chatbot
            submit_btn.click(
                fn=chatbot_respond,
                inputs=[chat_input, chatbot_para_interface],
                outputs=[chat_input, chatbot_para_interface]
            )
            
            chat_input.submit(
                fn=chatbot_respond,
                inputs=[chat_input, chatbot_para_interface],
                outputs=[chat_input, chatbot_para_interface]
            )
            
            chatbot_para_interface.like(
                fn=print_like_dislike, 
                inputs=None, 
                outputs=None
            )
            
        with gr.TabItem("📚 Histórico de Posts", id=2):
            gr.Markdown("### 🔍 Buscar e Filtrar Histórico")
            gr.Markdown("Navegue pelos posts gerados anteriormente.")

            with gr.Row():
                busca_query_input = gr.Textbox(
                    label="🔍 Buscar por Tema/Texto", 
                    placeholder="Digite para buscar...", 
                    scale=3,
                    interactive=True
                )
                filtro_nicho_hist = gr.Dropdown(
                    label="🎯 Nicho", 
                    choices=["Todos"] + NICHOS_DISPONIVEIS, 
                    value="Todos",
                    interactive=True
                )
            with gr.Row():
                filtro_estilo_hist = gr.Dropdown(
                    label="🎨 Estilo", 
                    choices=["Todos"] + ESTILOS_DISPONIVEIS, 
                    value="Todos",
                    interactive=True
                )
                filtro_formato_hist = gr.Dropdown(
                    label="📄 Formato", 
                    choices=["Todos"] + list(FORMATO_CONFIGS.keys()), 
                    value="Todos",
                    interactive=True
                )
                filtro_favoritos_hist = gr.Checkbox(
                    label="⭐ Apenas Favoritos", 
                    value=False,
                    interactive=True
                )
            
            gr.Markdown("") # Espaçamento
            buscar_hist_btn = gr.Button("Buscar", variant="primary")
            
            historico_display = gr.HTML(
                value=carregar_historico_inicial(),
            )
            
            gr.Markdown("") # Espaçamento
            export_csv_btn = gr.Button("Exportar Histórico para CSV")
            download_csv_file = gr.File(label="Download CSV")


        with gr.TabItem("📊 Analytics", id=3):
            gr.Markdown("### Análise de Uso da Ferramenta")
            gr.Markdown("Estes dados são salvos no Firestore e agregam o uso de todos os usuários.")
            
            analytics_display = gr.Markdown(
                value=gerar_relatorio_analytics()
            )
            
            gr.Markdown("") # Espaçamento
            with gr.Row():
                gerar_relatorio_btn = gr.Button("Atualizar Relatório", variant="secondary")
                resetar_analytics_btn = gr.Button("Resetar Analytics (CUIDADO)", variant="stop")

        with gr.TabItem("⚙️ Configurações", id=4):
            gr.Markdown("### Configurações do Gerador")
            gr.Markdown("**Modelo de Texto (LLM):** Llama 3.1 8B (Usado para Posts e Chatbot)")
            gr.Markdown("**Modelos de Imagem:** FLUX.1-schnell, FLUX.1-dev, SDXL 1.0")
            gr.Markdown("**Modelo de Tradução (PT -> EN):** Helsinki-NLP/opus-mt-pt-en")
            gr.Markdown("**API Provider:** Hugging Face Inference")
            gr.Markdown("**Database:** Google Firestore (via Firebase Admin)")
            gr.Markdown("---")
            gr.Markdown("#### Funcionalidades (Versão Completa):")
            gr.Markdown("- **Gerador de Posts:** Cria posts completos com texto e imagem.")
            gr.Markdown("- **Seleção de Formato:** Permite escolher o formato do texto (Instagram, Twitter, LinkedIn, WhatsApp).")
            gr.Markdown("- **Controles Avançados:** Permite seleção de Estilo, Qualidade e Filtros para a imagem.")
            gr.Markdown("- **Download de Post:** Baixa um .zip com .txt e .png.")
            gr.Markdown("- **Chatbot Assistente:** Converse com a IA para ideias e perguntas rápidas.")
            gr.Markdown("- **Histórico Persistente:** Salva os *posts gerados* no Firestore.")
            gr.Markdown("- **Busca no Histórico:** Permite buscar e filtrar posts antigos.")
            gr.Markdown("- **Favoritos:** Permite marcar posts como favoritos.")
            gr.Markdown("- **Sistema de Cache:** Salva posts localmente para acelerar requisições futuras.")
            gr.Markdown("- **Sistema de Analytics:** Rastreia o uso (total, por nicho, etc.) no Firestore.")

        with gr.TabItem("ℹ️ Sobre", id=5):
            gr.Markdown("""
            ### Sobre Este Projeto

            Este gerador foi desenvolvido no **Curso de Python com IA**.

            **Tecnologias:**
            - Hugging Face Spaces (hospedagem)
            - Gradio (interface web)
            - **Llama 3.1 8B (geração de texto e chatbot)**
            - **FLUX.1 & SDXL (geração de imagens)**
            - Opus-MT (tradução)
            - **Firebase Firestore (Banco de Dados & Analytics)**
            - **PIL (Python Imaging Library) (para composição de posts)**
            - **Cache local (para performance)**
            - **CSV & ZIP (para exportação)**

            **Como funciona:**
            1. **Gerar Post:** Você define o tema, nicho, estilo e **formato** do *texto*.
            2. **Imagem (Opcional):** Você ativa, descreve a imagem e seleciona *Estilo*, *Qualidade* e *Filtro*.
            3. O sistema otimiza o prompt, traduz para inglês e usa o sistema de *fallback* de modelos (baseado na *Qualidade*) para gerar a imagem.
            4. **Refinar (Opcional):** Clique em "Refinar Post" para editar o texto gerado.
            5. **Download:** Após a geração, você pode clicar em "Baixar Post (.zip)" para salvar um ZIP com o texto e a imagem.
            6. **Chatbot:** Você pode conversar diretamente com a IA na aba 'Chatbot Assistente' para tirar dúvidas.
            7. **Histórico & Analytics:** Os posts gerados são salvos no Firestore e as métricas de uso são atualizadas.
            8. **Exportar:** Na aba "Histórico", você pode filtrar e exportar seus dados como CSV.

            **Desenvolvido por:** Wilder Paz
            """)

    # Footer
    gr.Markdown("""
    ---
    **Curso de Python com IA** | 🤖 Desenvolvido com Llama 3.1 & FLUX | ⚡ Hugging Face Spaces + Gradio + Firestore + Cache + Analytics
    """)

    # ============================================
    # CONECTAR EVENTOS
    # ============================================
    
    # Lista de inputs para o botão Gerar
    gerar_inputs = [
        tema_input, nicho_input, estilo_input, 
        formato_input, usar_cache_checkbox, favorito_checkbox,
        descricao_img_input, gerar_img_checkbox,
        estilo_img_input, qualidade_img_input, filtro_img_input
    ]
    
    # Lista de outputs do botão Gerar
    gerar_outputs = [
        texto_output, imagem_output, status_output,  
        palavras_output, caracteres_output, hashtags_output,
        analytics_display,
        editor_locked, texto_output, refinar_btn
    ]
    
    # Botão principal
    click_event = gerar_btn.click(
        fn=gerar_post_interface,
        inputs=gerar_inputs,
        outputs=gerar_outputs,
        show_progress="full"
    )
    
    # Lista de outputs para o botão Limpar
    limpar_outputs = [
        # Aba Gerador
        tema_input,
        nicho_input,
        estilo_input,
        formato_input,
        usar_cache_checkbox,
        favorito_checkbox,
        gerar_img_checkbox,
        descricao_img_input,
        estilo_img_input,
        qualidade_img_input,
        filtro_img_input,
        texto_output, 
        imagem_output, 
        status_output,  
        palavras_output, 
        caracteres_output, 
        hashtags_output,
        download_zip_output,
        download_csv_file,
        analytics_display,
        # Editor
        editor_locked,
        texto_output,
        refinar_btn,
        # Aba Histórico
        busca_query_input,
        filtro_nicho_hist,
        filtro_estilo_hist,
        filtro_formato_hist,
        filtro_favoritos_hist
    ]
    
    # Botão limpar
    limpar_btn.click(
        fn=limpar_tudo,
        inputs=[],
        outputs=limpar_outputs
    )
    
    # Botão de Download ZIP
    download_zip_btn.click(
        fn=preparar_download_zip,
        inputs=[texto_output, imagem_output],
        outputs=[download_zip_output]
    )
    
    # Conectar o novo botão Limpar Cache
    limpar_cache_btn.click(
        fn=limpar_cache_feedback,
        inputs=None,
        outputs=[status_output]
    )
    
    # Botão Refinar
    refinar_btn.click(
        fn=toggle_editor_interactivity,
        inputs=[editor_locked],
        outputs=[editor_locked, texto_output, refinar_btn]
    )
    
    # --- Eventos da Aba Histórico ---
    
    # Lista de inputs para os filtros de histórico
    hist_filter_inputs = [
        busca_query_input, 
        filtro_nicho_hist, 
        filtro_estilo_hist, 
        filtro_formato_hist, 
        filtro_favoritos_hist
    ]
    
    # Botão de buscar no histórico
    buscar_hist_btn.click(
        fn=filtrar_historico_local,
        inputs=hist_filter_inputs,
        outputs=[historico_display]
    )
    
    # Atualizar o histórico (mantendo filtros) após gerar um novo post
    click_event.then(
        fn=recarregar_e_formatar_historico,
        inputs=hist_filter_inputs,
        outputs=[historico_display]
    )
    
    # Evento de exportar CSV
    export_csv_btn.click(
        fn=exportar_historico_csv,
        inputs=None,
        outputs=[download_csv_file]
    )
    
    # --- Eventos da Aba Analytics ---
    
    gerar_relatorio_btn.click(
        fn=gerar_relatorio_analytics,
        inputs=None,
        outputs=[analytics_display]
    )
    
    resetar_analytics_btn.click(
        fn=resetar_analytics,
        inputs=None,
        outputs=[analytics_display],
        js="() => { return confirm('Tem certeza que deseja resetar TODOS os dados de analytics e cache? Esta ação não pode ser desfeita.') }"
    )

# Lançar aplicação
if __name__ == "__main__":
    demo.launch()

