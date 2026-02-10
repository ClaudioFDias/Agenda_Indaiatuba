import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, date
import textwrap
import re
import time

# ===============================
# 1. CONEXÃO GOOGLE SHEETS
# ===============================
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

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)

    except Exception:
        st.error("Erro crítico de conexão com o Google Sheets.")
        st.stop()


@st.cache_data(ttl=300)
def load_data_cached():
    client = get_gspread_client()
    for tentativa in range(3):
        try:
            ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")

            sheet_ev = ss.worksheet("Calendario_Eventos")
            df_ev = pd.DataFrame(sheet_ev.get_all_records())
            df_ev.columns = [c.strip() for c in df_ev.columns]

            sheet_us = ss.worksheet("Usuarios")
            df_us = pd.DataFrame(sheet_us.get_all_records())
            df_us.columns = [c.strip() for c in df_us.columns]

            return df_ev, df_us

        except Exception:
            if tentativa < 2:
                time.sleep(2)
            else:
                st.error("Erro ao carregar dados.")
                st.stop()


def get_sheets():
    client = get_gspread_client()
    ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    return ss.worksheet("Calendario_Eventos"), ss.worksheet("Usuarios")


# ===============================
# 2. CONFIGURAÇÕES
# ===============================
cores_niveis = {
    "Nenhum": "#FFFFFF",
    "BAS": "#C8E6C9",
    "AV1": "#FFCDD2",
    "IN": "#BBDEFB",
    "AV2": "#795548",
    "AV2-24": "#795548",
    "AV2-23": "#795548",
    "AV2/": "#795548",
    "AV3": "#E1BEE7",
    "AV3A": "#E1BEE7",
    "AV3/": "#E1BEE7",
    "AV4": "#FFF9C4",
    "AV4A": "#FFF9C4"
}

mapa_niveis_num = {k: i for i, k in enumerate(cores_niveis.keys())}

dias_semana = {
    "Monday": "Segunda",
    "Tuesday": "Terça",
    "Wednesday": "Quarta",
    "Thursday": "Quinta",
    "Friday": "Sexta",
    "Saturday": "Sábado",
    "Sunday": "Domingo"
}


# ===============================
# 3. DIALOGS
# ===============================
@st.dialog("Conflito de Agenda")
def conflito_dialog(evento, horario):
    st.warning("⚠️ Você já possui uma atividade neste horário.")
    st.write(f"**Evento:** {evento}")
    st.write(f"**Horário:** {horario}")
    if st.button("Entendido", type="primary", use_container_width=True):
        st.rerun()


@st.dialog("Confirmar Inscrição")
def confirmar_dialog(linha, col_idx):
    if st.button("Confirmar Inscrição", type="primary", use_container_width=True):
        sheet_ev, _ = get_sheets()
        sheet_ev.update_cell(linha, col_idx, st.session_state.user["Nome"])
        st.cache_data.clear()
        st.rerun()


# ===============================
# 4. ESTILO
# ===============================
st.set_page_config(page_title="ProVida Escala", layout="centered")

st.markdown("""
<style>
.public-card { padding: 15px; border-radius: 12px; border: 1px solid #ccc; margin-bottom: 20px; }
.public-title { font-size: 1.15em; font-weight: 800; margin-bottom: 10px; }
.card-container { padding: 15px; border-radius: 12px; border: 1px solid #ddd; margin-top: 15px; }
</style>
""", unsafe_allow_html=True)


# ===============================
# 5. ESTADOS
# ===============================
if "user" not in st.session_state:
    st.session_state.user = None

if "ver_painel" not in st.session_state:
    st.session_state.ver_painel = False


df_ev, df_us = load_data_cached()
df_ev["Data_Dt"] = pd.to_datetime(df_ev["Data Específica"], dayfirst=True, errors="coerce")
deps_na_planilha = sorted(df_ev["Departamento"].dropna().unique())


