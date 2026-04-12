
import streamlit as st

st.set_page_config(page_title="Cobrança Inteligente", layout="wide")

st.title("Cobrança Inteligente")
st.caption("Veja. Decida. Cobre.")

cliente = "Cliente Exemplo"

mensagem = f"""Olá, tudo bem? {cliente},

Identificamos títulos em aberto em seu cadastro:

- Título 123 | Vencimento 10/01/2024 | Valor R$ 150,00

Valor total: R$ 150,00.

Esses títulos estão próximos de medidas administrativas, sendo importante a regularização com urgência.

Aguardamos sua posição."""

col1, col2 = st.columns([6.5,3.5])

with col1:
    st.subheader("Checklist de cobrança")
    st.dataframe({"Cliente":[cliente],"Status":["Não cobrado"]})

with col2:
    st.subheader("Assistente de Cobrança")
    st.code(mensagem)

st.download_button("Baixar", "teste")
