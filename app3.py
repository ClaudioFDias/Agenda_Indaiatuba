import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import textwrap
import re

# --- 1. CONEXÃO (Igual ao anterior) ---
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
    sheet = ss.worksheet("Calendario_Eventos")
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 2. CONFIGS ---
mapa_niveis = {
    "Nenhum": 0, "BAS": 1, "AV1": 2, "IN": 3, "AV2": 4, "AV2-24": 4, 
    "AV2-23": 5, "Av.2/": 6, "AV3": 7, "AV3A": 8, "AV3/": 9, "AV4": 10, "AV4A": 11
}
dias_semana = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}

def definir_status(row):
    v1, v2 = str(row.get('Voluntário 1', '')).strip(), str(row.get('Voluntário 2', '')).strip()
    if v1 == "" and v2 == "": return "🔴 2 Vagas", "#FFEBEE"
    if v1 == "" or v2 == "": return "🟡 1 Vaga", "#FFF9C4"
    return "🟢 Completo", "#FFFFFF"

# --- 3. DIALOG ---
@st.dialog("Confirmar Inscrição")
def confirmar_dialog(sheet, linha, row, vaga_n, col_idx, col_ev):
    st.markdown(f"### {row[col_ev]}")
    st.write(f"⏰ {row['Data_Dt'].strftime('%d/%m')} - {row['Horário']}")
    if st.button("Confirmar", type="primary", use_container_width=True):
        sheet.update_cell(linha, col_idx, st.session_state.nome_usuario)
        st.cache_resource.clear()
        st.rerun()

# --- 4. LOGIN ---
st.set_page_config(page_title="ProVida", layout="wide")

if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login")
    with st.form("login"):
        n = st.text_input("Nome Completo")
        niv = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Entrar"):
            if n: 
                st.session_state.update({"nome_usuario": n, "nivel_num": mapa_niveis[niv], "autenticado": True})
                st.rerun()
    st.stop()

# --- 5. DATA ---
try:
    sheet, df = load_data()
    col_ev = next((c for c in df.columns if 'Evento' in c), 'Evento')
    col_hr = 'Horário' if 'Horário' in df.columns else 'Horário'
    
    df['Data_Dt'] = pd.to_datetime(df['Data Específica'], errors='coerce')
    df['Dia_da_Semana'] = df['Data_Dt'].dt.weekday.map(dias_semana)
    df['Niv_N'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    
    df = df.sort_values(by=['Data_Dt', col_hr]).reset_index(drop=False)

    st.title(f"🤝 Olá, {st.session_state.nome_usuario.split()[0]}")

    # Filtros
    with st.sidebar:
        f_dat = st.date_input("A partir de", datetime.now().date())
        if st.button("Sair"): st.session_state.autenticado = False; st.rerun()

    df_f = df[(df['Niv_N'] <= st.session_state.nivel_num) & (df['Data_Dt'].dt.date >= f_dat)].copy()

    # --- 6. EXIBIÇÃO EM CARDS (MOBILE FRIENDLY) ---
    st.subheader("📋 Escala de Atividades")
    st.caption("Abaixo estão as atividades disponíveis para seu nível.")

    for i, row in df_f.iterrows():
        status_texto, cor_fundo = definir_status(row)
        
        # Criando um container com borda para cada atividade
        with st.container(border=True):
            # Layout de colunas para Status e Data
            c1, c2 = st.columns([1, 2])
            c1.markdown(f"**{status_texto}**")
            c2.markdown(f"📅 {row['Data_Dt'].strftime('%d/%m')} ({row['Dia_da_Semana']}) - {row[col_hr]}")
            
            # Título do Evento (Aqui ele quebra a linha automaticamente se for grande!)
            st.markdown(f"### {row[col_ev]}")
            st.markdown(f"🎓 **Nível:** {row['Nível']}")
            
            # Voluntários
            v1 = row['Voluntário 1'] if row['Voluntário 1'] else "---"
            v2 = row['Voluntário 2'] if row['Voluntário 2'] else "---"
            st.markdown(f"👤 **V1:** {v1} | 👤 **V2:** {v2}")
            
            # Botão de Inscrição (Só aparece se houver vaga)
            if "Completo" not in status_texto:
                if st.button(f"Inscrever-se no Evento {i}", key=f"btn_{i}", use_container_width=True):
                    linha_p = int(row['index']) + 2
                    vaga_n = "Voluntário 1" if not row['Voluntário 1'] else "Voluntário 2"
                    col_alvo = 7 if not row['Voluntário 1'] else 8
                    confirmar_dialog(sheet, linha_p, row, vaga_n, col_alvo, col_ev)
            else:
                st.button("✅ Escala Completa", key=f"btn_{i}", disabled=True, use_container_width=True)

except Exception as e:
    st.error(f"Erro: {e}")
