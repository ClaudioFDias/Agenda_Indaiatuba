import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# --- 1. CONEXÃO COM O GOOGLE SHEETS ---
@st.cache_resource
def get_gspread_client():
    try:
        # Puxa a chave bruta das aspas triplas do TOML
        pk = st.secrets["PRIVATE_KEY"]
        email = "volutarios@chromatic-tree-279819.iam.gserviceaccount.com"
        
        # Reconstrói o dicionário para o Google
        creds_dict = {
            "type": "service_account",
            "project_id": "chromatic-tree-279819",
            "private_key_id": "866d21c6b1ad8efba9661a2a15b47b658d9e1573",
            "private_key": pk,
            "client_email": email,
            "client_id": "110888986067806154751",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{email.replace('@', '%40')}"
        }
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro ao conectar com Google: {e}")
        st.stop()

# --- 2. CONFIGURAÇÃO E LOGIN ---
st.set_page_config(page_title="Portal ProVida", layout="wide")

mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login")
    with st.form("login_form"):
        nome = st.text_input("Seu Nome")
        nivel = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Entrar"):
            st.session_state.nome_usuario = nome
            st.session_state.nivel_usuario_num = mapa_niveis[nivel]
            st.session_state.autenticado = True
            st.rerun()
    st.stop()

# --- 3. EXIBIÇÃO DA PLANILHA ---
if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()

try:
    client = get_gspread_client()
    sh = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    df = pd.DataFrame(sh.worksheet("Calendario_Eventos").get_all_records())
    
    # Filtro de nível
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df_filtrado = df[df['Nivel_Num'] <= st.session_state.nivel_usuario_num]

    st.header(f"Olá, {st.session_state.nome_usuario}")
    st.subheader("Atividades Disponíveis")
    st.dataframe(df_filtrado[['Nome do Evento ou da Atividade', 'Data Específica', 'Nível', 'Voluntário 1', 'Voluntário 2']], hide_index=True)

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")

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


