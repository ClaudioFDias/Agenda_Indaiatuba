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
    sheet = ss.worksheet("Calendario_Eventos")
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 2. CONFIGURAÇÕES VISUAIS E MAPEAMENTO ---
# Cores de fundo por nível
cores_niveis = {
    "Nenhum": "#FFFFFF",
    "BAS": "#C8E6C9",      # Verde Claro
    "AV1": "#FFCDD2",      # Vermelho Claro
    "IN": "#BBDEFB",       # Azul Claro
    "AV2": "#B71C1C",      # Vermelho Escuro
    "AV2-24": "#B71C1C",   # Vermelho Escuro
    "AV2-23": "#B71C1C",   # Vermelho Escuro
    "Av.2/": "#B71C1C",    # Vermelho Escuro
    "AV3": "#E1BEE7",      # Roxo Claro (p/ leitura) ou #4A148C se quiser escuro
    "AV3A": "#E1BEE7",
    "AV3/": "#E1BEE7",
    "AV4": "#FFF9C4",      # Amarelo
    "AV4A": "#FFF9C4"
}

# Cores de texto (ajusta para branco se o fundo for muito escuro)
def cor_texto(nivel):
    if "AV2" in nivel: return "#FFFFFF" # Texto branco para fundos vermelhos escuros
    return "#000000"

mapa_niveis_num = {k: i for i, k in enumerate(cores_niveis.keys())}
dias_semana_extenso = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}

def info_status(row):
    v1 = str(row.get('Voluntário 1', '')).strip()
    v2 = str(row.get('Voluntário 2', '')).strip()
    if v1 == "" and v2 == "": return "🔴 2 Vagas"
    if v1 == "" or v2 == "": return "🟡 1 Vaga"
    return "🟢 Completo"

# --- 3. DIALOG ---
@st.dialog("Confirmar Inscrição")
def confirmar_dialog(sheet, linha, row, vaga_n, col_idx, col_ev, col_hr):
    st.markdown(f"### {row[col_ev]}")
    st.write(f"📅 **Data:** {row['Data_Dt'].strftime('%d/%m')} ({row['Dia_Extenso']})")
    st.write(f"👤 **Vaga:** {vaga_n}")
    if st.button("Confirmar", type="primary", width="stretch"):
        sheet.update_cell(linha, col_idx, st.session_state.nome_usuario)
        st.cache_resource.clear()
        st.rerun()

# --- 4. LOGIN ---
st.set_page_config(page_title="ProVida", layout="centered")

if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login")
    with st.form("login"):
        n = st.text_input("Nome Completo")
        niv = st.selectbox("Seu Nível", list(cores_niveis.keys()))
        if st.form_submit_button("Entrar"):
            if n: 
                st.session_state.update({"nome_usuario": n, "nivel_num": mapa_niveis_num[niv], "autenticado": True})
                st.rerun()
    st.stop()

# --- 5. PROCESSAMENTO ---
try:
    sheet, df = load_data()
    col_ev = next((c for c in df.columns if 'Evento' in c), 'Evento')
    col_hr = next((c for c in df.columns if c.lower() in ['horário', 'horario', 'hora']), 'Horario')
    
    df['Data_Dt'] = pd.to_datetime(df['Data Específica'], errors='coerce', dayfirst=True)
    df['Dia_Extenso'] = df['Data_Dt'].dt.weekday.map(dias_semana_extenso)
    df['Niv_N'] = df['Nível'].astype(str).str.strip().map(mapa_niveis_num).fillna(99)
    
    df = df.sort_values(by=['Data_Dt', col_hr]).reset_index(drop=False)

    st.title(f"🤝 Olá, {st.session_state.nome_usuario.split()[0]}")

    with st.sidebar:
        f_dat = st.date_input("Filtrar por data:", datetime.now().date())
        if st.button("Sair"): 
            st.session_state.autenticado = False
            st.rerun()

    df_f = df[(df['Niv_N'] <= st.session_state.nivel_num) & (df['Data_Dt'].dt.date >= f_dat)].copy()

    # --- 6. RENDERIZAÇÃO DOS CARDS ---
    for i, row in df_f.iterrows():
        status_txt = info_status(row)
        nivel_row = str(row['Nível']).strip()
        bg_cor = cores_niveis.get(nivel_row, "#FFFFFF")
        txt_cor = cor_texto(nivel_row)

        # HTML/CSS para o Card Customizado
        st.markdown(f"""
            <div style="
                background-color: {bg_cor}; 
                padding: 20px; 
                border-radius: 10px; 
                border: 1px solid #ddd; 
                margin-bottom: 10px;
                color: {txt_cor};
            ">
                <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 0.9em; opacity: 0.9;">
                    <span>{status_txt}</span>
                    <span>{row['Data_Dt'].strftime('%d/%m')} - {row['Dia_Extenso']}</span>
                </div>
                <h2 style="margin: 10px 0; color: {txt_cor}; border: none;">{row[col_ev]}</h2>
                <div style="font-size: 1.1em; margin-bottom: 10px;">
                    ⏰ <b>Horário:</b> {row[col_hr]} | 🎓 <b>Nível:</b> {nivel_row}
                </div>
                <div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 5px;">
                    👤 <b>V1:</b> {row['Voluntário 1'] if row['Voluntário 1'] else 'Vago'}<br>
                    👤 <b>V2:</b> {row['Voluntário 2'] if row['Voluntário 2'] else 'Vago'}
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Botão de Inscrição fora do HTML (Streamlit não permite botões dentro de f-strings HTML)
        if "Completo" not in status_txt:
            if st.button(f"Inscrever-se no evento acima", key=f"btn_{i}", type="primary", width="stretch"):
                linha_planilha = int(row['index']) + 2
                vaga_nome = "Voluntário 1" if not row['Voluntário 1'] else "Voluntário 2"
                coluna_idx = 7 if not row['Voluntário 1'] else 8
                confirmar_dialog(sheet, linha_planilha, row, vaga_nome, coluna_idx, col_ev, col_hr)
        else:
            st.button("✅ Escala Completa", key=f"btn_{i}", disabled=True, width="stretch")
        
        st.write("") # Espaçador entre cards

except Exception as e:
    st.error(f"Erro: {e}")
