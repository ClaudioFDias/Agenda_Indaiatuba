import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal de Voluntários ProVida", layout="wide")

# --- BLOCO DE DIAGNÓSTICO E CONEXÃO ---
@st.cache_resource
def get_gspread_client():
    try:
        # Camada 1: Leitura do Segredo
        if "GCP_JSON_ESTRITO" not in st.secrets:
            st.error("❌ Erro Camada 1: Secret 'GCP_JSON_ESTRITO' não encontrado.")
            st.stop()
        
        raw_json = st.secrets["GCP_JSON_ESTRITO"]
        
        # Camada 2: Conversão para Dicionário (JSON Parsing)
        try:
            info = json.loads(raw_json)
        except Exception as e:
            st.error(f"❌ Erro Camada 2 (JSON Inválido): {e}")
            st.code(raw_json[:100] + "...") # Mostra o início para conferência
            st.stop()
        
        # Camada 3: Tratamento da Chave Privada (O ponto crítico)
        if "private_key" in info:
            # Remove escapes literais e garante quebras de linha reais
            info["private_key"] = info["private_key"].replace("\\n", "\n")
            if "-----BEGIN PRIVATE KEY-----" not in info["private_key"]:
                st.error("❌ Erro Camada 3: Cabeçalho da chave privada está corrompido.")
                st.stop()
        else:
            st.error("❌ Erro Camada 3: Campo 'private_key' ausente no JSON.")
            st.stop()

        # Camada 4: Autenticação com o Google
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
            client = gspread.authorize(creds)
            return client
        except Exception as e:
            st.error(f"❌ Erro Camada 4 (Google Auth/JWT): {e}")
            st.stop()
            
    except Exception as e:
        st.error(f"❌ Erro Crítico Não Mapeado: {e}")
        st.stop()

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
