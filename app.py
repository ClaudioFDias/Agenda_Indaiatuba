import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

# --- 1. CONEXÃO USANDO O JSON INTEGRAL ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # Lê o JSON completo que você colou no Secrets
        info = json.loads(st.secrets["GCP_JSON"])
        
        # O ServiceAccountCredentials resolve os problemas de \n automaticamente
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro ao processar credenciais: {e}")
        st.stop()

# --- 2. CARREGAMENTO DE DADOS ---
def load_data():
    client = get_gspread_client()
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    ss = client.open_by_key(spreadsheet_id)
    sheet = ss.worksheet("Calendario_Eventos")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    # Limpa espaços nos nomes das colunas
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 3. CONFIGURAÇÃO E LOGIN ---
st.set_page_config(page_title="Portal de Voluntários", page_icon="🤝", layout="wide")

mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Portal ProVida")
    with st.form("login"):
        nome = st.text_input("Nome Completo")
        nivel = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Entrar"):
            if nome:
                st.session_state.nome_usuario = nome
                st.session_state.nivel_usuario_num = mapa_niveis[nivel]
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Digite seu nome.")
    st.stop()

# --- 4. TELA PRINCIPAL ---
try:
    sheet, df = load_data()
    st.success(f"Bem-vindo, {st.session_state.nome_usuario}!")

    # Tratamento simples de datas (ajuste o nome da coluna se necessário)
    if 'Data Específica' in df.columns:
        df['Data Formatada'] = pd.to_datetime(df['Data Específica'], errors='coerce').dt.date
    
    # Filtro de visibilidade baseado no nível
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df_visivel = df[df['Nivel_Num'] <= st.session_state.nivel_usuario_num].copy()

    st.subheader("📅 Calendário de Escala")
    colunas_finais = ['Nome do Evento ou da Atividade', 'Data Formatada', 'Nível', 'Voluntário 1', 'Voluntário 2']
    # Exibe apenas se as colunas existirem
    cols_existentes = [c for c in colunas_finais if c in df_visivel.columns]
    st.dataframe(df_visivel[cols_existentes], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro ao carregar a planilha: {e}")

if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()

# --- 5. INTERFACE PRINCIPAL ---
try:
    sheet, df = load_data()
    st.title(f"Olá, {st.session_state.nome_usuario}!")
    
    # Processamento de datas
    df['Data Formatada'] = pd.to_datetime(df['Data Específica']).dt.date
    
    # Filtro de Nível: vê o seu nível e inferiores
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df_visivel = df[df['Nivel_Num'] <= st.session_state.nivel_usuario_num].copy()

    st.subheader("📅 Escala de Atividades")
    cols = ['Nome do Evento ou da Atividade', 'Data Formatada', 'Nível', 'Voluntário 1', 'Voluntário 2']
    st.dataframe(df_visivel[cols], use_container_width=True, hide_index=True)

    # Botão de Inscrição Simples
    with st.expander("Fazer minha inscrição"):
        vagas_abertas = df_visivel[(df_visivel['Voluntário 1'] == "") | (df_visivel['Voluntário 2'] == "")]
        if not vagas_abertas.empty:
            opcao = st.selectbox("Escolha a atividade:", vagas_abertas['Nome do Evento ou da Atividade'].unique())
            if st.button("Confirmar minha participação"):
                st.info("Função de gravação pronta para ser acionada.")
        else:
            st.write("Nenhuma vaga aberta no seu nível.")

except Exception as e:
    st.error(f"Erro ao conectar: {e}")

if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()


