import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import textwrap
import re

# --- 1. CONEXÃO ---
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
        st.error("Erro de conexão."); st.stop()

def load_data():
    client = get_gspread_client()
    ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    sheet_ev = ss.worksheet("Calendario_Eventos")
    sheet_us = ss.worksheet("Usuarios") # Certifique-se que esta aba existe
    
    df_ev = pd.DataFrame(sheet_ev.get_all_records())
    df_us = pd.DataFrame(sheet_us.get_all_records())
    
    return sheet_ev, sheet_us, df_ev, df_us

# --- 2. CONFIGURAÇÕES ---
cores_niveis = {
    "Nenhum": "#FFFFFF", "BAS": "#C8E6C9", "AV1": "#FFCDD2", "IN": "#BBDEFB",
    "AV2": "#795548", "AV2-24": "#795548", "AV2-23": "#795548", "AV2/": "#795548",
    "AV3": "#E1BEE7", "AV3A": "#E1BEE7", "AV3/": "#E1BEE7", "AV4": "#FFF9C4", "AV4A": "#FFF9C4"
}

lista_deps = ["Rede Global", "Cultural", "Portaria", "Estacionamento"]
mapa_niveis_num = {k: i for i, k in enumerate(cores_niveis.keys())}

def info_status(row):
    v1 = str(row.get('Voluntário 1', '')).strip()
    v2 = str(row.get('Voluntário 2', '')).strip()
    if v1 == "" and v2 == "": return "🔴 2 Vagas"
    if v1 == "" or v2 == "": return "🟡 1 Vaga"
    return "🟢 Completo"

# --- 3. DIALOG DE CONFIRMAÇÃO ---
@st.dialog("Confirmar Inscrição")
def confirmar_dialog(sheet, linha, row, vaga_n, col_idx):
    st.markdown(f"### {row['Nome do Evento']}")
    st.write(f"👤 **Vaga:** {vaga_n}")
    if st.button("Confirmar", type="primary", width="stretch"):
        sheet.update_cell(linha, col_idx, st.session_state.user['Nome'])
        st.cache_resource.clear()
        st.rerun()

# --- 4. FLUXO DE LOGIN / CADASTRO ---
st.set_page_config(page_title="ProVida Escala", layout="centered")

if 'user' not in st.session_state: st.session_state.user = None
if 'email_input' not in st.session_state: st.session_state.email_input = ""

sheet_ev, sheet_us, df_ev, df_us = load_data()

if st.session_state.user is None:
    st.title("🤝 Bem-vindo à Escala")
    
    email = st.text_input("Digite seu e-mail para acessar:", value=st.session_state.email_input).strip().lower()
    
    if email:
        # Busca usuário no DF
        user_row = df_us[df_us['Email'].str.lower() == email]
        
        if not user_row.empty:
            # USUÁRIO EXISTE: Login Automático
            user_data = user_row.iloc[0].to_dict()
            st.session_state.user = user_data
            st.success(f"Olá {user_data['Nome']}, identificamos seu cadastro!")
            if st.button("Entrar no Sistema"): st.rerun()
        else:
            # USUÁRIO NÃO EXISTE: Tela de Inscrição
            st.warning("E-mail não encontrado. Vamos fazer seu cadastro!")
            with st.form("cadastro"):
                nome = st.text_input("Nome como está no crachá:")
                tel = st.text_input("Telefone (ex: 11999999999):")
                deps = st.multiselect("Departamentos que você participa:", lista_deps)
                niv = st.selectbox("Nível do Curso:", list(cores_niveis.keys()))
                
                if st.form_submit_button("Finalizar Cadastro"):
                    if nome and tel and deps:
                        nova_linha = [email, nome, tel, ",".join(deps), niv]
                        sheet_us.append_row(nova_linha)
                        st.session_state.user = {"Email": email, "Nome": nome, "Telefone": tel, "Departamentos": ",".join(deps), "Nivel": niv}
                        st.cache_resource.clear()
                        st.rerun()
                    else:
                        st.error("Por favor, preencha todos os campos.")
    st.stop()

