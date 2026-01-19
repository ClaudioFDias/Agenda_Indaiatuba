import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import textwrap
import re

# --- 1. CONFIGURAÇÃO DE ACESSO ---
@st.cache_resource
def get_gspread_client():
    try:
        partes = [f"S{i}" for i in range(1, 22)]
        chave_full = "".join([re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets[p]) for p in partes])
        key_lines = textwrap.wrap(chave_full, 64)
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"
        
        creds_info = {
            "type": st.secrets["TYPE"],
            "project_id": st.secrets["PROJECT_ID"],
            "private_key_id": st.secrets["PRIVATE_KEY_ID"],
            "private_key": formatted_key,
            "client_email": st.secrets["CLIENT_EMAIL"],
            "client_id": st.secrets["CLIENT_ID"],
            "auth_uri": st.secrets["AUTH_URI"],
            "token_uri": st.secrets["TOKEN_URI"],
            "auth_provider_x509_cert_url": st.secrets["AUTH_PROVIDER_X509_CERT_URL"],
            "client_x509_cert_url": st.secrets["CLIENT_X509_CERT_URL"]
        }
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na Autenticação: {e}")
        st.stop()

def load_data():
    client = get_gspread_client()
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    ss = client.open_by_key(spreadsheet_id)
    sheet = ss.worksheet("Calendario_Eventos")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 2. CONFIGURAÇÕES E DICIONÁRIOS ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

dias_semana_pt = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
}

