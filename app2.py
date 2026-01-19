import streamlit as st
import re
import textwrap
import base64

st.set_page_config(page_title="Validador de Chave ProVida", layout="centered")

st.title("🛠️ Validador de Integridade de Chave")

def validar_chave():
    partes_nome = ["P1", "P2", "P3", "P4", "P5", "P6"]
    diagnostico = []
    chave_full = ""
    
    st.subheader("1. Verificação dos Segredos (Secrets)")
    
    for nome in partes_nome:
        if nome in st.secrets:
            val = st.secrets[nome].strip()
            # Remove qualquer lixo que não seja Base64
            limpo = re.sub(r'[^A-Za-z0-9+/=]', '', val)
            chave_full += limpo
            diagnostico.append({"Parte": nome, "Status": "✅ OK", "Tamanho": len(limpo)})
        else:
            diagnostico.append({"Parte": nome, "Status": "❌ AUSENTE", "Tamanho": 0})
    
    st.table(diagnostico)
    
    st.subheader("2. Resultado da Reconstrução")
    total_len = len(chave_full)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Caracteres", total_len)
    with col2:
        # O Base64 DEVE ser múltiplo de 4
        resto = total_len % 4
        if resto == 0:
            st.success("✅ Tamanho Válido (Múltiplo de 4)")
        else:
            st.error(f"❌ Tamanho Inválido! Sobram {resto} caracteres.")
            st.info("Dica: Verifique se faltou copiar o final da P6 (o sinal de '=' conta).")

    st.subheader("3. Teste de Decodificação (Base64)")
    try:
        # Tenta decodificar a string para ver se o formato é binário válido
        base64.b64decode(chave_full)
        st.success("✅ A string é um Base64 válido e pode ser convertida em chave!")
        
        # Mostra os 10 primeiros e 10 últimos para conferência manual
        st.code(f"Início: {chave_full[:20]}... \nFinal: ...{chave_full[-20:]}")
        
    except Exception as e:
        st.error(f"❌ Falha na decodificação Base64: {e}")
        st.warning("Isso significa que há caracteres corrompidos ou a ordem das partes (P1-P6) está trocada.")

    st.subheader("4. Formatação Final (Visualização)")
    key_lines = textwrap.wrap(chave_full, 64)
    final_pem = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"
    st.text_area("Chave que será enviada ao Google:", final_pem, height=200)

if st.button("Executar Teste de Integridade"):
    validar_chave()
else:
    st.info("Clique no botão acima para validar as partes P1 a P6 que você configurou.")