# --- 5. DASHBOARD (LOGADO) ---
user = st.session_state.user
st.title(f"🤝 Olá, {user['Nome'].split()[0]}!")

# Filtros Automáticos baseados no cadastro
meus_deps = user['Departamentos'].split(",")
nivel_usuario_num = mapa_niveis_num.get(user['Nivel'], 0)

# Interface de Filtros
with st.expander("🔍 Preferências de Visualização"):
    f_dat = st.date_input("A partir de:", datetime.now().date())
    filtro_status = st.pills("Status:", ["Tudo", "Minhas Inscrições", "Vagas Abertas"], default="Tudo")

# Processamento da Escala
df_ev['Data_Dt'] = pd.to_datetime(df_ev['Data Específica'], errors='coerce', dayfirst=True)
df_ev['Niv_N'] = df_ev['Nível'].astype(str).str.strip().map(mapa_niveis_num).fillna(99)
df_ev = df_ev.sort_values(by=['Data_Dt', 'Horario']).reset_index(drop=False)

# Filtro 1: Apenas departamentos que o usuário participa E nível compatível
df_f = df_ev[
    (df_ev['Departamento'].isin(meus_deps)) & 
    (df_ev['Niv_N'] <= nivel_usuario_num) & 
    (df_ev['Data_Dt'].dt.date >= f_dat)
].copy()

# Filtros de Status
if filtro_status == "Minhas Inscrições":
    nome_l = user['Nome'].strip().lower()
    df_f = df_f[(df_f['Voluntário 1'].astype(str).str.lower() == nome_l) | (df_f['Voluntário 2'].astype(str).str.lower() == nome_l)]
elif filtro_status == "Vagas Abertas":
    df_f = df_f[df_f.apply(lambda x: "Vaga" in info_status(x), axis=1)]

# --- 6. EXIBIÇÃO DOS CARDS ---
for i, row in df_f.iterrows():
    status_txt = info_status(row)
    bg_cor = cores_niveis.get(str(row['Nível']).strip(), "#FFFFFF")
    txt_cor = "#FFFFFF" if "AV2" in str(row['Nível']) else "#000000"
    v1, v2 = str(row['Voluntário 1']).strip(), str(row['Voluntário 2']).strip()
    
    ja_inscrito = (v1.lower() == user['Nome'].lower() or v2.lower() == user['Nome'].lower())
    cheio = (v1 != "" and v2 != "")

    st.markdown(f"""
        <div style="background-color: {bg_cor}; padding: 15px; border-radius: 10px 10px 0 0; border: 1px solid #ddd; color: {txt_cor}; margin-top: 15px;">
            <div style="display: flex; justify-content: space-between; font-weight: 800; font-size: 0.85em;">
                <span>{status_txt}</span>
                <span>{row['Data_Dt'].strftime('%d/%m')}</span>
            </div>
            <h3 style="margin: 5px 0; color: {txt_cor}; border: none;">{row['Nome do Evento']}</h3>
            <div style="font-size: 0.9em; font-weight: 600; opacity: 0.85; margin-bottom: 5px;">🏢 {row['Departamento']}</div>
            <div style="font-size: 0.9em; margin-bottom: 8px;">⏰ {row['Horario']} | 🎓 Nível: {row['Nível']}</div>
            <div style="background: rgba(0,0,0,0.15); padding: 8px; border-radius: 5px; font-size: 0.9em;">
                <b>V1:</b> {v1}<br><b>V2:</b> {v2}
            </div>
        </div>
    """, unsafe_allow_html=True)

    if ja_inscrito:
        st.button("✅ INSCRITO", key=f"btn_{i}", disabled=True, width="stretch")
    elif cheio:
        st.button("🚫 COMPLETO", key=f"btn_{i}", disabled=True, width="stretch")
    else:
        if st.button("Quero me inscrever", key=f"btn_{i}", type="primary", width="stretch"):
            v_alvo, c_alvo = ("Voluntário 1", 8) if v1 == "" else ("Voluntário 2", 9)
            confirmar_dialog(sheet_ev, int(row['index'])+2, row, v_alvo, c_alvo)

if st.button("Sair / Trocar Usuário"):
    st.session_state.user = None
    st.rerun()
