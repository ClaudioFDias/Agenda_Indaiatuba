import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal ProVida", layout="wide")

@st.cache_resource
def get_gspread_client():
    try:
        # 1. Puxa a chave limpa do Secret
        key_raw = st.secrets["PRIVATE_KEY_CLEAN"]
        
        # 2. Transforma o padrão [[N]] de volta em quebra de linha real (\n)
        # E monta o cabeçalho e rodapé
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + key_raw.replace("[[N]]", "\n") + "\n-----END PRIVATE KEY-----\n"
        
        # 3. Monta o dicionário de credenciais
        creds_dict = {
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
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na reconstrução da chave: {e}")
        st.stop()

# --- LÓGICA DE LOGIN ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login de Voluntários")
    with st.form("login"):
        nome = st.text_input("Seu Nome")
        nivel = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Entrar"):
            st.session_state.nome_usuario = nome
            st.session_state.nivel_usuario_num = mapa_niveis[nivel]
            st.session_state.autenticado = True
            st.rerun()
    st.stop()

# --- EXIBIÇÃO DOS DADOS ---
try:
    client = get_gspread_client()
    sh = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    df = pd.DataFrame(sh.worksheet("Calendario_Eventos").get_all_records())
    
    # Limpeza e Filtro
    df.columns = [c.strip() for c in df.columns]
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df_filtrado = df[df['Nivel_Num'] <= st.session_state.nivel_usuario_num]

    st.header(f"Bem-vindo, {st.session_state.nome_usuario}!")
    
    colunas_finais = ['Nome do Evento ou da Atividade', 'Data Específica', 'Nível', 'Voluntário 1', 'Voluntário 2']
    cols_existentes = [c for c in colunas_finais if c in df_filtrado.columns]
    
    st.dataframe(df_filtrado[cols_existentes], use_container_width=True, hide_index=True)

    if st.sidebar.button("Sair"):
        st.session_state.autenticado = False
        st.rerun()

except Exception as e:
    st.error(f"Erro ao acessar dados: {e}")

# --- CARREGAMENTO DE DADOS ---
def load_data():
    client = get_gspread_client()
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    
    try:
        # Camada 5: Acesso à Planilha Específica
        sh = client.open_by_key(spreadsheet_id)
        # Camada 6: Acesso à Aba
        worksheet = sh.worksheet("Calendario_Eventos")
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Limpeza de nomes de colunas (remove espaços invisíveis)
        df.columns = [c.strip() for c in df.columns]
        return df
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("❌ Erro Camada 5: Planilha não encontrada (ID incorreto).")
    except gspread.exceptions.APIError as e:
        st.error(f"❌ Erro Camada 5 (API Google): {e}")
        st.info("💡 Verifique se o e-mail da conta de serviço tem permissão de EDITOR na planilha.")
    except Exception as e:
        st.error(f"❌ Erro Camada 6: {e}")
    return None

# --- LÓGICA DE LOGIN ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🤝 Portal de Voluntários ProVida")
    st.markdown("---")
    with st.form("form_login"):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome Completo")
        with col2:
            nivel = st.selectbox("Seu Nível Atual", list(mapa_niveis.keys()))
        
        submit = st.form_submit_button("Entrar no Sistema")
        
        if submit:
            if nome:
                st.session_state.nome_usuario = nome
                st.session_state.nivel_usuario_num = mapa_niveis[nivel]
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.warning("Por favor, preencha seu nome.")
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.title(f"Bem-vindo(a), {st.session_state.nome_usuario}!")
if st.sidebar.button("Sair/Logout"):
    st.session_state.autenticado = False
    st.rerun()

df = load_data()

if df is not None:
    # Filtro de Nível (Mostra o nível do usuário e todos abaixo)
    if 'Nível' in df.columns:
        df['Nivel_Num_Tabela'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
        df_filtrado = df[df['Nivel_Num_Tabela'] <= st.session_state.nivel_usuario_num].copy()
        
        st.subheader("📅 Próximas Atividades")
        
        # Ajuste de visualização de colunas
        colunas_exibir = ['Nome do Evento ou da Atividade', 'Data Específica', 'Nível', 'Voluntário 1', 'Voluntário 2']
        cols_final = [c for c in colunas_exibir if c in df_filtrado.columns]
        
        st.dataframe(df_filtrado[cols_final], use_container_width=True, hide_index=True)
    else:
        st.warning("A coluna 'Nível' não foi encontrada na planilha.")

