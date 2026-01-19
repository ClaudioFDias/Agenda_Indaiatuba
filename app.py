import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import textwrap
import re

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal de Voluntários ProVida", layout="wide")

@st.cache_resource
def get_gspread_client():
    try:
        # 1. Reconstrução
        partes_nome = ["P1", "P2", "P3", "P4", "P5", "P6"]
        chave_full = ""
        for nome in partes_nome:
            if nome in st.secrets:
                # Limpeza absoluta de caracteres não-base64
                limpo = re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets[nome])
                chave_full += limpo
        
        # 2. CORTE CIRÚRGICO (Ajustado para ignorar o caractere 'T' extra)
        # Se a chave tem 1621, pegamos apenas os 1620 primeiros.
        chave_final = chave_full[:1620]
        
        # 3. Formatação PEM
        key_lines = textwrap.wrap(chave_final, 64)
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"
        
        # ... (restante do dicionário creds_info igual ao anterior)
        
        # Estrutura do Dicionário de Credenciais
        creds_info = {
            "type": "service_account",
            "project_id": "chromatic-tree-279819",
            "private_key_id": "866d21c6b1ad8efba9661a2a15b47b658d9e1573",
            "private_key": formatted_key,
            "client_email": "volutarios@chromatic-tree-279819.iam.gserviceaccount.com",
            "client_id": "110888986067806154751",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/volutarios%40chromatic-tree-279819.iam.gserviceaccount.com"
        }
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    
    except Exception as e:
        st.error(f"❌ Falha Crítica na Conexão: {e}")
        st.stop()

# --- 2. MAPEAMENTO DE NÍVEIS ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

# --- 3. SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login de Voluntários - ProVida")
    with st.form("login_form"):
        nome = st.text_input("Seu Nome")
        nivel = st.selectbox("Seu Nível Atual", list(mapa_niveis.keys()))
        
        if st.form_submit_button("Acessar Calendário"):
            if nome:
                st.session_state.nome_usuario = nome
                st.session_state.nivel_usuario_num = mapa_niveis[nivel]
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.warning("Por favor, informe seu nome.")
    st.stop()

# --- 4. EXIBIÇÃO DOS DADOS (PÓS-LOGIN) ---
try:
    client = get_gspread_client()
    # Abre a planilha pelo ID único
    sh = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    worksheet = sh.worksheet("Calendario_Eventos")
    
    # Converte para DataFrame do Pandas
    df = pd.DataFrame(worksheet.get_all_records())
    
    # Limpeza básica de nomes de colunas
    df.columns = [c.strip() for c in df.columns]
    
    if 'Nível' in df.columns:
        # Cria coluna numérica para comparação de filtros
        df['Nivel_Num_Tabela'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
        
        # Lógica de Filtro: O voluntário vê tudo do nível dele para baixo
        df_filtrado = df[df['Nivel_Num_Tabela'] <= st.session_state.nivel_usuario_num].copy()
        
        st.header(f"Bem-vindo, {st.session_state.nome_usuario}!")
        st.info(f"Exibindo atividades compatíveis com o nível: **{list(mapa_niveis.keys())[list(mapa_niveis.values()).index(st.session_state.nivel_usuario_num)]}**")
        
        # Seleção das colunas principais para exibição
        colunas_u = ['Nome do Evento ou da Atividade', 'Data Específica', 'Nível', 'Voluntário 1', 'Voluntário 2']
        colunas_exibir = [c for c in colunas_u if c in df_filtrado.columns]
        
        st.dataframe(
            df_filtrado[colunas_exibir], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.error("Erro: A coluna 'Nível' não foi encontrada na sua planilha Google.")

except Exception as e:
    st.error(f"Erro ao carregar os dados da planilha: {e}")
    st.info("Dica: Verifique se o e-mail da conta de serviço está como 'Editor' na planilha.")

# --- 5. BOTÃO DE LOGOUT ---
if st.sidebar.button("Sair do Sistema"):
    st.session_state.autenticado = False
    st.rerun()

