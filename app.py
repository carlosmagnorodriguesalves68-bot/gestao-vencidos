
from datetime import date
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Gestão de Vencidos", layout="wide")

REGRAS = [
    (-9999, 2, "AGUARDANDO BAIXA", "Nenhuma ação necessária"),
    (3, 4, "RISCO DE BLOQUEIO", "Orientar cliente"),
    (5, 7, "BLOQUEADO", "Informar cliente"),
    (8, 11, "RADAR PERDA", "Cobrança diária"),
    (12, 60, "PROTESTO IMINENTE", "Cobrança urgente"),
    (61, 99999, "INADIMPLÊNCIA", "Tratar inadimplência"),
]

ORDEM_STATUS = [
    "INADIMPLÊNCIA",
    "PROTESTO IMINENTE",
    "RADAR PERDA",
    "BLOQUEADO",
    "RISCO DE BLOQUEIO",
    "AGUARDANDO BAIXA",
]

STATUS_CORES = {
    "AGUARDANDO BAIXA": {"bg": "#DDF5E3", "text": "#166534"},
    "RISCO DE BLOQUEIO": {"bg": "#DCEBFF", "text": "#1D4ED8"},
    "BLOQUEADO": {"bg": "#FFE4CC", "text": "#C2410C"},
    "RADAR PERDA": {"bg": "#FFF0B8", "text": "#A16207"},
    "PROTESTO IMINENTE": {"bg": "#FFD6D6", "text": "#B91C1C"},
    "INADIMPLÊNCIA": {"bg": "#D6D6D6", "text": "#1F2937"},
}

SITUACOES_MANUAIS = [
    "Não cobrado",
    "Cobrado hoje",
    "Aguardando retorno",
    "Resolvido",
]

COLUNAS_DESEJADAS = {
    "Cliente": "Cliente",
    "Nome": "Nome",
    "N doc.": "N doc",
    "N doc": "N doc",
    "Referência": "Referência",
    "Referencia": "Referência",
    "Tipo": "Tipo",
    "Data Doc.": "Data Doc",
    "Data Doc": "Data Doc",
    "Venc.Liq.": "Venc Liq",
    "Venc Liq": "Venc Liq",
    "Montante": "Montante",
}

def normalizar_texto(x):
    if pd.isna(x):
        return ""
    return str(x).replace("\\n", " ").replace("\\r", " ").strip()

