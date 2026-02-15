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

@st.dialog("Atenção")
def usuario_existe_dialog(email):
    st.warning(f"⚠️ O e-mail **{email}** já está cadastrado no sistema.")
    st.write("Para editar as informações deste voluntário, utilize a aba **'Alterar Existente'**.")
    if st.button("Entendi", type="primary", use_container_width=True):
        st.rerun()

@st.dialog("Gerenciar Inscrição")
def gerenciar_inscricao_dialog(linha_planilha, row_data, v_index, df_us, df_ev):
    st.subheader("Inscrever Voluntário")
    st.info(f"📍 {row_data['Departamento']} | ⏰ {row_data['Horario']}")
    nivel_atividade = mapa_niveis_num.get(str(row_data['Nível']).strip(), 0)
    usuarios_aptos = []
    for _, u in df_us.iterrows():
        u_deps = [d.strip() for d in str(u['Departamentos']).split(",")]
        u_nivel = mapa_niveis_num.get(str(u['Nivel']).strip(), 0)
        if row_data['Departamento'] in u_deps and u_nivel >= nivel_atividade:
            conflito = df_ev[(df_ev['Data Específica'] == row_data['Data Específica']) & (df_ev['Horario'] == row_data['Horario']) & ((df_ev['Voluntário 1'] == u['Nome']) | (df_ev['Voluntário 2'] == u['Nome']))]
            if conflito.empty:
                usuarios_aptos.append(f"{u['Nome']} ({u['Nivel']})")
    if not usuarios_aptos:
        st.warning("Nenhum voluntário disponível/apto para este horário.")
    else:
        u_selecionado = st.selectbox("Selecione o Voluntário:", [""] + sorted(usuarios_aptos))
        if st.button("Confirmar Inscrição", type="primary", use_container_width=True) and u_selecionado:
            nome_final = u_selecionado.split(" (")[0]
            sheet_ev, _ = get_sheets()
            sheet_ev.update_cell(linha_planilha, v_index, nome_final)
            st.cache_data.clear(); st.success("Inscrito!"); time.sleep(1); st.rerun()

@st.dialog("Cancelar Inscrição")
def cancelar_dialog(linha, col_idx, nome):
    st.warning(f"Tem certeza que deseja remover **{nome}** desta atividade?")
    if st.button("Sim, Remover", type="primary", use_container_width=True):
        sheet_ev, _ = get_sheets()
        sheet_ev.update_cell(linha, col_idx, "")
        st.cache_data.clear(); st.success("Removido!"); time.sleep(1); st.rerun()

