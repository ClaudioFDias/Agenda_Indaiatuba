import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
from datetime import date

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Quem está na Escala?", layout="wide")

st.title("🏃‍♂️ Responsáveis por Departamento")

# --- CONEXÃO COM GOOGLE SHEETS ---
@st.cache_data(ttl=600)  # Atualiza os dados a cada 10 minutos
def carregar_dados():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    
    df = pd.DataFrame(ss.worksheet("Calendario_Eventos").get_all_records())
    df['Data_Formatada'] = pd.to_datetime(df['Data Específica'], format='%d/%m/%Y').dt.date
    return df

try:
    df_total = carregar_dados()

    # --- FILTRO DE DATA ---
    col_data, col_info = st.columns([1, 2])
    with col_data:
        data_selecionada = st.date_input("🗓️ Escolha uma data:", value=date.today())
    
    with col_info:
        st.info(f"Mostrando escala para: **{data_selecionada.strftime('%d/%m/%Y')}**")

    # Filtrar dados pela data
    df_dia = df_total[df_total['Data_Formatada'] == data_selecionada]

    if df_dia.empty:
        st.warning("Nenhuma atividade ou voluntário escalado para esta data.")
    else:
        # --- EXIBIÇÃO POR DEPARTAMENTO ---
        # Pegamos todos os departamentos únicos para criar a grade
        departamentos = sorted(df_dia['Departamento'].unique())
        
        # Criamos colunas para o layout (3 colunas por linha)
        cols = st.columns(3)
        
        for i, depto in enumerate(departamentos):
            with cols[i % 3]:
                st.subheader(f"🏢 {depto}")
                eventos_depto = df_dia[df_dia['Departamento'] == depto]
                
                for _, row in eventos_depto.iterrows():
                    v1 = str(row['Voluntário 1']).strip()
                    v2 = str(row['Voluntário 2']).strip()
                    horario = row['Horario']
                    evento = row['Nome do Evento']
                    nivel = row['Nível']
                    
                    # Estilização do Card
                    with st.container():
                        st.markdown(f"""
                        <div style="border: 1px solid #ddd; padding: 10px; border-radius: 10px; margin-bottom: 10px; background-color: #f9f9f9;">
                            <small style="color: #666;">{horario} - {nivel}</small><br>
                            <b style="color: #1565c0;">{evento}</b><br>
                            👤 {v1 if v1 not in ['', '---', 'nan'] else '<i>Vaga Aberta</i>'}<br>
                            👤 {v2 if v2 not in ['', '---', 'nan'] else '<i>Vaga Aberta</i>'}
                        </div>
                        """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
