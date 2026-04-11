
from datetime import date
from io import StringIO, BytesIO
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Gestão de Vencidos V11.3", layout="wide")

FAIXAS = [
    ("Recuperação de Perda", 31, 999999, "30+d"),
    ("Protesto Iminente", 12, 30, "12-30d"),
    ("Radar de Perda", 9, 11, "9-11d"),
    ("Bloqueio", 5, 8, "5-8d"),
    ("Risco", 3, 4, "3-4d"),
    ("Aguardando Baixa", -999999, 2, "0-2d"),
]
FAIXA_LABEL = {nome: desc for nome, _a, _b, desc in FAIXAS}

FAIXA_CORES = {
    "Recuperação de Perda": {"bg": "#E5E7EB", "text": "#111827"},
    "Protesto Iminente": {"bg": "#FEE2E2", "text": "#991B1B"},
    "Radar de Perda": {"bg": "#FEF3C7", "text": "#92400E"},
    "Bloqueio": {"bg": "#FFEDD5", "text": "#9A3412"},
    "Risco": {"bg": "#DBEAFE", "text": "#1D4ED8"},
    "Aguardando Baixa": {"bg": "#E0E7FF", "text": "#3730A3"},
}

SITUACOES_MANUAIS = ["Não cobrado", "Cobrado hoje", "Aguardando retorno", "Resolvido"]

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

