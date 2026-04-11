
from datetime import date
from io import StringIO, BytesIO
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Gestão de Vencidos V11", layout="wide")

FAIXAS = [
    ("Recuperação de Perda", 31, 999999, "Clientes com mais de 30 dias de atraso"),
    ("Protesto Iminente", 12, 30, "Clientes com atraso entre 12 e 30 dias"),
    ("Radar de Perda", 9, 11, "Clientes com atraso entre 9 e 11 dias"),
    ("Bloqueio", 5, 8, "Clientes com atraso entre 5 e 8 dias"),
    ("Risco", 3, 4, "Clientes com atraso entre 3 e 4 dias"),
    ("Aguardando Baixa", -999999, 2, "Clientes com até 2 dias de atraso"),
]

FAIXA_ORDEM = {nome: i+1 for i, (nome, *_rest) in enumerate(FAIXAS)}

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
        linha_bruta = bruto.iloc[i]
        if linha_bruta.isna().all():
            continue
        linha = [normalizar_texto(x) for x in linha_bruta.tolist()]
        if (
            "Cliente" in linha and
            "Nome" in linha and
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

    obrigatorias = ["Cliente", "Nome", "N doc", "Referência", "Tipo", "Data Doc", "Venc Liq", "Montante"]
    faltando = [c for c in obrigatorias if c not in df.columns]
    if faltando:
        raise ValueError("Faltam colunas obrigatórias: " + ", ".join(faltando))

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

def descricao_faixa(nome):
    for n, _ini, _fim, desc in FAIXAS:
        if n == nome:
            return desc
    return ""

def score_prioridade(dias, valor_total, qtd_titulos):
    return (dias * 2) + (valor_total / 100.0) + (qtd_titulos * 5)

def label_prioridade(score):
    if score > 200:
        return "🔥 Alta"
    elif score > 100:
        return "⚠️ Média"
    return "🟢 Baixa"

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

def estilo_faixa(valor):
    cfg = FAIXA_CORES.get(valor, {"bg": "#ffffff", "text": "#222222"})
    return f"background-color: {cfg['bg']}; color: {cfg['text']}; font-weight: 800;"

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
.card-choice {
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 10px 12px;
    background: white;
    min-height: 86px;
}
.card-choice strong { display:block; font-size: 15px; color:#111827; }
.card-choice small { color:#6b7280; display:block; margin-top:4px; line-height:1.25; }
div[data-testid="stDataFrame"] {
    border: 1px solid #e6ebf2;
    border-radius: 16px;
    overflow: hidden;
    background: white;
}
</style>
""", unsafe_allow_html=True)

st.title("Gestão de Vencidos V11")
st.caption("Versão refeita e estável: leitura robusta de CSV/Excel, cards por faixa, checklist por cliente e ranking de cobrança.")

if "faixas_sel_v11" not in st.session_state:
    st.session_state["faixas_sel_v11"] = [f[0] for f in FAIXAS]
if "busca_v11" not in st.session_state:
    st.session_state["busca_v11"] = ""
if "nao_cobrados_v11" not in st.session_state:
    st.session_state["nao_cobrados_v11"] = False
if "status_manual_v11" not in st.session_state:
    st.session_state["status_manual_v11"] = {}

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
df["ordem"] = df["Faixa"].map(FAIXA_ORDEM)

for cliente in df["Cliente"].astype(str).unique():
    if cliente not in st.session_state["status_manual_v11"]:
        st.session_state["status_manual_v11"][cliente] = "Não cobrado"

df["Situação Manual"] = df["Cliente"].astype(str).map(st.session_state["status_manual_v11"])

# agregados por cliente
clientes_df = (
    df.groupby(["Cliente", "Nome"], as_index=False)
      .agg(
          Qtd_Titulos=("N doc", "count"),
          Valor_total=("Montante", "sum"),
          Maior_Dias=("Dias", "max"),
          Pior_Ordem=("ordem", "min"),
          Faixa_Principal=("ordem", lambda s: sorted(s)[0])
      )
)
# map faixa principal from order
ordem_para_faixa = {v: k for k, v in FAIXA_ORDEM.items()}
clientes_df["Faixa_Principal"] = clientes_df["Pior_Ordem"].map(ordem_para_faixa)
clientes_df["Score"] = clientes_df.apply(lambda r: score_prioridade(r["Maior_Dias"], r["Valor_total"], r["Qtd_Titulos"]), axis=1)
clientes_df["Prioridade"] = clientes_df["Score"].apply(label_prioridade)
clientes_df["Situação Manual"] = clientes_df["Cliente"].astype(str).map(st.session_state["status_manual_v11"])

# filtros
f1, f2, f3 = st.columns([1.5, 1.4, 1.0])
with f1:
    busca = st.text_input("Cliente ou nome", value=st.session_state["busca_v11"])
with f2:
    nao_cobrados = st.checkbox("Mostrar só não cobrados", value=st.session_state["nao_cobrados_v11"])
with f3:
    st.write("")
    st.write("")
    limpar = st.button("Limpar filtros", use_container_width=True)

if limpar:
    busca = ""
    nao_cobrados = False
    st.session_state["faixas_sel_v11"] = [f[0] for f in FAIXAS]

st.session_state["busca_v11"] = busca
st.session_state["nao_cobrados_v11"] = nao_cobrados

# cards/faixas (multiseleção)
counts = {}
for nome, ini, fim, desc in FAIXAS:
    qtd_clientes = clientes_df[clientes_df["Faixa_Principal"] == nome]["Cliente"].nunique()
    counts[nome] = qtd_clientes

st.markdown('<div class="section-title">Faixas de atraso</div>', unsafe_allow_html=True)
card_cols = st.columns(3)
for idx, (nome, _ini, _fim, desc) in enumerate(FAIXAS):
    col = card_cols[idx % 3]
    with col:
        marcado = nome in st.session_state["faixas_sel_v11"]
        novo = st.checkbox(
            f"{nome} ({counts[nome]})",
            value=marcado,
            key=f"faixa_checkbox_{idx}",
            help=desc,
        )
        st.markdown(f'<div class="card-choice"><strong>{nome}</strong><small>{desc}</small></div>', unsafe_allow_html=True)
        if novo and nome not in st.session_state["faixas_sel_v11"]:
            st.session_state["faixas_sel_v11"].append(nome)
        if (not novo) and nome in st.session_state["faixas_sel_v11"]:
            st.session_state["faixas_sel_v11"].remove(nome)

faixas_ativas = st.session_state["faixas_sel_v11"] or [f[0] for f in FAIXAS]

filtrado_clientes = clientes_df[clientes_df["Faixa_Principal"].isin(faixas_ativas)].copy()
if busca:
    mask = (
        filtrado_clientes["Cliente"].astype(str).str.contains(busca, case=False, na=False) |
        filtrado_clientes["Nome"].astype(str).str.contains(busca, case=False, na=False)
    )
    filtrado_clientes = filtrado_clientes[mask]
if nao_cobrados:
    filtrado_clientes = filtrado_clientes[filtrado_clientes["Situação Manual"] == "Não cobrado"]

clientes_filtrados_set = set(filtrado_clientes["Cliente"].astype(str).tolist())
filtrado = df[df["Cliente"].astype(str).isin(clientes_filtrados_set)].copy()

# cards executivos
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Clientes filtrados</div><div class="metric-value">{filtrado_clientes["Cliente"].nunique():,}</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Títulos filtrados</div><div class="metric-value">{len(filtrado):,}</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Valor total</div><div class="metric-value">{moeda_br(filtrado["Montante"].sum())}</div></div>', unsafe_allow_html=True)
with m4:
    alta = filtrado_clientes[filtrado_clientes["Prioridade"] == "🔥 Alta"]["Cliente"].nunique()
    st.markdown(f'<div class="metric-card"><div class="metric-label">Prioridade alta</div><div class="metric-value">{alta:,}</div></div>', unsafe_allow_html=True)

# ranking top 5
st.markdown('<div class="section-title">Quem cobrar agora</div><div class="small-muted">Ranking automático considerando maior atraso, valor e quantidade de títulos.</div>', unsafe_allow_html=True)
top5 = filtrado_clientes.sort_values(["Score", "Valor_total"], ascending=[False, False]).head(5).copy()
if len(top5) == 0:
    st.info("Nenhum cliente disponível no ranking.")
else:
    top5_view = top5[["Cliente", "Nome", "Valor_total", "Qtd_Titulos", "Maior_Dias", "Prioridade", "Faixa_Principal"]].copy()
    top5_view["Valor_total"] = top5_view["Valor_total"].map(moeda_br)
    st.dataframe(top5_view, use_container_width=True, hide_index=True)

left, right = st.columns([1.5, 0.9])

with left:
    st.markdown('<div class="section-title">Checklist de cobrança</div><div class="small-muted">Agrupado por cliente para marcar uma vez só.</div>', unsafe_allow_html=True)
    checklist = filtrado_clientes.sort_values(["Pior_Ordem", "Valor_total"], ascending=[True, False]).copy()
    checklist_view = checklist[["Cliente", "Nome", "Qtd_Titulos", "Valor_total", "Maior_Dias", "Faixa_Principal", "Prioridade", "Situação Manual"]].copy()
    checklist_view["Valor_total"] = checklist_view["Valor_total"].map(moeda_br)

    edited = st.data_editor(
        checklist_view,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        height=380,
        disabled=["Cliente", "Nome", "Qtd_Titulos", "Valor_total", "Maior_Dias", "Faixa_Principal", "Prioridade"],
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
        key="editor_checklist_v11"
    )

    for _, row in edited.iterrows():
        st.session_state["status_manual_v11"][str(row["Cliente"])] = row["Situação Manual"]

    filtrado["Situação Manual"] = filtrado["Cliente"].astype(str).map(st.session_state["status_manual_v11"])

with right:
    st.markdown('<div class="section-title">Gerador de mensagem</div><div class="small-muted">Uma única mensagem por cliente.</div>', unsafe_allow_html=True)
    clientes_msg = filtrado_clientes.sort_values(["Pior_Ordem", "Valor_total"], ascending=[True, False]).copy()
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

st.markdown(f'<div class="section-title" style="margin-top:14px;">Tabela final de cobrança</div><div class="small-muted">Mostrando {len(filtrado):,} registros</div>', unsafe_allow_html=True)

mostrar = filtrado[["Cliente","Nome","N doc","Referência","Tipo","Data Doc","Venc Liq","Montante","Dias","Faixa","Prioridade","Ação","Situação Manual"]].copy()
mostrar["Data Doc"] = mostrar["Data Doc"].dt.strftime("%d/%m/%Y")
mostrar["Venc Liq"] = mostrar["Venc Liq"].dt.strftime("%d/%m/%Y")
mostrar["Montante"] = mostrar["Montante"].map(moeda_br)

styled = mostrar.style.map(estilo_faixa, subset=["Faixa"])
st.dataframe(styled, use_container_width=True, hide_index=True, height=620)

csv_saida = filtrado[["Cliente","Nome","N doc","Referência","Tipo","Data Doc","Venc Liq","Montante","Dias","Faixa","Prioridade","Ação","Situação Manual"]].copy()
csv_saida["Data Doc"] = csv_saida["Data Doc"].dt.strftime("%d/%m/%Y")
csv_saida["Venc Liq"] = csv_saida["Venc Liq"].dt.strftime("%d/%m/%Y")

st.download_button(
    "Baixar resultado em CSV",
    csv_saida.to_csv(index=False).encode("utf-8-sig"),
    file_name="resultado_vencidos.csv",
    mime="text/csv",
    use_container_width=True
)
