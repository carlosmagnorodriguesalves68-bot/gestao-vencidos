
import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("📊 Gestão de Vencidos V10.6")

arquivo = st.file_uploader("Suba sua planilha", type=["csv", "xlsx"])

def tratar_moeda(valor):
    try:
        valor = str(valor)
        valor = valor.replace("R$", "").replace(" ", "")
        valor = valor.replace(".", "").replace(",", ".")
        return float(valor)
    except:
        return 0.0

if arquivo:
    if arquivo.name.endswith(".csv"):
        df = pd.read_csv(arquivo, encoding="latin1", sep=None, engine="python")
    else:
        df = pd.read_excel(arquivo)

    df = df.dropna(how='all')
    df["Montante"] = df["Montante"].apply(tratar_moeda)

    if "Dias" not in df.columns:
        df["Dias"] = 5

    agrupado = df.groupby("Cliente").agg({
        "Montante": "sum",
        "Cliente": "count",
        "Dias": "max"
    }).rename(columns={"Cliente": "Qtd_Titulos"}).reset_index()

    agrupado["Score"] = (agrupado["Dias"] * 2) + (agrupado["Montante"] / 100) + (agrupado["Qtd_Titulos"] * 5)

    def prioridade(score):
        if score > 200:
            return "🔥 Alta"
        elif score > 100:
            return "⚠️ Média"
        else:
            return "🟢 Baixa"

    agrupado["Prioridade"] = agrupado["Score"].apply(prioridade)

    ranking = agrupado.sort_values(by="Score", ascending=False)

    st.subheader("🚨 Quem cobrar agora")

    top5 = ranking.head(5)

    for _, row in top5.iterrows():
        st.write(f"{row['Cliente']} | R$ {row['Montante']:.2f} | {row['Dias']} dias | {row['Prioridade']}")

    st.subheader("📋 Lista completa")
    st.dataframe(ranking)

else:
    st.info("Envie uma planilha para começar.")
