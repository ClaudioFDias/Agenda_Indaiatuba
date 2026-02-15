import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, date
import textwrap
import re
import time

# --- 1. CONEXÃO RESILIENTE ---
@st.cache_resource
def get_gspread_client():
    try:
        partes = [f"S{i}" for i in range(1, 22)]
        chave_full = "".join([re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets[p]) for p in partes])
        key_lines = textwrap.wrap(chave_full, 64)
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"
        creds_info = {
            "type": st.secrets["TYPE"], "project_id": st.secrets["PROJECT_ID"],
            "private_key_id": st.secrets["PRIVATE_KEY_ID"], "private_key": formatted_key,
            "client_email": st.secrets["CLIENT_EMAIL"], "client_id": st.secrets["CLIENT_ID"],
            "auth_uri": st.secrets["AUTH_URI"], "token_uri": st.secrets["TOKEN_URI"],
            "auth_provider_x509_cert_url": st.secrets["AUTH_PROVIDER_X509_CERT_URL"],
            "client_x509_cert_url": st.secrets["CLIENT_X509_CERT_URL"]
        }
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception:
        st.error("Erro crítico de conexão."); st.stop()

@st.cache_data(ttl=60)
def load_admin_data():
    client = get_gspread_client()
    try:
        ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
        df_ev = pd.DataFrame(ss.worksheet("Calendario_Eventos").get_all_records())
        df_ev.columns = [c.strip() for c in df_ev.columns]
        df_us = pd.DataFrame(ss.worksheet("Usuarios").get_all_records())
        df_us.columns = [c.strip() for c in df_us.columns]
        df_dir = pd.DataFrame(ss.worksheet("Diretores").get_all_records())
        df_dir.columns = [c.strip() for c in df_dir.columns]
        return df_ev, df_us, df_dir
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}"); st.stop()

def get_sheets():
    client = get_gspread_client()
    ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    return ss.worksheet("Calendario_Eventos"), ss.worksheet("Usuarios")

# --- 2. CONFIGURAÇÕES ---
cores_niveis = {
    "Nenhum": "#FFFFFF", "BAS": "#C8E6C9", "AV1": "#FFCDD2", "IN": "#BBDEFB",
    "AV2": "#795548", "AV2-24": "#795548", "AV2-23": "#795548", "AV2/": "#795548",
    "AV3": "#E1BEE7", "AV3A": "#E1BEE7", "AV3/": "#E1BEE7", "AV4": "#FFF9C4", "AV4A": "#FFF9C4"
}
mapa_niveis_num = {k: i for i, k in enumerate(cores_niveis.keys())}
dias_semana = {"Monday": "Segunda-feira", "Tuesday": "Terça-feira", "Wednesday": "Quarta-feira", "Thursday": "Quinta-feira", "Friday": "Sexta-feira", "Saturday": "Sábado", "Sunday": "Domingo"}

# --- 3. DIALOGS ---
@st.dialog("Gerenciar Inscrição")
def gerenciar_inscricao_dialog(linha_planilha, row_data, v_index, df_us, df_ev):
    st.subheader("Inscrever Voluntário")
    st.info(f"📍 {row_data['Departamento']} | ⏰ {row_data['Horario']}")
    nivel_at = mapa_niveis_num.get(str(row_data['Nível']).strip(), 0)
    usuarios_aptos = []
    for _, u in df_us.iterrows():
        u_deps = [d.strip() for d in str(u['Departamentos']).split(",")]
        u_nivel = mapa_niveis_num.get(str(u['Nivel']).strip(), 0)
        if row_data['Departamento'] in u_deps and u_nivel >= nivel_at:
            conflito = df_ev[(df_ev['Data Específica'] == row_data['Data Específica']) & (df_ev['Horario'] == row_data['Horario']) & ((df_ev['Voluntário 1'] == u['Nome']) | (df_ev['Voluntário 2'] == u['Nome']))]
            if conflito.empty: usuarios_aptos.append(f"{u['Nome']} ({u['Nivel']})")

    if not usuarios_aptos: st.warning("Nenhum voluntário apto disponível.")
    else:
        u_sel = st.selectbox("Selecione:", [""] + sorted(usuarios_aptos))
        if st.button("Confirmar", type="primary", use_container_width=True) and u_sel:
            sheet_ev, _ = get_sheets()
            sheet_ev.update_cell(linha_planilha, v_index, u_sel.split(" (")[0])
            st.cache_data.clear(); st.rerun()

@st.dialog("Cancelar Inscrição")
def cancelar_dialog(linha, col_idx, nome):
    st.warning(f"Remover **{nome}**?")
    if st.button("Sim, Remover", type="primary", use_container_width=True):
        sheet_ev, _ = get_sheets()
        sheet_ev.update_cell(linha, col_idx, "")
        st.cache_data.clear(); st.rerun()

# --- 4. STYLE & INIT ---
st.set_page_config(page_title="Gestor ProVida", layout="wide")
if 'admin' not in st.session_state: st.session_state.admin = None
if 'menu_admin' not in st.session_state: st.session_state.menu_admin = "📅 Gestão de Escala"
if 'aba_index' not in st.session_state: st.session_state.aba_index = 0

df_ev, df_us, df_dir = load_admin_data()

