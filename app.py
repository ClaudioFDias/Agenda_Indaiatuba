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

@st.cache_data(ttl=300)
def load_data_cached():
    client = get_gspread_client()
    for tentativa in range(3):
        try:
            ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
            sheet_ev = ss.worksheet("Calendario_Eventos")
            data_ev = sheet_ev.get_all_records()
            df_ev = pd.DataFrame(data_ev)
            df_ev.columns = [c.strip() for c in df_ev.columns]
            sheet_us = ss.worksheet("Usuarios") 
            data_us = sheet_us.get_all_records()
            df_us = pd.DataFrame(data_us) if data_us else pd.DataFrame(columns=['Email', 'Nome', 'Telefone', 'Departamentos', 'Nivel'])
            df_us.columns = [c.strip() for c in df_us.columns]
            return df_ev, df_us
        except Exception:
            if tentativa < 2: time.sleep(2); continue
            else: st.error("Erro ao carregar dados."); st.stop()

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

@st.dialog("Conflito de Agenda")
def conflito_dialog(dados_conflito):
    st.warning("⚠️ **Você já possui uma atividade neste horário!**")
    st.markdown(f"""
    **Atividade conflitante:**
    * **Evento:** {dados_conflito['Nome do Evento']}
    * **Departamento:** {dados_conflito['Departamento']}
    * **Horário:** {dados_conflito['Horario']}
    """)
    if st.button("Entendido", type="primary", use_container_width=True): st.rerun()

@st.dialog("Confirmar Inscrição")
def confirmar_dialog(linha, row, col_idx):
    dia_nome = dias_semana.get(row['Data_Dt'].strftime('%A'), "")
    st.markdown("### Resumo da Inscrição:")
    st.info(f"""
    📅 **Data:** {row['Data Específica']} ({dia_nome})  
    ⏰ **Horário:** {row['Horario']}  
    🎭 **Evento:** {row['Nível']} - {row['Nome do Evento']}  
    🏢 **Departamento:** {row['Departamento']}
    """)
    st.write("Deseja confirmar sua participação nesta escala?")
    
    if st.button("Confirmar Inscrição", type="primary", use_container_width=True):
        with st.spinner("Salvando..."):
            sheet_ev, _ = get_sheets()
            sheet_ev.update_cell(linha, col_idx, st.session_state.user['Nome'])
            st.cache_data.clear(); st.rerun()

# --- 4. STYLE ---
st.set_page_config(page_title="ProVida Escala", layout="centered")
st.markdown("""
    <style>
    .public-card { padding: 15px; border-radius: 12px; border: 1px solid #ccc; margin-bottom: 20px; box-shadow: 2px 2px 8px rgba(0,0,0,0.1); }
    .public-title { font-size: 1.15em; font-weight: 800; margin-bottom: 10px; padding-bottom: 5px; border-bottom: 1px solid rgba(0,0,0,0.1); }
    .depto-box { margin-top: 8px; padding: 10px; background: rgba(255,255,255,0.75); border-radius: 8px; color: #111; }
    .vol-status { display: block; margin-top: 3px; font-size: 0.95em; }
    .vol-filled { color: #1b5e20; font-weight: 700; }
    .vol-empty { color: #b71c1c; font-weight: 700; font-style: italic; }
    .card-container { padding: 15px; border-radius: 12px 12px 0 0; border: 1px solid #ddd; margin-top: 15px; }
    </style>
""", unsafe_allow_html=True)

if 'user' not in st.session_state: st.session_state.user = None
if 'ver_painel' not in st.session_state: st.session_state.ver_painel = False

df_ev, df_us = load_data_cached()
df_ev['Data_Dt'] = pd.to_datetime(df_ev['Data Específica'], errors='coerce', dayfirst=True)
deps_na_planilha = sorted([d for d in df_ev['Departamento'].unique() if str(d).strip() != ""])

# --- 5. FLUXO DE TELAS ---

# A) PAINEL PÚBLICO
if st.session_state.ver_painel:
    st.title("🏃‍♂️ Responsáveis do Dia")
    if st.button("⬅️ Voltar"): st.session_state.ver_painel = False; st.rerun()
    data_sel = st.date_input("Filtrar data:", value=date.today())
    df_dia = df_ev[df_ev['Data_Dt'].dt.date == data_sel].copy()
    if df_dia.empty: st.warning("Nenhuma atividade encontrada.")
    else:
        for (nivel, nome_ev, horario), grupo in df_dia.sort_values(['Horario', 'Nível']).groupby(['Nível', 'Nome do Evento', 'Horario']):
            bg_c = cores_niveis.get(str(nivel).strip(), "#f8f9fa")
            tx_c = "#FFFFFF" if "AV2" in str(nivel) else "#000000"
            html_parts = [f'<div class="public-card" style="background-color: {bg_c}; color: {tx_c};">', f'<div class="public-title" style="border-color: {tx_c}44;">{nivel} - {nome_ev} - {horario}</div>']
            for _, row in grupo.iterrows():
                v1, v2 = str(row['Voluntário 1']).strip(), str(row['Voluntário 1']).strip() # (Ajuste técnico v1/v2)
                v1, v2 = str(row['Voluntário 1']).strip(), str(row['Voluntário 2']).strip()
                v1_st = f'<span class="vol-filled">🟢 {v1}</span>' if v1 and v1 not in ["", "---", "nan", "None"] else '<span class="vol-empty">🔴 Vaga Aberta</span>'
                v2_st = f'<span class="vol-filled">🟢 {v2}</span>' if v2 and v2 not in ["", "---", "nan", "None"] else '<span class="vol-empty">🔴 Vaga Aberta</span>'
                html_parts.append(f'<div class="depto-box"><b>🏢 {row["Departamento"]}</b><div class="vol-status">{v1_st}{v2_st}</div></div>')
            html_parts.append('</div>')
            st.markdown("".join(html_parts), unsafe_allow_html=True)
    st.stop()

