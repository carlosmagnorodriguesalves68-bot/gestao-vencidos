
from datetime import date
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Gestão de Vencidos", layout="wide")

# ================= CONFIG =================
STATUS_BLOQUEIO_GRUPO = ["BLOQUEADO", "RADAR PERDA", "PROTESTO IMINENTE"]

# ================= FUNÇÕES =================
def moeda_br(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def gerar_mensagem_cliente(df_cliente):
    total = df_cliente["Montante"].sum()

    linhas = []
    for _, row in df_cliente.sort_values("Venc Liq").iterrows():
        linhas.append(
            f"- Título {row['N doc']} | Vencimento {row['Venc Liq'].strftime('%d/%m/%Y')} | Valor {moeda_br(row['Montante'])}"
        )

    mensagem = f"""Olá, tudo bem?

Identificamos que você possui os seguintes títulos em aberto:

{chr(10).join(linhas)}

Valor total em aberto: {moeda_br(total)}.

Poderia nos informar uma previsão de regularização?

Fico à disposição."""

    return mensagem

# ================= APP =================
st.title("Gestão de Vencidos")

arquivo = st.file_uploader("Subir planilha")

if arquivo:
    df = pd.read_excel(arquivo)

    df["Venc Liq"] = pd.to_datetime(df["Venc Liq"], dayfirst=True)
    df["Montante"] = pd.to_numeric(df["Montante"], errors="coerce")

    data_ref = st.date_input("Data de referência", value=date.today())

    df["Dias"] = (pd.to_datetime(data_ref) - df["Venc Liq"]).dt.days

    def status(d):
        if d >= 61:
            return "INADIMPLÊNCIA"
        elif d >= 12:
            return "PROTESTO IMINENTE"
        elif d >= 8:
            return "RADAR PERDA"
        elif d >= 5:
            return "BLOQUEADO"
        elif d >= 3:
            return "RISCO DE BLOQUEIO"
        else:
            return "AGUARDANDO BAIXA"

    df["Status"] = df["Dias"].apply(status)

    # ================= CARDS =================
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total títulos", len(df))
    col2.metric("Valor vencido", moeda_br(df["Montante"].sum()))

    clientes_criticos = df[df["Status"].isin(["INADIMPLÊNCIA","PROTESTO IMINENTE"])]["Cliente"].nunique()
    col3.metric("Clientes críticos", clientes_criticos)

    clientes_bloqueados = df[df["Status"].isin(STATUS_BLOQUEIO_GRUPO)]["Cliente"].nunique()
    col4.metric("Clientes bloqueados", clientes_bloqueados)

    # ================= LAYOUT =================
    left, right = st.columns([1.4, 0.8])

    with left:
        st.subheader("Checklist de cobrança")

        if "check" not in st.session_state:
            st.session_state["check"] = {}

        for i, row in df.iterrows():
            key = f"{row['Cliente']}_{row['N doc']}"
            if key not in st.session_state["check"]:
                st.session_state["check"][key] = False

            st.session_state["check"][key] = st.checkbox(
                f"{row['Cliente']} | {moeda_br(row['Montante'])}",
                value=st.session_state["check"][key]
            )

    with right:
        st.subheader("Gerador de mensagem")

        clientes = df["Cliente"].unique()

        cliente_sel = st.selectbox("Selecione o cliente", clientes)

        df_cliente = df[df["Cliente"] == cliente_sel]

        mensagem = gerar_mensagem_cliente(df_cliente)

        st.code(mensagem)

    st.subheader("Tabela")
    st.dataframe(df)

