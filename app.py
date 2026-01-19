import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import textwrap
import re

# --- 1. CONFIGURAÇÃO DE ACESSO (VERSÃO SECRETS) ---
@st.cache_resource
def get_gspread_client():
    try:
        # Reconstrução robusta (S1 a S21)
        partes = [f"S{i}" for i in range(1, 22)]
        chave_full = ""
        for p in partes:
            if p in st.secrets:
                # Remove espaços, quebras de linha e caracteres invisíveis
                limpo = re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets[p])
                chave_full += limpo
        
        # Formatação PEM rigorosa
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
        st.error(f"Erro crítico na autenticação: {e}")
        st.stop()

def load_data():
    client = get_gspread_client()
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    ss = client.open_by_key(spreadsheet_id)
    sheet = ss.worksheet("Calendario_Eventos")
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 2. CONFIGURAÇÕES ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

dias_semana_pt = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
}

# --- 3. DIÁLOGO DE CONFIRMAÇÃO ---
@st.dialog("Confirmar Inscrição")
def confirmar_inscricao_dialog(sheet, linha, row_data, vaga_nome, col_index):
    st.info(f"Você está preenchendo a vaga: **{vaga_nome}**")
    
    # Tabela de resumo para o Double Check
    resumo = {
        "Campo": ["Evento", "Departamento", "Nível", "Data", "Dia"],
        "Informação": [
            row_data['Nome do Evento ou da Atividade'],
            row_data.get('Departamento Responsável', 'N/A'),
            row_data['Nível'],
            row_data['Data Formatada'].strftime('%d/%m/%Y'),
            row_data['Dia da Semana']
        ]
    }
    st.table(pd.DataFrame(resumo))
    
    st.write(f"Confirmar inscrição para **{st.session_state.nome_usuario}**?")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Confirmar", type="primary", use_container_width=True):
            with st.spinner("Acessando Planilha..."):
                sheet.update_cell(linha, col_index, st.session_state.nome_usuario)
                st.success("Inscrito!")
                st.cache_resource.clear()
                st.rerun()
    with c2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()

# --- 4. FLUXO DE LOGIN ---
st.set_page_config(page_title="Portal ProVida", layout="wide")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login do Voluntário")
    with st.form("login"):
        nome = st.text_input("Nome Completo")
        nivel = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Acessar"):
            if nome:
                st.session_state.update({"nome_usuario": nome, "nivel_usuario_num": mapa_niveis[nivel], "autenticado": True})
                st.rerun()
    st.stop()

# --- 5. CARREGAMENTO E FILTROS ---
try:
    sheet, df = load_data()
    
    # Tratamento de Colunas e Datas
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df['Data_Dt'] = pd.to_datetime(df['Data Específica'], errors='coerce')
    df['Data Formatada'] = df['Data_Dt'].dt.date
    df['Dia da Semana'] = df['Data_Dt'].dt.weekday.map(dias_semana_pt)
    
    st.title(f"🤝 Bem-vindo, {st.session_state.nome_usuario}")

    # Filtros
    with st.expander("🔍 Filtros de Busca", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            f_evento = st.selectbox("Evento", ["Todos"] + sorted(df[df['Nome do Evento ou da Atividade'] != '']['Nome do Evento ou da Atividade'].unique().tolist()))
        with c2:
            depto_col = 'Departamento Responsável'
            f_depto = st.selectbox("Departamento", ["Todos"] + sorted(df[df[depto_col] != ''][depto_col].unique().tolist()))
        with c3:
            f_nivel = st.selectbox("Nível da Atividade", ["Todos"] + list(mapa_niveis.keys()))
        with c4:
            f_data = st.date_input("A partir de", datetime.now().date())
        
        ocultar_cheios = st.checkbox("Ocultar atividades com escala completa (2 voluntários)")

    # Lógica de Visibilidade por Nível
    def visivel(row, n_user):
        t = str(row.get('Tipo', '')).strip()
        n_ev = row['Nivel_Num']
        if t in ["Aberto a não alunos", "Aberto a todos os níveis"]: return True
        if t == "Somente o nível da atividade": return n_user == n_ev
        if t == "Nível da atividade e superiores": return n_user >= n_ev
        if t == "Nível da atividade e inferiores": return n_user <= n_ev
        return n_user >= n_ev

    df['Pode_Ver'] = df.apply(lambda r: visivel(r, st.session_state.nivel_usuario_num), axis=1)
    df_f = df[(df['Pode_Ver']) & (df['Data Formatada'] >= f_data)].copy()

    if f_evento != "Todos": df_f = df_f[df_f['Nome do Evento ou da Atividade'] == f_evento]
    if f_depto != "Todos": df_f = df_f[df_f[depto_col] == f_depto]
    if f_nivel != "Todos": df_f = df_f[df_f['Nível'] == f_nivel]
    
    if ocultar_cheios:
        df_f = df_f[~((df_f['Voluntário 1'].astype(str).str.strip() != "") & (df_f['Voluntário 2'].astype(str).str.strip() != ""))]

    # --- 6. INSCRIÇÃO ---
    st.subheader("📝 Escolha sua Atividade")
    df_vagas = df_f[(df_f['Voluntário 1'].astype(str).str.strip() == "") | (df_f['Voluntário 2'].astype(str).str.strip() == "")].copy()

    if not df_vagas.empty:
        df_vagas['label'] = df_vagas.apply(lambda x: f"{x[depto_col]} | {x['Nome do Evento ou da Atividade']} | {x['Nível']} | {x['Data Formatada'].strftime('%d/%m')} ({x['Dia da Semana']})", axis=1)
        item = st.selectbox("Atividades com vaga disponível:", df_vagas['label'].tolist())
        
        if st.button("Quero me inscrever", type="primary"):
            idx = df_vagas[df_vagas['label'] == item].index[0]
            linha = int(idx) + 2
            vals = sheet.row_values(linha)
            # Vol 1 está na coluna 7 (G), Vol 2 na 8 (H)
            v1_vazio = True if len(vals) < 7 or not str(vals[6]).strip() else False
            confirmar_inscricao_dialog(sheet, linha, df_vagas.loc[idx], ("Voluntário 1" if v1_vazio else "Voluntário 2"), (7 if v1_vazio else 8))
    else:
        st.info("Nenhuma vaga disponível com os filtros atuais.")

    # --- 7. TABELA ---
    st.subheader("📋 Escala de Voluntários")
    cols = ['Nome do Evento ou da Atividade', 'Data Formatada', 'Dia da Semana', 'Nível', 'Voluntário 1', 'Voluntário 2']
    st.dataframe(df_f[cols], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro ao processar dados: {e}")

if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()
