import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("📊 Gestão de Vencidos V10.2")

arquivo = st.file_uploader("Suba sua planilha", type=["csv", "xlsx"])

if arquivo:

    if arquivo.name.endswith(".csv"):
        df = pd.read_csv(arquivo, encoding="latin1", sep=None, engine="python")
    else:
        df = pd.read_excel(arquivo)

    df = df.dropna(how='all')

    def tratar_moeda(valor):
        try:
            valor = str(valor)
            valor = valor.replace("R$", "").replace(" ", "")
            valor = valor.replace(".", "").replace(",", ".")
            return float(valor)
        except:
            return 0.0

    df["Montante"] = df["Montante"].apply(tratar_moeda)

    agrupado = df.groupby("Cliente").agg({
        "Montante": "sum",
        "Cliente": "count"
    }).rename(columns={"Cliente": "Qtd_Titulos"}).reset_index()

    if "status_manual" not in st.session_state:
        st.session_state.status_manual = {}

    def atualizar_status(cliente, status):
        st.session_state.status_manual[cliente] = status

    if st.button("✅ Marcar TODOS como 'Cobrado hoje'"):
        for cliente in agrupado["Cliente"]:
            st.session_state.status_manual[cliente] = "Cobrado hoje"

    filtro_status = st.selectbox(
        "Filtrar clientes",
        ["Todos", "Não cobrado", "Cobrado hoje", "Aguardando retorno", "Resolvido"]
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📋 Checklist de Cobrança")

        for _, row in agrupado.iterrows():
            cliente = row["Cliente"]
            total = row["Montante"]
            qtd = row["Qtd_Titulos"]

            status = st.session_state.status_manual.get(cliente, "Não cobrado")

            if filtro_status != "Todos" and status != filtro_status:
                continue

            c1, c2, c3, c4 = st.columns([3, 1, 1, 2])

            c1.write(f"**{cliente}**")
            c2.write(f"{qtd} títulos")
            c3.write(f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            novo_status = c4.selectbox(
                "Status",
                ["Não cobrado", "Cobrado hoje", "Aguardando retorno", "Resolvido"],
                index=["Não cobrado", "Cobrado hoje", "Aguardando retorno", "Resolvido"].index(status),
                key=f"status_{cliente}"
            )

            if novo_status != status:
                atualizar_status(cliente, novo_status)

    with col2:
        st.subheader("💬 Gerador de Mensagem")

        cliente_sel = st.selectbox("Selecione o cliente", agrupado["Cliente"])

        if cliente_sel:
            dados_cliente = df[df["Cliente"] == cliente_sel]

            mensagem = "Olá, tudo bem?\n\n"
            mensagem += "Identificamos que você possui os seguintes títulos em aberto:\n\n"

            for _, linha in dados_cliente.iterrows():
                valor = linha["Montante"]
                valor_formatado = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                mensagem += f"- Valor: {valor_formatado}\n"

            mensagem += "\nPoderia verificar para nós, por favor?\nObrigado!"

            st.text_area("Mensagem pronta:", mensagem, height=250)
            st.code(mensagem, language="text")

    st.subheader("📊 Resumo")

    total_geral = agrupado["Montante"].sum()
    total_clientes = len(agrupado)

    c1, c2 = st.columns(2)
    c1.metric("Clientes", total_clientes)
    c2.metric("Total", f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    st.dataframe(agrupado)

else:
    st.info("Envie uma planilha para começar.")
