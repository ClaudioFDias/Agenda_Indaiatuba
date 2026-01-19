import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal de Voluntários ProVida", page_icon="🤝", layout="wide")

# --- 1. FUNÇÃO DE CONEXÃO (TRATA O JWT SIGNATURE) ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # Carrega o JSON do secrets
        info = json.loads(st.secrets["GCP_JSON"])
        
        # Correção crucial para o erro 'Invalid JWT Signature':
        # Converte as strings de escape \\n em quebras de linha reais \n
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
            
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro Crítico de Autenticação: {e}")
        st.stop()

# --- 2. FUNÇÃO PARA CARREGAR DADOS ---
def load_data():
    try:
        client = get_gspread_client()
        # ID da sua planilha extraído das credenciais anteriores
        spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
        ss = client.open_by_key(spreadsheet_id)
        sheet = ss.worksheet("Calendario_Eventos")
        
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Limpeza de nomes de colunas
        df.columns = [col.strip() for col in df.columns]
        return sheet, df
    except Exception as e:
        st.error(f"Erro ao acessar a Planilha Google: {e}")
        return None, None

# --- 3. MAPEAMENTO DE NÍVEIS ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

# --- 4. LÓGICA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso ao Portal de Voluntários")
    
    # Adicionando um formulário para evitar múltiplos carregamentos
    with st.form("form_login"):
        nome = st.text_input("Seu Nome Completo")
        nivel = st.selectbox("Seu Nível Atual", list(mapa_niveis.keys()))
        submit = st.form_submit_button("Entrar no Portal")
        
        if submit:
            if nome:
                st.session_state.nome_usuario = nome
                st.session_state.nivel_usuario_num = mapa_niveis[nivel]
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.warning("Por favor, preencha o seu nome.")
    st.stop()

# --- 5. INTERFACE DO USUÁRIO LOGADO ---
# Botão de Logout na Sidebar com Key Única
if st.sidebar.button("Sair do Sistema", key="sidebar_logout_btn"):
    st.session_state.autenticado = False
    st.rerun()

st.title(f"Bem-vindo(a), {st.session_state.nome_usuario}!")

sheet, df = load_data()

if df is not None:
    try:
        # Conversão de data para exibição bonita
        if 'Data Específica' in df.columns:
            df['Data'] = pd.to_datetime(df['Data Específica'], errors='coerce').dt.date
            
        # Filtro de Visibilidade: O voluntário vê o seu nível e todos os níveis abaixo dele
        df['Nivel_Num_Tabela'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
        df_filtrado = df[df['Nivel_Num_Tabela'] <= st.session_state.nivel_usuario_num].copy()
        
        st.subheader("📅 Próximas Atividades Disponíveis")
        
        # Colunas que queremos exibir
        colunas_exibir = ['Nome do Evento ou da Atividade', 'Data', 'Nível', 'Voluntário 1', 'Voluntário 2']
        cols_final = [c for c in colunas_exibir if c in df_filtrado.columns]
        
        st.dataframe(
            df_filtrado[cols_final], 
            use_container_width=True, 
            hide_index=True
        )

    except Exception as e:
        st.error(f"Erro ao processar as colunas da planilha: {e}")
else:
    st.info("Aguardando carregamento dos dados...")
