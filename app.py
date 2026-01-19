import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
import re

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Portal de Voluntários", layout="wide")

# --- 1. CONEXÃO ULTRA-ROBUSTA ---
@st.cache_resource
def get_gspread_client():
    try:
        # Puxa o conteúdo bruto do secret
        raw_json = st.secrets["GCP_JSON"]
        
        # Limpeza preventiva para evitar erros de caractere invisível
        raw_json = raw_json.strip()
        
        # Converte em dicionário Python
        info = json.loads(raw_json)
        
        # O TRATAMENTO DEFINITIVO DA CHAVE:
        # Remove aspas extras, espaços e garante que o \n seja lido como quebra de linha
        pk = info["private_key"]
        pk = pk.replace("\\n", "\n").replace('"', '').strip()
        info["private_key"] = pk
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        return gspread.authorize(creds)
        
    except Exception as e:
        st.error(f"Erro na Chave de Segurança: {e}")
        st.stop()

# --- 2. CARREGAMENTO DOS DADOS ---
def load_data():
    client = get_gspread_client()
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    try:
        ss = client.open_by_key(spreadsheet_id)
        sheet = ss.worksheet("Calendario_Eventos")
        df = pd.DataFrame(sheet.get_all_records())
        df.columns = [col.strip() for col in df.columns]
        return df
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        return None

# --- 3. LÓGICA DE LOGIN E MAPEAMENTO ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login Portal ProVida")
    with st.form("login"):
        u_nome = st.text_input("Seu Nome")
        u_nivel = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Entrar"):
            if u_nome:
                st.session_state.nome_usuario = u_nome
                st.session_state.nivel_usuario_num = mapa_niveis[u_nivel]
                st.session_state.autenticado = True
                st.rerun()
    st.stop()

# --- 4. EXIBIÇÃO ---
if st.sidebar.button("Sair", key="logout"):
    st.session_state.autenticado = False
    st.rerun()

st.header(f"Olá, {st.session_state.nome_usuario}!")

df = load_data()
if df is not None:
    # Filtro de Nível
    df['Nivel_Num'] = df['Nível'].astype(str).map(mapa_niveis).fillna(99)
    df_visivel = df[df['Nivel_Num'] <= st.session_state.nivel_usuario_num].copy()
    
    # Formatação de Data
    if 'Data Específica' in df_visivel.columns:
        df_visivel['Data'] = pd.to_datetime(df_visivel['Data Específica'], errors='coerce').dt.date
    
    st.subheader("📅 Atividades")
    exibir = ['Nome do Evento ou da Atividade', 'Data', 'Nível', 'Voluntário 1', 'Voluntário 2']
    st.dataframe(df_visivel[[c for c in exibir if c in df_visivel.columns]], use_container_width=True, hide_index=True)

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

