import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import textwrap

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal ProVida", layout="wide")

@st.cache_resource
def get_gspread_client():
    """Conecta ao Google Sheets reconstruindo a chave PEM para evitar erros de Base64."""
    try:
        # 1. Recupera a string bruta e limpa espaços/quebras acidentais
        raw_key = st.secrets["PRIVATE_KEY_RAW"].replace(" ", "").replace("\n", "").strip()
        
        # 2. Reconstrói o formato PEM oficial (linhas de 64 caracteres)
        # O Google exige essa estrutura exata para validar a assinatura RSA
        key_lines = textwrap.wrap(raw_key, 64)
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"
        
        # 3. Dicionário de credenciais (IDs fixos para evitar erros de config)
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
        st.error(f"❌ Falha Crítica na Reconstrução da Chave: {e}")
        st.stop()

# --- MAPEAMENTO DE NÍVEIS ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

# --- SISTEMA DE LOGIN ---
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

# --- CARREGAMENTO E EXIBIÇÃO DE DADOS ---
try:
    client = get_gspread_client()
    # Substitua pelo ID da sua planilha se necessário
    sh = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    worksheet = sh.worksheet("Calendario_Eventos")
    
    df = pd.DataFrame(worksheet.get_all_records())
    
    # Limpeza de colunas
    df.columns = [c.strip() for c in df.columns]
    
    # Lógica de Filtro por Nível
    if 'Nível' in df.columns:
        df['Nivel_Num_Tabela'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
        df_filtrado = df[df['Nivel_Num_Tabela'] <= st.session_state.nivel_usuario_num].copy()
        
        st.header(f"Olá, {st.session_state.nome_usuario}!")
        st.subheader("📅 Atividades Disponíveis")
        
        # Colunas para exibir
        colunas_finais = ['Nome do Evento ou da Atividade', 'Data Específica', 'Nível', 'Voluntário 1', 'Voluntário 2']
        cols_presentes = [c for c in colunas_finais if c in df_filtrado.columns]
        
        st.dataframe(df_filtrado[cols_presentes], use_container_width=True, hide_index=True)
    else:
        st.error("Erro: A coluna 'Nível' não foi encontrada na planilha.")

    if st.sidebar.button("Sair"):
        st.session_state.autenticado = False
        st.rerun()

except Exception as e:
    st.error(f"❌ Erro ao acessar o Google Sheets: {e}")
    st.info("Verifique se o e-mail 'volutarios@chromatic-tree-279819.iam.gserviceaccount.com' tem permissão de EDITOR na planilha.")
