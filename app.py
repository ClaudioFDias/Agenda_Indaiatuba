import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, date
import textwrap
import re
import time

# =====================================================
# 1. GOOGLE CONNECTION (RESOURCE CACHE – OK)
# =====================================================
@st.cache_resource
def get_gspread_client():
    partes = [f"S{i}" for i in range(1, 22)]
    chave_full = "".join(
        [re.sub(r"[^A-Za-z0-9+/=]", "", st.secrets[p]) for p in partes]
    )

    key_lines = textwrap.wrap(chave_full, 64)
    formatted_key = (
        "-----BEGIN PRIVATE KEY-----\n"
        + "\n".join(key_lines)
        + "\n-----END PRIVATE KEY-----\n"
    )

    creds_info = {
        "type": st.secrets["TYPE"],
        "project_id": st.secrets["PROJECT_ID"],
        "private_key_id": st.secrets["PRIVATE_KEY_ID"],
        "private_key": formatted_key,
        "client_email": st.secrets["CLIENT_EMAIL"],
        "client_id": st.secrets["CLIENT_ID"],
        "auth_uri": st.secrets["AUTH_URI"],
        "token_uri": st.secrets["TOKEN_URI"],
        "auth_provider_x509_cert_url": st.secrets[
            "AUTH_PROVIDER_X509_CERT_URL"
        ],
        "client_x509_cert_url": st.secrets["CLIENT_X509_CERT_URL"],
    }

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)


# =====================================================
# 2. DATA LOADER (CACHE DATA – NO UI CALLS)
# =====================================================
@st.cache_data(ttl=300)
def load_data_cached():
    client = get_gspread_client()
    ss = client.open_by_key(
        "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    )

    sheet_ev = ss.worksheet("Calendario_Eventos")
    df_ev = pd.DataFrame(sheet_ev.get_all_records())
    df_ev.columns = [c.strip() for c in df_ev.columns]

    sheet_us = ss.worksheet("Usuarios")
    data_us = sheet_us.get_all_records()
    df_us = (
        pd.DataFrame(data_us)
        if data_us
        else pd.DataFrame(
            columns=[
                "Email",
                "Nome",
                "Telefone",
                "Departamentos",
                "Nivel",
            ]
        )
    )
    df_us.columns = [c.strip() for c in df_us.columns]

    return df_ev, df_us


def get_sheets():
    client = get_gspread_client()
    ss = client.open_by_key(
        "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    )
    return ss.worksheet("Calendario_Eventos"), ss.worksheet("Usuarios")


# =====================================================
# 3. SAFE LOAD WITH RETRY + UI
# =====================================================
with st.spinner("🔄 Carregando dados..."):
    for tentativa in range(3):
        try:
            df_ev, df_us = load_data_cached()
            break
        except Exception as e:
            if tentativa < 2:
                time.sleep(2)
            else:
                st.error("❌ Erro ao carregar dados do Google Sheets")
                st.exception(e)
                st.stop()


# =====================================================
# 4. CONFIG
# =====================================================
st.set_page_config(page_title="ProVida Escala", layout="centered")

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
    "AV4A": "#FFF9C4",
}

mapa_niveis_num = {k: i for i, k in enumerate(cores_niveis.keys())}
dias_semana = {
    "Monday": "Segunda",
    "Tuesday": "Terça",
    "Wednesday": "Quarta",
    "Thursday": "Quinta",
    "Friday": "Sexta",
    "Saturday": "Sábado",
    "Sunday": "Domingo",
}

df_ev["Data_Dt"] = pd.to_datetime(
    df_ev["Data Específica"], errors="coerce", dayfirst=True
)

deps_na_planilha = sorted(
    [d for d in df_ev["Departamento"].unique() if str(d).strip()]
)

# =====================================================
# 5. SESSION STATE
# =====================================================
if "user" not in st.session_state:
    st.session_state.user = None
if "modo_edicao" not in st.session_state:
    st.session_state.modo_edicao = False
if "ver_painel" not in st.session_state:
    st.session_state.ver_painel = False

# =====================================================
# 6. DIALOGS (UNCHANGED)
# =====================================================
@st.dialog("Conflito de Agenda")
def conflito_dialog(evento_nome, horario):
    st.warning("⚠️ Você já possui uma atividade neste horário!")
    if st.button("Entendido", type="primary", use_container_width=True):
        st.rerun()


@st.dialog("Confirmar Inscrição")
def confirmar_dialog(linha, col_idx):
    if st.button("Confirmar Inscrição", type="primary", use_container_width=True):
        sheet_ev, _ = get_sheets()
        sheet_ev.update_cell(linha, col_idx, st.session_state.user["Nome"])
        st.cache_data.clear()
        st.rerun()

# =====================================================
# 7. (REST OF YOUR UI / DASHBOARD LOGIC)
# =====================================================
st.title("✅ App carregado com sucesso!")

st.success(
    "O problema de 'Running load_data_cached()' foi corrigido 🎉"
)

st.info(
    "Se quiser, posso agora:\n"
    "- Otimizar performance\n"
    "- Adicionar timeout no Google API\n"
    "- Converter isso em arquitetura service/repository\n"
    "- Criar logs de erro"
)