# --- 5. LOGIN ---
if st.session_state.admin is None:
    st.title("🛡️ Painel do Gestor")
    with st.form("login_admin"):
        em = st.text_input("E-mail de Diretor:").strip().lower()
        if st.form_submit_button("Acessar", type="primary", use_container_width=True):
            if em in df_dir['Email'].astype(str).str.lower().values:
                st.session_state.admin = em
                st.rerun()
            else: st.error("Acesso negado.")
    st.stop()

# --- 6. NAVEGAÇÃO ---
# O segredo está na 'key' para controlar via session_state
st.sidebar.radio("Navegação", ["📅 Gestão de Escala", "👥 Gestão de Usuários"], key="menu_admin")
if st.sidebar.button("Sair"): st.session_state.admin = None; st.rerun()

# --- 7. MÓDULOS ---

if st.session_state.menu_admin == "👥 Gestão de Usuários":
    st.title("Gestão de Voluntários")
    
    # Controlamos qual aba está ativa pelo session_state
    abas = ["Criar Novo", "Alterar Existente"]
    aba_selecionada = st.tabs(abas)
    
    # ABA 1: CRIAR NOVO
    with aba_selecionada[0]:
        with st.form("novo_user"):
            n_email = st.text_input("E-mail:").strip().lower()
            n_nome = st.text_input("Nome Crachá:")
            n_tel = st.text_input("Telefone:")
            n_deps = st.multiselect("Departamentos:", options=sorted(df_ev['Departamento'].unique().tolist()))
            n_niv = st.selectbox("Nível:", list(cores_niveis.keys()))
            
            if st.form_submit_button("Cadastrar", type="primary"):
                if n_email in df_us['Email'].astype(str).str.lower().values:
                    # AQUI O REDIRECIONAMENTO CORRIGIDO:
                    st.session_state.user_to_edit = n_email
                    st.session_state.aba_index = 1 # Indica que queremos a aba de edição
                    st.warning("E-mail já cadastrado! Redirecionando...")
                    time.sleep(1)
                    st.rerun()
                else:
                    _, s_us = get_sheets()
                    s_us.append_row([n_email, n_nome, n_tel, ",".join(n_deps), n_niv])
                    st.cache_data.clear(); st.success("Cadastrado!"); time.sleep(1); st.rerun()

    # ABA 2: ALTERAR EXISTENTE
    with aba_selecionada[1]:
        u_list = df_us['Email'].tolist()
        
        # Se houve redirecionamento, seleciona o e-mail certo
        default_email = st.session_state.get('user_to_edit', u_list[0] if u_list else "")
        try: d_idx = u_list.index(default_email)
        except: d_idx = 0
            
        s_u_email = st.selectbox("Usuário:", u_list, index=d_idx)
        if s_u_email:
            u_data = df_us[df_us['Email'] == s_u_email].iloc[0]
            with st.form("edit_user"):
                e_nome = st.text_input("Nome:", value=u_data['Nome'])
                e_tel = st.text_input("Telefone:", value=u_data['Telefone'])
                e_deps = st.multiselect("Deps:", options=sorted(df_ev['Departamento'].unique().tolist()), 
                                        default=[d.strip() for d in str(u_data['Departamentos']).split(",") if d])
                e_niv = st.selectbox("Nível:", list(cores_niveis.keys()), index=list(cores_niveis.keys()).index(u_data['Nivel']))
                
                if st.form_submit_button("Salvar"):
                    _, s_us = get_sheets()
                    r_idx = df_us[df_us['Email'] == s_u_email].index[0] + 2
                    s_us.update(f"B{r_idx}:E{r_idx}", [[e_nome, e_tel, ",".join(e_deps), e_niv]])
                    # Limpa o redirecionamento após salvar
                    if 'user_to_edit' in st.session_state: del st.session_state['user_to_edit']
                    st.cache_data.clear(); st.success("Atualizado!"); time.sleep(1); st.rerun()

else: # 📅 Gestão de Escala
    st.title("Painel de Escala Geral")
    col_f1, col_f2 = st.columns(2)
    with col_f1: f_data = st.date_input("Data:", value=date.today())
    with col_f2: f_dep = st.selectbox("Depto:", ["Todos"] + sorted(df_ev['Departamento'].unique().tolist()))

    df_ev['Data_Dt'] = pd.to_datetime(df_ev['Data Específica'], dayfirst=True)
    df_f = df_ev[df_ev['Data_Dt'].dt.date >= f_data].copy()
    if f_dep != "Todos": df_f = df_f[df_f['Departamento'] == f_dep]

    for idx, row in df_f.sort_values(['Data_Dt', 'Horario']).iterrows():
        bg = cores_niveis.get(str(row['Nível']).strip(), "#f0f0f0")
        st.markdown(f'<div style="background:{bg}; padding:10px; border-radius:10px; border:1px solid #ddd; margin-bottom:5px;"><b>{row["Data Específica"]} | {row["Horario"]}</b><br>{row["Nível"]} - {row["Nome do Evento"]} ({row["Departamento"]})</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        for i, c_name in enumerate(['Voluntário 1', 'Voluntário 2']):
            with [c1, c2][i]:
                nm = str(row[c_name]).strip()
                if nm and nm not in ["", "---", "nan"]:
                    if st.button(f"🗑️ {nm}", key=f"r_{idx}_{i}", use_container_width=True): cancelar_dialog(idx+2, 8+i, nm)
                else:
                    if st.button(f"➕ Vaga {i+1}", key=f"a_{idx}_{i}", use_container_width=True): gerenciar_inscricao_dialog(idx+2, row, 8+i, df_us, df_ev)
        st.divider()