# ===============================
# 6. PAINEL PÚBLICO
# ===============================
if st.session_state.ver_painel:
    st.title("🏃 Responsáveis do Dia")

    if st.button("⬅️ Voltar"):
        st.session_state.ver_painel = False
        st.rerun()

    data_sel = st.date_input("Data:", value=date.today())
    df_dia = df_ev[df_ev["Data_Dt"].dt.date == data_sel]

    if df_dia.empty:
        st.warning("Nenhuma atividade encontrada.")
    else:
        for _, row in df_dia.iterrows():
            st.markdown(
                f"""
                <div class="public-card">
                    <b>{row['Nome do Evento']} | {row['Departamento']}</b><br>
                    ⏰ {row['Horario']}<br>
                    👤 {row['Voluntário 1'] or '---'} / {row['Voluntário 2'] or '---'}
                </div>
                """,
                unsafe_allow_html=True
            )

    st.stop()


# ===============================
# 7. LOGIN (SEGURO)
# ===============================
if st.session_state.user is None:
    st.title("🤝 Escala de Voluntários")

    if st.button("🔍 Ver Responsáveis do Dia (Público)", use_container_width=True):
        st.session_state.ver_painel = True
        st.rerun()

    st.divider()

    with st.form("login"):
        email = st.text_input("E-mail:").strip().lower()
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if entrar:
        user_row = df_us[df_us["Email"].astype(str).str.lower() == email]

        if user_row.empty:
            st.error("🚫 Usuário não encontrado. Falar com o responsável do seu Departamento.")
            st.stop()
        else:
            st.session_state.user = user_row.iloc[0].to_dict()
            st.success("Login realizado com sucesso!")
            st.rerun()

    st.stop()


# ===============================
# 8. DASHBOARD LOGADO
# ===============================
user = st.session_state.user
nome_user = user["Nome"].lower().strip()
meus_deps = [d.strip() for d in user["Departamentos"].split(",") if d.strip()]

st.title(f"👋 Olá, {user['Nome'].split()[0]}!")

df_ev["Niv_N"] = df_ev["Nível"].map(mapa_niveis_num).fillna(99)

df_f = df_ev[
    (df_ev["Departamento"].isin(meus_deps)) &
    (df_ev["Niv_N"] <= mapa_niveis_num.get(user["Nivel"], 99)) &
    (df_ev["Data_Dt"].dt.date >= date.today())
]

for i, row in df_f.iterrows():
    v1 = str(row["Voluntário 1"]).strip()
    v2 = str(row["Voluntário 2"]).strip()

    st.markdown(
        f"""
        <div class="card-container">
            <b>{row['Nome do Evento']} | {row['Departamento']}</b><br>
            📅 {row['Data_Dt'].strftime('%d/%m')} ⏰ {row['Horario']}<br>
            👤 {v1 or '---'} / {v2 or '---'}
        </div>
        """,
        unsafe_allow_html=True
    )

    if nome_user in [v1.lower(), v2.lower()]:
        st.button("✅ INSCRITO", disabled=True, use_container_width=True)
    elif v1 and v2:
        st.button("🚫 CHEIO", disabled=True, use_container_width=True)
    else:
        if st.button("Quero me inscrever", key=i, type="primary", use_container_width=True):
            conflito = df_ev[
                (df_ev["Data Específica"] == row["Data Específica"]) &
                (df_ev["Horario"] == row["Horario"]) &
                (
                    df_ev["Voluntário 1"].astype(str).str.lower().str.strip() == nome_user |
                    df_ev["Voluntário 2"].astype(str).str.lower().str.strip() == nome_user
                )
            ]

            if not conflito.empty:
                conflito_dialog(conflito.iloc[0]["Nome do Evento"], conflito.iloc[0]["Horario"])
            else:
                confirmar_dialog(int(row["index"]) + 2, 8 if v1 == "" else 9)

st.divider()

if st.button("🔄 Sincronizar"):
    st.cache_data.clear()
    st.rerun()

if st.button("🚪 Sair"):
    st.session_state.user = None
    st.rerun()