def moeda_br(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def normalizar_texto(x):
    if pd.isna(x):
        return ""
    return str(x).replace("\n", " ").replace("\r", " ").strip()

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
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except Exception:
        return None

def converter_montante(serie):
    return serie.apply(converter_valor_brasileiro)

def ler_csv_bruto(uploaded_file):
    raw = uploaded_file.getvalue()
    tentativas = [
        ("utf-16-le", ";"),
        ("utf-16", ";"),
        ("utf-8-sig", ";"),
        ("latin-1", ";"),
        ("utf-8-sig", ","),
        ("latin-1", ","),
        ("utf-8-sig", "\t"),
        ("latin-1", "\t"),
    ]
    ultimo_erro = None
    for enc, sep in tentativas:
        try:
            texto = raw.decode(enc)
            df = pd.read_csv(StringIO(texto), sep=sep, header=None)
            if df.shape[1] >= 3:
                return df, f"CSV ({sep})"
        except Exception as e:
            ultimo_erro = e
    raise ValueError(f"Não consegui ler o CSV. {ultimo_erro}")

def achar_cabecalho(bruto):
    for i in range(min(40, len(bruto))):
        linha = [normalizar_texto(x) for x in bruto.iloc[i].tolist()]
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
        bruto, origem = ler_csv_bruto(uploaded_file)
    else:
        bruto = pd.read_excel(BytesIO(uploaded_file.getvalue()), header=None)
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
    for col in ["Cliente", "Nome", "N doc", "Referência", "Tipo"]:
        df[col] = df[col].map(normalizar_texto)
    df = df[df["Cliente"] != ""].copy()
    df["Data Doc"] = pd.to_datetime(df["Data Doc"], dayfirst=True, errors="coerce")
    df["Venc Liq"] = pd.to_datetime(df["Venc Liq"], dayfirst=True, errors="coerce")
    df["Montante"] = converter_montante(df["Montante"])
    df = df.dropna(subset=["Venc Liq", "Montante"]).copy()
    return df, origem, header_idx + 1

def faixa_por_dias(dias):
    for nome, ini, fim, _desc in FAIXAS:
        if ini <= dias <= fim:
            return nome
    return "Aguardando Baixa"

def gerar_mensagem_cliente(df_cliente):
    total = df_cliente["Montante"].sum()
    linhas = []
    for _, row in df_cliente.sort_values(["Venc Liq", "Montante"], ascending=[True, False]).iterrows():
        linhas.append(
            f"- Título {row['N doc']} | Vencimento {row['Venc Liq'].strftime('%d/%m/%Y')} | Valor {moeda_br(row['Montante'])}"
        )
    return f"""Olá, tudo bem?

Identificamos que você possui os seguintes títulos em aberto:

{chr(10).join(linhas)}

Valor total em aberto: {moeda_br(total)}.

Poderia nos informar uma previsão de regularização?

Fico à disposição."""

def safe_cols(df, cols):
    return [c for c in cols if c in df.columns]

def estilo_faixa(valor):
    cfg = FAIXA_CORES.get(valor, {"bg": "#ffffff", "text": "#222222"})
    return f"background-color: {cfg['bg']}; color: {cfg['text']}; font-weight: 800;"

st.markdown("""
<style>
.stApp { background: #f5f7fb; }
.block-container { padding-top: 0.7rem; padding-bottom: 1.5rem; max-width: 1500px; }
.metric-card {
    background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
    border: 1px solid #e6ebf2;
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 6px 18px rgba(16,24,40,0.05);
}
.metric-label { font-size: 13px; color: #6b7280; margin-bottom: 8px; }
.metric-value { font-size: 28px; font-weight: 800; color: #0f172a; line-height: 1.1; }
.section-title { font-size: 18px; font-weight: 800; color: #0f172a; margin-bottom: 8px; }
.small-muted { font-size: 12px; color: #6b7280; }
div[data-testid="stDataFrame"] {
    border: 1px solid #e6ebf2;
    border-radius: 16px;
    overflow: hidden;
    background: white;
}
.stButton > button {
    width: 100%;
    border-radius: 12px;
    border: 1px solid #dbe3ef;
    padding: 0.45rem 0.5rem;
    font-weight: 700;
    min-height: 44px;
    font-size: 13px;
}
.legend-line{
    font-size:11px;
    color:#6b7280;
    text-align:center;
    margin-top:-2px;
    margin-bottom:8px;
}
</style>
""", unsafe_allow_html=True)

st.title("Gestão de Vencidos V11.3")
st.caption("Layout mais compacto, botões em uma linha e tabela final colorida.")

if "faixas_sel_v113" not in st.session_state:
    st.session_state["faixas_sel_v113"] = [f[0] for f in FAIXAS]
if "busca_v113" not in st.session_state:
    st.session_state["busca_v113"] = ""
if "nao_cobrados_v113" not in st.session_state:
    st.session_state["nao_cobrados_v113"] = False
if "status_manual_v113" not in st.session_state:
    st.session_state["status_manual_v113"] = {}

arquivo = st.file_uploader("Selecione o arquivo", type=["xlsx", "xls", "csv"])
if arquivo is None:
    st.info("Envie o arquivo para começar.")
    st.stop()

try:
    base_df, origem, linha_cabecalho = ler_arquivo(arquivo)
except Exception as e:
    st.error(f"Erro ao ler o arquivo: {e}")
    st.stop()

c1, c2 = st.columns([1, 1])
with c1:
    data_ref = st.date_input("Data de referência", value=date.today(), format="DD/MM/YYYY")
with c2:
    st.write("")
    st.info(f"Arquivo lido como {origem} | Cabeçalho encontrado na linha {linha_cabecalho}")

df = base_df.copy()
df["Dias"] = (pd.to_datetime(data_ref) - df["Venc Liq"]).dt.days.astype(int)
df["Faixa"] = df["Dias"].apply(faixa_por_dias)

for cliente in df["Cliente"].astype(str).unique():
    if cliente not in st.session_state["status_manual_v113"]:
        st.session_state["status_manual_v113"][cliente] = "Não cobrado"

df["Situação Manual"] = df["Cliente"].astype(str).map(st.session_state["status_manual_v113"])

clientes_df = (
    df.groupby(["Cliente", "Nome"], as_index=False)
      .agg(
          Qtd_Titulos=("N doc", "count"),
          Valor_total=("Montante", "sum"),
          Maior_Dias=("Dias", "max"),
          Faixa_Principal=("Dias", lambda s: faixa_por_dias(max(s))),
          Situação_Manual=("Situação Manual", "first"),
      )
)
clientes_df["Situação Manual"] = clientes_df["Cliente"].astype(str).map(st.session_state["status_manual_v113"])

# filtros topo compactos
f1, f2, f3 = st.columns([1.5, 1.0, 0.8])
with f1:
    busca = st.text_input("Cliente ou nome", value=st.session_state["busca_v113"])
with f2:
    nao_cobrados = st.checkbox("Mostrar só não cobrados", value=st.session_state["nao_cobrados_v113"])
with f3:
    st.write("")
    st.write("")
    if st.button("Limpar filtros", use_container_width=True):
        busca = ""
        nao_cobrados = False
        st.session_state["faixas_sel_v113"] = [f[0] for f in FAIXAS]
        st.rerun()

st.session_state["busca_v113"] = busca
st.session_state["nao_cobrados_v113"] = nao_cobrados

# botões em uma linha
st.markdown('<div class="section-title">Faixas de atraso</div>', unsafe_allow_html=True)
btn_cols = st.columns(6)
for i, (nome, _ini, _fim, desc) in enumerate(FAIXAS):
    qtd = clientes_df[clientes_df["Faixa_Principal"] == nome]["Cliente"].nunique()
    ativo = nome in st.session_state["faixas_sel_v113"]
    with btn_cols[i]:
        if st.button(f"{nome} ({qtd})", key=f"faixa_btn_v113_{i}", type="primary" if ativo else "secondary"):
            atuais = st.session_state["faixas_sel_v113"]
            if nome in atuais:
                atuais.remove(nome)
            else:
                atuais.append(nome)
            if len(atuais) == 0:
                st.session_state["faixas_sel_v113"] = [f[0] for f in FAIXAS]
            st.rerun()
        st.markdown(f'<div class="legend-line">{desc}</div>', unsafe_allow_html=True)

faixas_ativas = st.session_state["faixas_sel_v113"]

filtrado_clientes = clientes_df[clientes_df["Faixa_Principal"].isin(faixas_ativas)].copy()
if busca:
    mask = (
        filtrado_clientes["Cliente"].astype(str).str.contains(busca, case=False, na=False) |
        filtrado_clientes["Nome"].astype(str).str.contains(busca, case=False, na=False)
    )
    filtrado_clientes = filtrado_clientes[mask]
if nao_cobrados:
    filtrado_clientes = filtrado_clientes[filtrado_clientes["Situação Manual"] == "Não cobrado"]

clientes_set = set(filtrado_clientes["Cliente"].astype(str).tolist())
filtrado = df[df["Cliente"].astype(str).isin(clientes_set)].copy()

# cards executivos
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Clientes filtrados</div><div class="metric-value">{filtrado_clientes["Cliente"].nunique():,}</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Títulos filtrados</div><div class="metric-value">{len(filtrado):,}</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Valor total</div><div class="metric-value">{moeda_br(filtrado["Montante"].sum())}</div></div>', unsafe_allow_html=True)
with m4:
    bloqueio_clientes = filtrado_clientes[filtrado_clientes["Faixa_Principal"].isin(["Bloqueio", "Radar de Perda", "Protesto Iminente"])]["Cliente"].nunique()
    st.markdown(f'<div class="metric-card"><div class="metric-label">Clientes em bloqueio</div><div class="metric-value">{bloqueio_clientes:,}</div></div>', unsafe_allow_html=True)

left, right = st.columns([1.5, 0.9])

with left:
    st.markdown('<div class="section-title">Checklist de cobrança</div><div class="small-muted">Agrupado por cliente para marcar uma vez só.</div>', unsafe_allow_html=True)
    checklist = filtrado_clientes.sort_values(["Maior_Dias", "Valor_total"], ascending=[False, False]).copy()
    checklist_view = checklist[["Cliente", "Nome", "Qtd_Titulos", "Valor_total", "Maior_Dias", "Faixa_Principal", "Situação Manual"]].copy()
    checklist_view["Valor_total"] = checklist_view["Valor_total"].map(moeda_br)

    edited = st.data_editor(
        checklist_view,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        height=360,
        disabled=["Cliente", "Nome", "Qtd_Titulos", "Valor_total", "Maior_Dias", "Faixa_Principal"],
        column_config={
            "Qtd_Titulos": st.column_config.NumberColumn("Qtd. títulos"),
            "Valor_total": st.column_config.TextColumn("Montante total"),
            "Maior_Dias": st.column_config.NumberColumn("Maior atraso"),
            "Faixa_Principal": st.column_config.TextColumn("Faixa"),
            "Situação Manual": st.column_config.SelectboxColumn(
                "Situação Manual",
                options=SITUACOES_MANUAIS,
                required=True,
            ),
        },
        key="editor_checklist_v113"
    )

    for _, row in edited.iterrows():
        st.session_state["status_manual_v113"][str(row["Cliente"])] = row["Situação Manual"]

    filtrado["Situação Manual"] = filtrado["Cliente"].astype(str).map(st.session_state["status_manual_v113"])

with right:
    st.markdown('<div class="section-title">Gerador de mensagem</div><div class="small-muted">Uma única mensagem por cliente.</div>', unsafe_allow_html=True)
    clientes_msg = filtrado_clientes.sort_values(["Maior_Dias", "Valor_total"], ascending=[False, False]).copy()
    if len(clientes_msg) == 0:
        st.info("Nenhum cliente disponível.")
    else:
        clientes_msg["descricao"] = clientes_msg.apply(
            lambda r: f"{r['Cliente']} - {r['Nome']} | {r['Qtd_Titulos']} título(s) | {moeda_br(r['Valor_total'])}",
            axis=1
        )
        idx = st.selectbox(
            "Selecione o cliente",
            options=clientes_msg.index.tolist(),
            format_func=lambda i: clientes_msg.loc[i, "descricao"]
        )
        cliente_sel = str(clientes_msg.loc[idx, "Cliente"])
        df_cliente = filtrado[filtrado["Cliente"].astype(str) == cliente_sel].copy()
        st.code(gerar_mensagem_cliente(df_cliente), language=None)
        st.caption("Use o ícone de copiar no bloco acima para enviar no WhatsApp.")

st.markdown(f'<div class="section-title" style="margin-top:12px;">Tabela final de cobrança</div><div class="small-muted">Mostrando {len(filtrado):,} registros</div>', unsafe_allow_html=True)

colunas_finais = safe_cols(filtrado, ["Cliente","Nome","N doc","Referência","Tipo","Data Doc","Venc Liq","Montante","Dias","Faixa","Situação Manual"])
mostrar = filtrado[colunas_finais].copy()

if "Data Doc" in mostrar.columns:
    mostrar["Data Doc"] = pd.to_datetime(mostrar["Data Doc"], errors="coerce").dt.strftime("%d/%m/%Y")
if "Venc Liq" in mostrar.columns:
    mostrar["Venc Liq"] = pd.to_datetime(mostrar["Venc Liq"], errors="coerce").dt.strftime("%d/%m/%Y")
if "Montante" in mostrar.columns:
    mostrar["Montante"] = mostrar["Montante"].map(moeda_br)

styled = mostrar.style.map(estilo_faixa, subset=["Faixa"])
st.dataframe(styled, use_container_width=True, hide_index=True, height=620)

csv_saida = mostrar.copy()
st.download_button(
    "Baixar resultado em CSV",
    csv_saida.to_csv(index=False).encode("utf-8-sig"),
    file_name="resultado_vencidos.csv",
    mime="text/csv",
    use_container_width=True
)