# B) LOGIN
if st.session_state.user is None:
    st.title("🤝 Escala de Voluntários")
    if st.button("🔍 Ver Responsáveis do Dia (Público)", use_container_width=True):
        st.session_state.ver_painel = True; st.rerun()
    st.divider()

    with st.form("login"):
        em = st.text_input("E-mail para entrar:").strip().lower()
        if st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True):
            u = df_us[df_us['Email'].astype(str).str.lower() == em]
            if not u.empty: 
                st.session_state.user = u.iloc[0].to_dict()
                st.rerun()
            else: 
                st.error("⚠️ Acesso não autorizado. E-mail não encontrado na base de dados.")
    st.stop()

# --- 6. DASHBOARD (LOGADO) ---
user = st.session_state.user
meus_deps = [d.strip() for d in str(user['Departamentos']).split(",") if d.strip() and d.lower() not in ['nan', 'none']]
st.title(f"🤝 Olá, {user['Nome'].split()[0]}!")

filtro_status = st.pills("Status:", ["Vagas Abertas", "Vagas Vazias", "Minhas Inscrições", "Tudo"], default="Vagas Abertas")
f_depto_pill = st.pills("Departamento:", ["Todos"] + meus_deps, default="Todos")

c1, c2 = st.columns(2)
with c1: f_nivel = st.selectbox("Filtrar por Nível:", ["Todos"] + list(cores_niveis.keys()))
with c2: f_data = st.date_input("A partir de:", value=date.today())

df_ev['Niv_N'] = df_ev['Nível'].astype(str).str.strip().map(mapa_niveis_num).fillna(99)
df_ev = df_ev.sort_values(by=['Data_Dt', 'Horario']).reset_index(drop=False)
df_f = df_ev[df_ev['Departamento'].isin(meus_deps)].copy()
df_f = df_f[(df_f['Niv_N'] <= mapa_niveis_num.get(user['Nivel'], 0)) & (df_f['Data_Dt'].dt.date >= f_data)]

if f_depto_pill != "Todos": df_f = df_f[df_f['Departamento'] == f_depto_pill]
if f_nivel != "Todos": df_f = df_f[df_f['Nível'].astype(str).str.strip() == f_nivel]

nome_u_comp = user['Nome'].lower().strip()
if filtro_status == "Minhas Inscrições":
    df_f = df_f[(df_f['Voluntário 1'].astype(str).str.lower().str.strip() == nome_u_comp) | (df_f['Voluntário 2'].astype(str).str.lower().str.strip() == nome_u_comp)]
elif filtro_status == "Vagas Abertas":
    df_f = df_f[(df_f['Voluntário 1'].astype(str).str.strip() == "") | (df_f['Voluntário 2'].astype(str).str.strip() == "")]
elif filtro_status == "Vagas Vazias":
    df_f = df_f[(df_f['Voluntário 1'].astype(str).str.strip() == "") & (df_f['Voluntário 2'].astype(str).str.strip() == "")]

for i, row in df_f.iterrows():
    v1, v2 = str(row['Voluntário 1']).strip(), str(row['Voluntário 2']).strip()
    dia_abr = dias_semana.get(row['Data_Dt'].strftime('%A'), "")[:3]
    bg = cores_niveis.get(str(row['Nível']).strip(), "#FFFFFF")
    tx = "#FFFFFF" if "AV2" in str(row['Nível']) else "#000000"
    st_vaga = "🟢 Cheio" if v1 and v2 else ("🟡 1 Vaga" if v1 or v2 else "🔴 2 Vagas")
    st.markdown(f'<div class="card-container" style="background-color: {bg}; color: {tx};"><div style="display: flex; justify-content: space-between; font-weight: 800;"><span>{st_vaga}</span><span>{dia_abr} - {row["Data_Dt"].strftime("%d/%m")}</span></div><h2 style="margin: 5px 0; font-size: 1.4em; color: {tx};">{row["Nível"]} - {row["Nome do Evento"]}</h2><div style="font-weight: 800; margin-bottom: 10px;">🏢 {row["Departamento"]} | ⏰ {row["Horario"]}</div><div style="background: rgba(0,0,0,0.07); padding: 10px; border-radius: 8px;"><b>Vol. 1:</b> {v1 if v1 else "---"}<br><b>Vol. 2:</b> {v2 if v2 else "---"}</div></div>', unsafe_allow_html=True)
    if (v1.lower() == nome_u_comp or v2.lower() == nome_u_comp): st.button("✅ INSCRITO", key=f"bi_{i}", disabled=True, use_container_width=True)
    elif v1 and v2: st.button("🚫 CHEIO", key=f"bf_{i}", disabled=True, use_container_width=True)
    else:
        if st.button("Quero me inscrever", key=f"bq_{i}", type="primary", use_container_width=True):
            conflito = df_ev[
                (df_ev['Data Específica'] == row['Data Específica']) & 
                (df_ev['Horario'] == row['Horario']) & 
                ((df_ev['Voluntário 1'].astype(str).str.lower().str.strip() == nome_u_comp) | 
                 (df_ev['Voluntário 2'].astype(str).str.lower().str.strip() == nome_u_comp))
            ]
            if not conflito.empty:
                conflito_dialog(conflito.iloc[0])
            else:
                confirmar_dialog(int(row['index'])+2, row, 8 if v1 == "" else 9)

st.divider()
if st.button("🔄 Sincronizar"): st.cache_data.clear(); st.rerun()
if st.button("Sair"): st.session_state.user = None; st.rerun()
