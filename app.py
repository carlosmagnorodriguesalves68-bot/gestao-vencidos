
import streamlit as st

st.set_page_config(page_title="Cobrança Inteligente", layout="wide")

# HEADER
st.markdown("<h1 style='margin-bottom:0'>🧾 Cobrança Inteligente</h1>", unsafe_allow_html=True)
st.markdown("<p style='margin-top:0;color:gray;font-size:13px'>Veja. Decida. Cobre.</p>", unsafe_allow_html=True)

# STATE
if "filtros" not in st.session_state:
    st.session_state["filtros"] = []

# BOTÕES
faixas = [
    ("Recuperação", "+30d"),
    ("Protesto", "12-30d"),
    ("Radar", "9-11d"),
    ("Bloqueio", "5-8d"),
    ("Risco", "3-4d"),
    ("Baixa", "0-2d"),
]

cols = st.columns(len(faixas))

for i, (nome, faixa) in enumerate(faixas):
    ativo = nome in st.session_state["filtros"]

    label = f"{nome}\n{faixa}"

    if cols[i].button(label, use_container_width=True, key=nome):
        if ativo:
            st.session_state["filtros"].remove(nome)
        else:
            st.session_state["filtros"].append(nome)
        st.rerun()

# BOTÃO LIMPAR
col1, col2 = st.columns([1,5])
if col1.button("Limpar filtros"):
    st.session_state["filtros"] = []
    st.rerun()

st.write("Filtros ativos:", st.session_state["filtros"] if st.session_state["filtros"] else "Nenhum (mostrando todos)")
