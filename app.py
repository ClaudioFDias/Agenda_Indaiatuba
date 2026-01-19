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

# --- 2. CONFIGURAÇÕES ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

dias_semana_pt = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
}

# --- 3. DIÁLOGO DE CONFIRMAÇÃO REESTRUTURADO ---
@st.dialog("Confirmar Inscrição")
def confirmar_inscricao_dialog(sheet, linha, row_data, vaga_nome, col_index, col_evento):
    st.markdown(f"### 📋 Resumo da Atividade")
    
    # Formato Rótulo: Valor
    st.markdown(f"**🔹 Evento:** {row_data[col_evento]}")
    st.markdown(f"**🔹 Nível:** {row_data['Nível']}")
    st.markdown(f"**🔹 Data:** {row_data['Data_Formatada'].strftime('%d/%m/%Y')} ({row_data['Dia_da_Semana']})")
    st.markdown(f"**🔹 Vaga:** {vaga_nome}")
    
    st.divider()
    st.write(f"Deseja confirmar sua inscrição como **{st.session_state.nome_usuario}**?")
    
    if st.button("✅ Confirmar Agora", type="primary", use_container_width=True):
        with st.spinner("Gravando na planilha..."):
            sheet.update_cell(linha, col_index, st.session_state.nome_usuario)
            st.success("Inscrição confirmada!")
            st.cache_resource.clear()
            st.rerun()

# --- 4. FLUXO DE LOGIN ---
st.set_page_config(page_title="Portal ProVida", layout="wide")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login")
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
    
    col_evento = next((c for c in df.columns if 'Evento' in c), 'Nome do Evento')
    col_depto = next((c for c in df.columns if 'Departamento' in c), 'Departamento Responsável')
    
    df['Data_Dt'] = pd.to_datetime(df['Data Específica'], errors='coerce')
    df['Data_Formatada'] = df['Data_Dt'].dt.date
    df['Dia_da_Semana'] = df['Data_Dt'].dt.weekday.map(dias_semana_pt)
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)

    st.title(f"🤝 Olá, {st.session_state.nome_usuario}")

    with st.sidebar:
        st.header("🔍 Filtros")
        f_ev = st.selectbox("Evento", ["Todos"] + sorted(df[df[col_evento] != ''][col_evento].unique().tolist()))
        f_dep = st.selectbox("Departamento", ["Todos"] + sorted(df[df[col_depto] != ''][col_depto].unique().tolist()))
        f_niv = st.selectbox("Nível da Atividade", ["Todos"] + list(mapa_niveis.keys()))
        f_dat = st.date_input("A partir de", datetime.now().date())
        ocultar = st.checkbox("Ocultar escalas cheias", value=False)
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.rerun()

    # Lógica de Visibilidade
    def visivel(row, n_user):
        t = str(row.get('Tipo', '')).strip()
        n_ev = row['Nivel_Num']
        if t in ["Aberto a não alunos", "Aberto a todos os níveis"]: return True
        return n_user >= n_ev # Simplificado para facilitar a experiência

    df['Pode_Ver'] = df.apply(lambda r: visivel(r, st.session_state.nivel_usuario_num), axis=1)
    df_f = df[(df['Pode_Ver']) & (df['Data_Formatada'] >= f_dat)].copy()

    if f_ev != "Todos": df_f = df_f[df_f[col_evento] == f_ev]
    if f_dep != "Todos": df_f = df_f[df_f[col_depto] == f_dep]
    if f_niv != "Todos": df_f = df_f[df_f['Nível'] == f_niv]
    
    if ocultar:
        df_f = df_f[~((df_f['Voluntário 1'].astype(str).str.strip() != "") & (df_f['Voluntário 2'].astype(str).str.strip() != ""))]

    # --- 6. ESCALA INTERATIVA (CLIQUE NA TABELA) ---
    st.subheader("📋 Escala de Atividades")
    st.info("💡 **Dica:** Clique em uma linha da tabela abaixo para se inscrever rapidamente.")

    cols_tabela = [col_evento, 'Data_Formatada', 'Dia_da_Semana', 'Nível', 'Voluntário 1', 'Voluntário 2']
    
    # Criamos a tabela com seleção de linha habilitada
    event = st.dataframe(
        df_f[cols_tabela], 
        use_container_width=True, 
        hide_index=True,
        on_select="rerun", # Faz o app rodar ao clicar na linha
        selection_mode="single-row"
    )

    # Lógica para quando o usuário clica na tabela
    if event.selection.rows:
        selected_index = event.selection.rows[0]
        row_selecionada = df_f.iloc[selected_index]
        
        # Verificar se ainda há vagas
        v1 = str(row_selecionada['Voluntário 1']).strip()
        v2 = str(row_selecionada['Voluntário 2']).strip()
        
        if v1 == "" or v2 == "":
            # Encontrar a linha real na planilha (baseado no index original do DF)
            linha_original = int(row_selecionada.name) + 2
            
            vaga_nome = "Voluntário 1" if v1 == "" else "Voluntário 2"
            col_alvo = 7 if v1 == "" else 8
            
            confirmar_inscricao_dialog(sheet, linha_original, row_selecionada, vaga_nome, col_alvo, col_evento)
        else:
            st.error("Esta atividade já está com a escala completa!")

except Exception as e:
    st.error(f"Erro ao processar os dados: {e}")