# --- 3. FUNÇÃO DO OVERLAY DE CONFIRMAÇÃO ---
@st.dialog("Confirmar Inscrição")
def confirmar_inscricao_dialog(sheet, linha, row_data, vaga_nome, col_index):
    st.warning(f"Você está se inscrevendo como **{vaga_nome}**.")
    st.markdown(f"""
    ### 📋 Detalhes da Atividade
    - **Evento:** {row_data['Nome do Evento ou da Atividade']}
    - **Departamento:** {row_data['Departamento Responsável']}
    - **Nível:** {row_data['Nível']}
    - **Data:** {row_data['Data Formatada'].strftime('%d/%m/%Y')} ({row_data['Dia da Semana']})
    - **Voluntário Logado:** {st.session_state.nome_usuario}
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sim, Confirmar", type="primary", use_container_width=True):
            with st.spinner("Gravando..."):
                sheet.update_cell(linha, col_index, st.session_state.nome_usuario)
                st.success("Inscrição realizada!")
                st.cache_resource.clear()
                st.rerun()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()

# --- 4. INTERFACE ---
st.set_page_config(page_title="Portal ProVida", page_icon="🤝", layout="wide")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso ao Portal")
    with st.form("identificacao"):
        nome = st.text_input("Seu Nome Completo")
        nivel = st.selectbox("Seu Nível Atual", list(mapa_niveis.keys()))
        if st.form_submit_button("Acessar Calendário"):
            if nome:
                st.session_state.update({"nome_usuario": nome, "nivel_usuario_num": mapa_niveis[nivel], "autenticado": True})
                st.rerun()
            else: st.error("Insira seu nome.")
    st.stop()

# --- PROCESSAMENTO DE DADOS ---
sheet, df = load_data()
st.title(f"🤝 Olá, {st.session_state.nome_usuario}")

df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
df['Data Formatada'] = pd.to_datetime(df['Data Específica'], errors='coerce').dt.date
df['Dia da Semana'] = pd.to_datetime(df['Data Específica'], errors='coerce').dt.weekday.map(dias_semana_pt)

# Lógica de Visibilidade
def checar_visibilidade(row, nivel_user):
    tipo_ev = str(row.get('Tipo', '')).strip()
    nivel_ev = row['Nivel_Num']
    if tipo_ev in ["Aberto a não alunos", "Aberto a todos os níveis"]: return True
    if tipo_ev == "Somente o nível da atividade": return nivel_user == nivel_ev
    if tipo_ev == "Nível da atividade e superiores": return nivel_user >= nivel_ev
    if tipo_ev == "Nível da atividade e inferiores": return nivel_user <= nivel_ev
    return nivel_user >= nivel_ev

df['Visivel'] = df.apply(lambda row: checar_visibilidade(row, st.session_state.nivel_usuario_num), axis=1)
df_visivel = df[df['Visivel'] == True].copy()

# --- FILTROS ---
st.markdown("### 🔍 Filtros")
c1, c2, c3, c4 = st.columns(4)
col_nome_ev = 'Nome do Evento ou da Atividade'
col_depto = 'Departamento Responsável'

with c1:
    f_evento = st.selectbox("Evento", ["Todos"] + sorted(df_visivel[col_nome_ev].unique().tolist()))
with c2:
    f_depto = st.selectbox("Departamento", ["Todos"] + sorted(df_visivel[col_depto].unique().tolist()))
with c3:
    f_nivel = st.selectbox("Nível da Atividade", ["Todos"] + list(mapa_niveis.keys()))
with c4:
    f_data = st.date_input("A partir de:", datetime.now().date())

ocultar_cheios = st.checkbox("Ocultar atividades com vagas preenchidas", value=False)

# Aplicação dos Filtros
df_filtrado = df_visivel[df_visivel['Data Formatada'] >= f_data]
if f_evento != "Todos": df_filtrado = df_filtrado[df_filtrado[col_nome_ev] == f_evento]
if f_depto != "Todos": df_filtrado = df_filtrado[df_filtrado[col_depto] == f_depto]
if f_nivel != "Todos": df_filtrado = df_filtrado[df_filtrado['Nível'] == f_nivel]

# Lógica para ocultar cheios (ambos voluntários preenchidos)
if ocultar_cheios:
    df_filtrado = df_filtrado[~(
        (df_filtrado['Voluntário 1'].astype(str).str.strip() != "") & 
        (df_filtrado['Voluntário 2'].astype(str).str.strip() != "")
    )]

# --- ÁREA DE INSCRIÇÃO ---
st.markdown("---")
if not df_filtrado.empty:
    # Dropdown com informações ricas: Depto, Evento, Nível, Data, Dia Semana
    df_filtrado['label_completa'] = df_filtrado.apply(
        lambda x: f"{x[col_depto]} | {x[col_nome_ev]} | Nível: {x['Nível']} | {x['Data Formatada'].strftime('%d/%m')} ({x['Dia da Semana']})", axis=1
    )
    
    # Apenas quem tem pelo menos uma vaga
    df_com_vaga = df_filtrado[(df_filtrado['Voluntário 1'].astype(str).str.strip() == "") | 
                               (df_filtrado['Voluntário 2'].astype(str).str.strip() == "")].copy()
    
    if not df_com_vaga.empty:
        escolha = st.selectbox("Selecione a atividade para se inscrever:", df_com_vaga['label_completa'].tolist())
        if st.button("Me inscrever nesta atividade", type="primary"):
            idx_selecionado = df_com_vaga[df_com_vaga['label_completa'] == escolha].index[0]
            linha_planilha = int(idx_selecionado) + 2
            row_values = sheet.row_values(linha_planilha)
            
            v1_vazio = True if len(row_values) < 7 or not str(row_values[6]).strip() else False
            vaga_nome = "Voluntário 1" if v1_vazio else "Voluntário 2"
            col_alvo = 7 if v1_vazio else 8
            
            confirmar_inscricao_dialog(sheet, linha_planilha, df_com_vaga.loc[idx_selecionado], vaga_nome, col_alvo)
    else:
        st.warning("Todas as vagas filtradas já estão ocupadas.")
else:
    st.info("Nenhuma atividade encontrada.")

# --- ESCALA ATUAL ---
st.markdown("### 📋 Escala Atual")
# Coluna Tipo removida, Dia da Semana adicionado
colunas_exibir = [col_nome_ev, 'Data Formatada', 'Dia da Semana', 'Nível', 'Voluntário 1', 'Voluntário 2']
st.dataframe(df_filtrado[colunas_exibir], use_container_width=True, hide_index=True)

if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()
