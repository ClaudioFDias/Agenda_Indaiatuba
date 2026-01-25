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

# --- 2. CONFIGURAÇÕES ---
mapa_niveis = {
    "Nenhum": 0, "BAS": 1, "AV1": 2, "IN": 3, "AV2": 4, "AV2-24": 4, 
    "AV2-23": 5, "Av.2/": 6, "AV3": 7, "AV3A": 8, "AV3/": 9, "AV4": 10, "AV4A": 11
}
dias_semana = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}

def info_status(row):
    v1 = str(row.get('Voluntário 1', '')).strip()
    v2 = str(row.get('Voluntário 2', '')).strip()
    if v1 == "" and v2 == "": return "🔴 2 Vagas", "#FFEBEE"
    if v1 == "" or v2 == "": return "🟡 1 Vaga", "#FFF9C4"
    return "🟢 Completo", "#F0F2F6"

# --- 3. DIALOG DE CONFIRMAÇÃO ---
@st.dialog("Confirmar Inscrição")
def confirmar_dialog(sheet, linha, row, vaga_n, col_idx, col_ev, col_hr):
    st.markdown(f"### {row[col_ev]}")
    st.write(f"**Data:** {row['Data_Dt'].strftime('%d/%m')} ({row['Dia_da_Semana']})")
    st.write(f"**Horário:** {row[col_hr]}")
    st.write(f"**Vaga:** {vaga_n}")
    
    if st.button("Confirmar Agora", type="primary", width="stretch"):
        with st.spinner("Salvando..."):
            sheet.update_cell(linha, col_idx, st.session_state.nome_usuario)
            st.cache_resource.clear()
            st.rerun()

# --- 4. LOGIN ---
st.set_page_config(page_title="ProVida", layout="centered") # Centered fica melhor para cards

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

# --- 5. PROCESSAMENTO DE DADOS ---
try:
    sheet, df = load_data()
    
    col_ev = next((c for c in df.columns if 'Evento' in c), 'Evento')
    col_hr = next((c for c in df.columns if c.lower() in ['horário', 'horario', 'hora']), 'Horario')
    if col_hr not in df.columns: df[col_hr] = "---"

    df['Data_Dt'] = pd.to_datetime(df['Data Específica'], errors='coerce', dayfirst=True)
    df['Dia_da_Semana'] = df['Data_Dt'].dt.weekday.map(dias_semana)
    df['Niv_N'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    
    # Ordenar por Data e Horário
    df = df.sort_values(by=['Data_Dt', col_hr]).reset_index(drop=False)

    st.title(f"🤝 Olá, {st.session_state.nome_usuario.split()[0]}")

    with st.sidebar:
        f_dat = st.date_input("Ver a partir de:", datetime.now().date())
        so_vagas = st.checkbox("Apenas eventos com vagas", value=False)
        if st.button("Sair"): 
            st.session_state.autenticado = False
            st.rerun()

    # Filtro de Nível e Data
    df_f = df[(df['Niv_N'] <= st.session_state.nivel_num) & (df['Data_Dt'].dt.date >= f_dat)].copy()
    
    if so_vagas:
        df_f = df_f[df_f.apply(lambda x: "Completo" not in info_status(x)[0], axis=1)]

    # --- 6. EXIBIÇÃO EM CARDS ---
    st.subheader("📋 Próximas Atividades")
    
    if df_f.empty:
        st.info("Nenhuma atividade encontrada para os filtros selecionados.")
    else:
        for i, row in df_f.iterrows():
            status_txt, status_cor = info_status(row)
            
            # Início do Card
            with st.container(border=True):
                # Cabeçalho do Card (Status e Data)
                col_a, col_b = st.columns([1, 1])
                col_a.markdown(f"**{status_txt}**")
                col_b.markdown(f"📅 **{row['Data_Dt'].strftime('%d/%m')} - {row['Dia_da_Semana']}**")
                
                # Título do Evento (Quebra linha sozinho)
                st.markdown(f"### {row[col_ev]}")
                
                # Detalhes: Horário e Nível
                st.markdown(f"⏰ **Horário:** {row[col_hr]} | 🎓 **Nível:** {row['Nível']}")
                
                # Voluntários atuais
                v1 = row['Voluntário 1'] if row['Voluntário 1'] else "*(Vaga aberta)*"
                v2 = row['Voluntário 2'] if row['Voluntário 2'] else "*(Vaga aberta)*"
                
                st.markdown(f"👤 **V1:** {v1}")
                st.markdown(f"👤 **V2:** {v2}")
                
                # Botão de Ação
                if "Completo" not in status_txt:
                    if st.button(f"Inscrever-se", key=f"btn_{i}", type="primary", width="stretch"):
                        linha_planilha = int(row['index']) + 2
                        vaga_nome = "Voluntário 1" if not row['Voluntário 1'] else "Voluntário 2"
                        coluna_idx = 7 if not row['Voluntário 1'] else 8
                        confirmar_dialog(sheet, linha_planilha, row, vaga_nome, coluna_idx, col_ev, col_hr)
                else:
                    st.button("✅ Escala Preenchida", key=f"btn_{i}", disabled=True, width="stretch")

except Exception as e:
    st.error(f"Ocorreu um erro: {e}")