# --- 4. STYLE ---
st.set_page_config(page_title="Gestor ProVida", layout="wide")
st.markdown("""
    <style>
    .card-container { padding: 15px; border-radius: 12px; border: 1px solid #ddd; margin-bottom: 10px; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    /* Esconde a barra lateral para focar nos botões superiores */
    [data-testid="stSidebar"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# --- 5. LOGIN ---
if 'admin' not in st.session_state: st.session_state.admin = None
if 'menu_ativo' not in st.session_state: st.session_state.menu_ativo = "escala"

df_ev, df_us, df_dir = load_admin_data()

if st.session_state.admin is None:
    st.title("🛡️ Painel do Gestor")
    with st.form("login_admin"):
        email = st.text_input("E-mail de Diretor:").strip().lower()
        if st.form_submit_button("Acessar Painel", type="primary", use_container_width=True):
            if email in df_dir['Email'].astype(str).str.lower().values:
                st.session_state.admin = email
                st.rerun()
            else:
                st.error("Acesso negado. E-mail não consta na lista de Diretores.")
    st.stop()

# IDENTIFICAÇÃO DO DEPARTAMENTO DO DIRETOR
depto_diretor = df_dir[df_dir['Email'].astype(str).str.lower() == st.session_state.admin]['Departamento'].iloc[0]

# --- 6. NAVEGAÇÃO SUPERIOR ---
c_nav1, c_nav2, c_nav3 = st.columns([1, 1, 0.5])
with c_nav1:
    if st.button("📅 Gestão de Escala", use_container_width=True, type="secondary" if st.session_state.menu_ativo == "usuarios" else "primary"):
        st.session_state.menu_ativo = "escala"
        st.rerun()
with c_nav2:
    if st.button("👥 Gestão de Usuários", use_container_width=True, type="secondary" if st.session_state.menu_ativo == "escala" else "primary"):
        st.session_state.menu_ativo = "usuarios"
        st.rerun()
with c_nav3:
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.admin = None
        st.rerun()

st.divider()

# --- 7. MÓDULOS ---

if st.session_state.menu_ativo == "usuarios":
    st.title(f"Gestão de Voluntários - {depto_diretor}")
    aba1, aba2 = st.tabs(["Criar Novo", "Alterar Existente"])
    
    with aba1:
        with st.form("novo_user"):
            new_email = st.text_input("E-mail:").strip().lower()
            new_nome = st.text_input("Nome Crachá:")
            new_tel = st.text_input("Telefone:")
            # Diretor só cadastra para o departamento dele
            new_deps = st.multiselect("Departamentos:", options=[depto_diretor], default=[depto_diretor])
            new_niv = st.selectbox("Nível:", list(cores_niveis.keys()))
            
            if st.form_submit_button("Cadastrar Voluntário", type="primary"):
                if new_email in df_us['Email'].astype(str).str.lower().values:
                    usuario_existe_dialog(new_email)
                else:
                    _, sheet_us = get_sheets()
                    sheet_us.append_row([new_email, new_nome, new_tel, ",".join(new_deps), new_niv])
                    st.cache_data.clear(); st.success("Cadastrado!"); time.sleep(1); st.rerun()

    with aba2:
        # Filtra lista de usuários que pertencem ao depto do diretor
        df_us_filtrado = df_us[df_us['Departamentos'].str.contains(depto_diretor, na=False)]
        user_list = df_us_filtrado['Email'].tolist()
        
        if not user_list:
            st.info("Nenhum voluntário cadastrado para seu departamento.")
        else:
            default_idx = user_list.index(st.session_state.get('user_to_edit')) if st.session_state.get('user_to_edit') in user_list else 0
            sel_user_email = st.selectbox("Selecione o usuário para editar:", user_list, index=default_idx)
            
            if sel_user_email:
                u_data = df_us[df_us['Email'] == sel_user_email].iloc[0]
                with st.form("edit_user"):
                    ed_nome = st.text_input("Nome:", value=u_data['Nome'])
                    ed_tel = st.text_input("Telefone:", value=u_data['Telefone'])
                    # Mantém travado no depto dele
                    ed_deps = st.multiselect("Departamentos:", options=[depto_diretor], default=[depto_diretor])
                    ed_niv = st.selectbox("Nível:", list(cores_niveis.keys()), index=list(cores_niveis.keys()).index(u_data['Nivel']))
                    
                    if st.form_submit_button("Salvar Alterações"):
                        _, sheet_us = get_sheets()
                        row_idx = df_us[df_us['Email'] == sel_user_email].index[0] + 2
                        sheet_us.update(f"B{row_idx}:E{row_idx}", [[ed_nome, ed_tel, ",".join(ed_deps), ed_niv]])
                        st.cache_data.clear(); st.success("Atualizado!"); time.sleep(1); st.rerun()

else: # 📅 Gestão de Escala
    st.title(f"Painel de Escala - {depto_diretor}")
    col_f1, col_f2 = st.columns([1, 2])
    
    with col_f1: 
        f_data = st.date_input("Filtrar Data:", value=date.today())
    
    with col_f2:
        # O filtro de departamento agora é restrito ao depto do diretor
        f_deptos_sel = st.multiselect(
            "Filtrar Departamentos:", 
            options=[depto_diretor],
            default=[depto_diretor],
            disabled=True # Travado para ele não ver outros
        )

    # --- Lógica de Filtragem ---
    df_ev['Data_Dt'] = pd.to_datetime(df_ev['Data Específica'], dayfirst=True)
    df_f = df_ev[df_ev['Data_Dt'].dt.date >= f_data].copy()

    # Filtra obrigatoriamente pelo depto do diretor logado
    df_f = df_f[df_f['Departamento'] == depto_diretor]

    df_f = df_f.sort_values(['Data_Dt', 'Horario'])

    # --- Renderização dos Cards ---
    if df_f.empty:
        st.info(f"Nenhum evento encontrado para {depto_diretor} nesta data.")
    else:
        for idx, row in df_f.iterrows():
            linha_planilha = idx + 2
            bg = cores_niveis.get(str(row['Nível']).strip(), "#f0f0f0")
            dia_nome = dias_semana.get(row['Data_Dt'].strftime('%A'), "")
            
            with st.container():
                st.markdown(f"""
                <div class="card-container" style="background-color: {bg}; border-left: 10px solid rgba(0,0,0,0.2);">
                    <div style="line-height: 1.6;">
                        <b>📅 Data: {row['Data Específica']} ({dia_nome})</b><br>
                        <b>⏰ Horário: {row['Horario']}</b><br>
                        <b>🎭 Evento: {row['Nível']} - {row['Nome do Evento']}</b><br>
                        <b>🏢 Departamento: {row['Departamento']}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                for i, col_name in enumerate(['Voluntário 1', 'Voluntário 2']):
                    with [c1, c2][i]:
                        vol_nome = str(row[col_name]).strip()
                        if vol_nome and vol_nome not in ["", "---", "nan"]:
                            st.success(f"**✅ {vol_nome}**")
                            if st.button(f"Remover {vol_nome.split()[0]}", key=f"rem_{idx}_{i}", use_container_width=True):
                                cancelar_dialog(linha_planilha, 8+i, vol_nome)
                        else:
                            if st.button(f"➕ Vaga {i+1}", key=f"add_{idx}_{i}", use_container_width=True):
                                gerenciar_inscricao_dialog(linha_planilha, row, 8+i, df_us, df_ev)
                st.divider()
