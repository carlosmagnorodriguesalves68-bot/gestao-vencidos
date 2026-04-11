
import streamlit as st

st.set_page_config(page_title="Cobrança Inteligente", layout="wide")

st.markdown("""
<h1 style='margin-bottom:0;'>🧾 Cobrança Inteligente</h1>
<p style='margin-top:0;color:gray;'>Veja. Decida. Cobre.</p>
""", unsafe_allow_html=True)

if "filtros" not in st.session_state:
    st.session_state["filtros"] = set()

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
    if cols[i].button(f"{nome}
{faixa}", use_container_width=True):
        if ativo:
            st.session_state["filtros"].remove(nome)
        else:
            st.session_state["filtros"].add(nome)
        st.rerun()

st.write("Filtros ativos:", st.session_state["filtros"])