def moeda_br(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def converter_valor_brasileiro(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)

    s = str(valor).strip()
    if s == "" or s.lower() in {"nan", "none"}:
        return None

    s = s.replace("R$", "").replace("\xa0", "").replace(" ", "")

    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None

    if "," in s:
        s = s.replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None

    if s.count(".") > 1:
        s = s.replace(".", "")
        try:
            return float(s)
        except Exception:
            return None

    try:
        return float(s)
    except Exception:
        return None

def converter_montante(serie):
    return serie.apply(converter_valor_brasileiro)

def achar_cabecalho(bruto):
    for i in range(min(30, len(bruto))):
        linha_bruta = bruto.iloc[i]
        if linha_bruta.isna().all():
            continue
        linha = [normalizar_texto(x) for x in linha_bruta.tolist()]
        if (
            "Cliente" in linha and "Nome" in linha and
            ("N doc." in linha or "N doc" in linha) and
            ("Venc.Liq." in linha or "Venc Liq" in linha) and
            "Montante" in linha
        ):
            return i
    return None

def ler_arquivo(uploaded_file):
    nome = uploaded_file.name.lower()
    if nome.endswith(".csv"):
        try:
            bruto = pd.read_csv(uploaded_file, sep=";", encoding="utf-16-le", header=None)
        except Exception:
            uploaded_file.seek(0)
            bruto = pd.read_csv(uploaded_file, sep=";", encoding="latin-1", header=None)
        origem = "CSV"
    else:
        bruto = pd.read_excel(uploaded_file, header=None)
        origem = "Excel"

    while len(bruto) > 0 and bruto.iloc[0].isna().all():
        bruto = bruto.iloc[1:].reset_index(drop=True)

    header_idx = achar_cabecalho(bruto)
    if header_idx is None:
        raise ValueError("Não encontrei a linha do cabeçalho automaticamente.")

    cab = [normalizar_texto(x) for x in bruto.iloc[header_idx].tolist()]
    df = bruto.iloc[header_idx + 1 :].copy()
    df.columns = cab
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

    manter = {}
    for col in df.columns:
        nome_col = normalizar_texto(col)
        if nome_col in COLUNAS_DESEJADAS:
            manter[col] = COLUNAS_DESEJADAS[nome_col]

    df = df[list(manter.keys())].rename(columns=manter)

    obrigatorias = ["Cliente", "Nome", "N doc", "Referência", "Tipo", "Data Doc", "Venc Liq", "Montante"]
    faltando = [c for c in obrigatorias if c not in df.columns]
    if faltando:
        raise ValueError("Faltam colunas obrigatórias: " + ", ".join(faltando))

    for col in ["Cliente", "Nome", "N doc", "Referência", "Tipo"]:
        df[col] = df[col].map(normalizar_texto)

    df = df[df["Cliente"] != ""]
    df["Data Doc"] = pd.to_datetime(df["Data Doc"], dayfirst=True, errors="coerce")
    df["Venc Liq"] = pd.to_datetime(df["Venc Liq"], dayfirst=True, errors="coerce")
    df["Montante"] = converter_montante(df["Montante"])
    df = df.dropna(subset=["Venc Liq", "Montante"])
    return df, origem, header_idx + 1

def classificar(dias):
    for ini, fim, status, acao in REGRAS:
        if ini <= dias <= fim:
            return status, acao
    return "SEM STATUS", ""

def prioridade_por_status(status):
    mapa = {
        "INADIMPLÊNCIA": "Crítica",
        "PROTESTO IMINENTE": "Alta",
        "RADAR PERDA": "Alta",
        "BLOQUEADO": "Alta",
        "RISCO DE BLOQUEIO": "Média",
        "AGUARDANDO BAIXA": "Baixa",
    }
    return mapa.get(status, "")

def aplicar_logica(df, data_ref):
    df = df.copy()
    df["Dias"] = (pd.to_datetime(data_ref) - df["Venc Liq"]).dt.days.astype(int)
    df[["Status", "Ação"]] = df["Dias"].apply(lambda x: pd.Series(classificar(int(x))))
    df["Prioridade"] = df["Status"].apply(prioridade_por_status)
    df["ordem"] = df["Status"].apply(lambda x: ORDEM_STATUS.index(x) if x in ORDEM_STATUS else 999)
    return df.sort_values(["ordem", "Montante", "Dias"], ascending=[True, False, False])

def estilo_linhas(df):
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    for idx, status in df["Status"].items():
        if status == "INADIMPLÊNCIA":
            styles.loc[idx, :] = "background-color: #ececec;"
        elif status == "PROTESTO IMINENTE":
            styles.loc[idx, :] = "background-color: #fff0f0;"
        elif status == "RADAR PERDA":
            styles.loc[idx, :] = "background-color: #fff9df;"
        elif status == "BLOQUEADO":
            styles.loc[idx, :] = "background-color: #fff4ea;"
    return styles

def estilo_status(valor):
    cfg = STATUS_CORES.get(valor, {"bg": "#ffffff", "text": "#222222"})
    return f"background-color: {cfg['bg']}; color: {cfg['text']}; font-weight: 800;"

def gerar_chave(row):
    return f"{row['Cliente']}|{row['N doc']}|{row['Referência']}|{row['Venc Liq']}|{row['Montante']}"

def gerar_mensagem_cliente(df_cliente):
    primeira = df_cliente.iloc[0]
    status = primeira["Status"]
    nome = primeira["Nome"]
    total = df_cliente["Montante"].sum()

    linhas = []
    for _, row in df_cliente.sort_values(["Venc Liq", "Montante"], ascending=[True, False]).iterrows():
        linhas.append(
            f"- Título {row['N doc']} | Vencimento {row['Venc Liq'].strftime('%d/%m/%Y')} | Valor {moeda_br(row['Montante'])}"
        )

    cabecalho = f"Olá, tudo bem?\n\nIdentificamos os seguintes títulos em aberto do cliente {nome}:\n\n"
    corpo = "\n".join(linhas)
    fechamento = f"\n\nValor total em aberto: {moeda_br(total)}.\n\nSituação atual: {status}.\nPor favor, nos informe uma previsão de regularização.\n\nFico à disposição."
    return cabecalho + corpo + fechamento

st.markdown("""
<style>
.stApp { background: #f5f7fb; }
.block-container { padding-top: 0.8rem; padding-bottom: 2rem; max-width: 1500px; }
.metric-card {
    background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
    border: 1px solid #e6ebf2;
    border-radius: 18px;
    padding: 18px 20px;
    box-shadow: 0 6px 18px rgba(16,24,40,0.05);
}
.metric-label { font-size: 13px; color: #6b7280; margin-bottom: 8px; }
.metric-value { font-size: 30px; font-weight: 800; color: #0f172a; line-height: 1.1; }
.section-title { font-size: 18px; font-weight: 800; color: #0f172a; margin-bottom: 8px; }
.small-muted { font-size: 13px; color: #6b7280; }
div[data-testid="stDataFrame"] {
    border: 1px solid #e6ebf2;
    border-radius: 16px;
    overflow: hidden;
    background: white;
}
</style>
""", unsafe_allow_html=True)

st.title("Gestão de Vencidos")
st.caption("Suba a planilha bruta do dia. O sistema ignora colunas desnecessárias, calcula os dias e monta a cobrança.")

arquivo = st.file_uploader("Selecione o arquivo", type=["xlsx", "xls", "csv"])

if arquivo is None:
    st.info("Envie o arquivo para começar.")
    st.stop()

try:
    base_df, origem, linha_cabecalho = ler_arquivo(arquivo)
except Exception as e:
    st.error(f"Erro ao ler o arquivo: {e}")
    st.stop()

cinfo1, cinfo2 = st.columns([1, 1])
with cinfo1:
    data_ref = st.date_input("Data de referência para cálculo dos dias", value=date.today(), format="DD/MM/YYYY")
with cinfo2:
    st.write("")
    st.info(f"Arquivo lido como {origem} | Cabeçalho encontrado na linha {linha_cabecalho}")

df = aplicar_logica(base_df, data_ref)
df["chave"] = df.apply(gerar_chave, axis=1)

if "status_manual" not in st.session_state:
    st.session_state["status_manual"] = {}

for _, row in df.iterrows():
    chave = row["chave"]
    if chave not in st.session_state["status_manual"]:
        st.session_state["status_manual"][chave] = "Não cobrado"

df["Situação Manual"] = df["chave"].map(st.session_state["status_manual"])

f1, f2, f3 = st.columns([1.2, 1.4, 1.1])
with f1:
    status_sel = st.multiselect("Status", ORDEM_STATUS, default=ORDEM_STATUS, key="status_multiselect")
with f2:
    busca = st.text_input("Cliente ou nome")
with f3:
    mostrar_so_nao_cobrados = st.checkbox("Mostrar só não cobrados")

filtrado = df[df["Status"].isin(status_sel)].copy()
if busca:
    mask = filtrado["Cliente"].astype(str).str.contains(busca, case=False, na=False) | filtrado["Nome"].astype(str).str.contains(busca, case=False, na=False)
    filtrado = filtrado[mask]
if mostrar_so_nao_cobrados:
    filtrado = filtrado[filtrado["Situação Manual"] == "Não cobrado"]
filtrado = filtrado.sort_values(["ordem", "Montante", "Dias"], ascending=[True, False, False])

total_titulos = len(filtrado)
valor_total = filtrado["Montante"].sum()
clientes_criticos = filtrado[filtrado["Status"].isin(["INADIMPLÊNCIA", "PROTESTO IMINENTE"])]["Cliente"].nunique()
clientes_bloqueados = filtrado[filtrado["Status"] == "BLOQUEADO"]["Cliente"].nunique()

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Total de títulos</div><div class="metric-value">{total_titulos:,}</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Valor vencido</div><div class="metric-value">{moeda_br(valor_total)}</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Clientes críticos</div><div class="metric-value">{clientes_criticos:,}</div></div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Clientes bloqueados</div><div class="metric-value">{clientes_bloqueados:,}</div></div>', unsafe_allow_html=True)

resumo_filtrado = (
    filtrado.groupby("Status", as_index=False)
            .agg(Quantidade=("Status", "size"), Valor=("Montante", "sum"), Clientes=("Cliente", "nunique"))
)
acao_por_status = {
    "AGUARDANDO BAIXA": "Nenhuma ação necessária",
    "RISCO DE BLOQUEIO": "Orientar cliente",
    "BLOQUEADO": "Informar cliente",
    "RADAR PERDA": "Cobrança diária",
    "PROTESTO IMINENTE": "Cobrança urgente",
    "INADIMPLÊNCIA": "Tratar inadimplência",
}
if not resumo_filtrado.empty:
    resumo_filtrado["ordem"] = resumo_filtrado["Status"].apply(lambda x: ORDEM_STATUS.index(x) if x in ORDEM_STATUS else 999)
    resumo_filtrado["Ação principal"] = resumo_filtrado["Status"].map(acao_por_status)
    resumo_filtrado = resumo_filtrado.sort_values("ordem").drop(columns="ordem")
    resumo_exibir = resumo_filtrado.copy()
    resumo_exibir["Valor"] = resumo_exibir["Valor"].map(moeda_br)
else:
    resumo_exibir = pd.DataFrame(columns=["Status", "Quantidade", "Clientes", "Valor", "Ação principal"])

st.markdown('<div class="section-title">Resumo por status</div>', unsafe_allow_html=True)
st.dataframe(resumo_exibir, use_container_width=True, hide_index=True)

left, right = st.columns([1.15, 1])

with left:
    st.markdown('<div class="section-title">Checklist de cobrança</div><div class="small-muted">Marque o andamento do que você já cobrou hoje.</div>', unsafe_allow_html=True)
    editor_df = filtrado[["chave", "Cliente", "Nome", "Montante", "Dias", "Status", "Prioridade", "Situação Manual"]].copy()
    editor_df["Montante"] = editor_df["Montante"].map(moeda_br)

    edited = st.data_editor(
        editor_df,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        height=360,
        disabled=["chave", "Cliente", "Nome", "Montante", "Dias", "Status", "Prioridade"],
        column_config={
            "chave": None,
            "Situação Manual": st.column_config.SelectboxColumn(
                "Situação Manual",
                options=SITUACOES_MANUAIS,
                required=True,
            ),
        },
        key="editor_checklist"
    )

    for _, row in edited.iterrows():
        st.session_state["status_manual"][row["chave"]] = row["Situação Manual"]

filtrado["Situação Manual"] = filtrado["chave"].map(st.session_state["status_manual"])

with right:
    st.markdown('<div class="section-title">Gerador de mensagem</div><div class="small-muted">Selecione o cliente e gere uma única mensagem com todos os títulos.</div>', unsafe_allow_html=True)

    clientes_msg = (
        filtrado.groupby(["Cliente", "Nome"], as_index=False)
                .agg(
                    Valor_total=("Montante", "sum"),
                    Titulos=("N doc", "count"),
                    Pior_ordem=("ordem", "min")
                )
                .sort_values(["Pior_ordem", "Valor_total"], ascending=[True, False])
    )

    if len(clientes_msg) == 0:
        st.info("Nenhum cliente disponível para gerar mensagem.")
    else:
        clientes_msg["descricao"] = clientes_msg.apply(
            lambda r: f"{r['Cliente']} - {r['Nome']} | {r['Titulos']} título(s) | {moeda_br(r['Valor_total'])}",
            axis=1
        )
        idx = st.selectbox(
            "Selecione o cliente",
            options=clientes_msg.index.tolist(),
            format_func=lambda i: clientes_msg.loc[i, "descricao"]
        )
        cliente_sel = clientes_msg.loc[idx, "Cliente"]
        df_cliente = filtrado[filtrado["Cliente"] == cliente_sel].copy()
        mensagem = gerar_mensagem_cliente(df_cliente)
        st.code(mensagem, language=None)
        st.caption("Use o ícone de copiar no bloco acima para enviar no WhatsApp.")

st.markdown(
    f'<div class="section-title" style="margin-top:14px;">Tabela final de cobrança</div><div class="small-muted">Mostrando {len(filtrado):,} registros</div>',
    unsafe_allow_html=True
)

mostrar = filtrado[["Cliente","Nome","N doc","Referência","Tipo","Data Doc","Venc Liq","Montante","Dias","Status","Prioridade","Ação","Situação Manual"]].copy()
mostrar["Data Doc"] = mostrar["Data Doc"].dt.strftime("%d/%m/%Y")
mostrar["Venc Liq"] = mostrar["Venc Liq"].dt.strftime("%d/%m/%Y")
mostrar["Montante"] = mostrar["Montante"].map(moeda_br)

styled = mostrar.style.apply(estilo_linhas, axis=None).map(estilo_status, subset=["Status"])
st.dataframe(styled, use_container_width=True, hide_index=True, height=620)

csv_saida = filtrado[["Cliente","Nome","N doc","Referência","Tipo","Data Doc","Venc Liq","Montante","Dias","Status","Prioridade","Ação","Situação Manual"]].copy()
csv_saida["Data Doc"] = csv_saida["Data Doc"].dt.strftime("%d/%m/%Y")
csv_saida["Venc Liq"] = csv_saida["Venc Liq"].dt.strftime("%d/%m/%Y")

st.download_button(
    "Baixar resultado em CSV",
    csv_saida.to_csv(index=False).encode("utf-8-sig"),
    file_name="resultado_vencidos.csv",
    mime="text/csv",
    use_container_width=True
)
