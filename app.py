
from datetime import date
from io import StringIO, BytesIO
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cobrança Inteligente", layout="wide")

FAIXAS = [
    ("Recuperação de Perda", 31, 999999, "+30d", "Prejuízo"),
    ("Protesto Iminente", 12, 30, "12–30d", "Urgente"),
    ("Radar de Perda", 9, 11, "9–11d", "Priorizar"),
    ("Bloqueio", 5, 8, "5–8d", "Cobrar agora"),
    ("Risco", 3, 4, "3–4d", "Avisar"),
    ("Aguardando Baixa", -999999, 2, "0–2d", "Sem ação"),
]

FAIXA_CORES = {
    "Recuperação de Perda": {"bg": "#D6D6D6", "text": "#1F2937"},
    "Protesto Iminente": {"bg": "#FFD6D6", "text": "#B91C1C"},
    "Radar de Perda": {"bg": "#FFF0B8", "text": "#A16207"},
    "Bloqueio": {"bg": "#FFE4CC", "text": "#C2410C"},
    "Risco": {"bg": "#DCEBFF", "text": "#1D4ED8"},
    "Aguardando Baixa": {"bg": "#E5E7EB", "text": "#475569"},
}

ICONES = {
    "Recuperação de Perda": "⚫",
    "Protesto Iminente": "🔴",
    "Radar de Perda": "🟡",
    "Bloqueio": "🟠",
    "Risco": "🔵",
    "Aguardando Baixa": "⚪",
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
    for nome, ini, fim, _leg, _acao in FAIXAS:
        if ini <= dias <= fim:
            return nome
    return "Aguardando Baixa"

def gerar_linhas_titulos(df_cliente):
    linhas = []
    for _, row in df_cliente.sort_values(["Venc Liq", "Montante"], ascending=[True, False]).iterrows():
        linhas.append(
            f"- Título {row['N doc']} | Vencimento {row['Venc Liq'].strftime('%d/%m/%Y')} | Valor {moeda_br(row['Montante'])}"
        )
    return "\n".join(linhas)

def gerar_mensagem_cliente(df_cliente):
    faixa = df_cliente["Faixa"].iloc[0]
    titulos = gerar_linhas_titulos(df_cliente)
    valor_total = moeda_br(df_cliente["Montante"].sum())

    if faixa == "Recuperação de Perda":
        return f"""Olá, tudo bem?

Identificamos títulos em aberto há mais tempo em seu cadastro:

{titulos}

Valor total: {valor_total}.

Precisamos tratar essa pendência o quanto antes.
Consegue nos informar uma previsão de regularização?

Caso necessário, podemos avaliar a melhor forma de negociação."""
    elif faixa == "Protesto Iminente":
        return f"""Olá, tudo bem?

Identificamos títulos em aberto:

{titulos}

Valor total: {valor_total}.

Esses títulos já estão próximos de medidas administrativas.
É importante verificarmos uma posição o quanto antes.

Fico no aguardo do seu retorno."""
    elif faixa == "Radar de Perda":
        return f"""Olá, tudo bem?

Você possui os seguintes títulos em aberto:

{titulos}

Valor total: {valor_total}.

Ainda estamos dentro do prazo de regularização sem maiores impactos.
Consegue nos informar uma previsão?"""
    elif faixa == "Bloqueio":
        return f"""Olá, tudo bem?

Seu cadastro encontra-se bloqueado devido aos títulos em aberto abaixo:

{titulos}

Valor total: {valor_total}.

Assim que houver a regularização, conseguimos seguir com a liberação normalmente.

Fico no aguardo do seu retorno."""
    elif faixa == "Risco":
        return f"""Olá, tudo bem?

Identificamos títulos recentes em aberto:

{titulos}

Valor total: {valor_total}.

Estamos entrando em contato de forma preventiva para evitar qualquer tipo de bloqueio.

Se o pagamento já foi realizado, pode desconsiderar."""
    else:
        return f"""Olá, tudo bem?

Identificamos títulos recentes em aberto:

{titulos}

Valor total: {valor_total}.

Caso o pagamento já tenha sido realizado, pode desconsiderar esta mensagem.

Se precisar de algo, estou à disposição."""

def safe_cols(df, cols):
    return [c for c in cols if c in df.columns]

def estilo_linhas(df):
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    if "Faixa" not in df.columns:
        return styles
    for idx, faixa in df["Faixa"].items():
        cfg = FAIXA_CORES.get(faixa)
        if cfg:
            styles.loc[idx, :] = f"background-color: {cfg['bg']};"
    return styles

def estilo_faixa(valor):
    cfg = FAIXA_CORES.get(valor, {"bg": "#ffffff", "text": "#222222"})
    return f"background-color: {cfg['bg']}; color: {cfg['text']}; font-weight: 800;"

st.markdown("""
<style>
.stApp { background: #f5f7fb; }
.block-container { padding-top: 1.5rem; padding-bottom: 1.2rem; max-width: 1500px; }
div[data-testid="stHorizontalBlock"] { gap: 0.45rem; }

.header-title {
    font-size: 28px;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 0;
}
.header-sub {
    font-size: 13px;
    color: #6b7280;
    margin-top: 0;
    margin-bottom: 0.5rem;
}
.metric-card {
    background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
    border: 1px solid #e6ebf2;
    border-radius: 18px;
    padding: 14px 16px;
    box-shadow: 0 6px 18px rgba(16,24,40,0.05);
}
.metric-label { font-size: 13px; color: #6b7280; margin-bottom: 6px; }
.metric-value { font-size: 28px; font-weight: 800; color: #0f172a; line-height: 1.1; }
.small-muted { font-size: 12px; color: #6b7280; }

div[data-testid="stDataFrame"] {
    border: 1px solid #e6ebf2;
    border-radius: 16px;
    overflow: hidden;
    background: white;
}

div[data-testid="stHorizontalBlock"] .stButton > button {
    width: 100%;
    min-height: 58px;
    border-radius: 12px;
    border: 1px solid #dbe3ef;
    padding: 4px 6px;
    font-weight: 800;
    font-size: 12px;
    line-height: 1.15;
    white-space: pre-line;
}
.legend-mini {
    font-size: 10px;
    color: #6b7280;
    text-align: center;
    margin-top: 2px;
    margin-bottom: 0;
}
.small-clear button {
    min-height: 34px !important;
    font-size: 11px !important;
    padding: 2px 6px !important;
}
</style>
""", unsafe_allow_html=True)

if "faixas_sel_v121" not in st.session_state:
    st.session_state["faixas_sel_v121"] = []
if "status_manual_v121" not in st.session_state:
    st.session_state["status_manual_v121"] = {}
if "busca_v121" not in st.session_state:
    st.session_state["busca_v121"] = ""
if "nao_cobrados_v121" not in st.session_state:
    st.session_state["nao_cobrados_v121"] = False

st.markdown('<div class="header-title">🧾 Cobrança Inteligente</div>', unsafe_allow_html=True)
st.markdown('<div class="header-sub">Veja. Decida. Cobre.</div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns([1.25, 0.8, 1.2, 0.8, 0.55])
with c1:
    arquivo = st.file_uploader("Arquivo", type=["xlsx", "xls", "csv"], label_visibility="collapsed")
with c2:
    data_ref = st.date_input("Data", value=date.today(), format="DD/MM/YYYY", label_visibility="collapsed")
with c3:
    busca = st.text_input("Buscar cliente", value=st.session_state["busca_v121"], placeholder="Buscar cliente", label_visibility="collapsed")
with c4:
    nao_cobrados = st.checkbox("Não cobrados", value=st.session_state["nao_cobrados_v121"])
with c5:
    st.markdown('<div class="small-clear">', unsafe_allow_html=True)
    limpar = st.button("Limpar", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

if limpar:
    st.session_state["faixas_sel_v121"] = []
    st.session_state["busca_v121"] = ""
    st.session_state["nao_cobrados_v121"] = False
    st.rerun()

st.session_state["busca_v121"] = busca
st.session_state["nao_cobrados_v121"] = nao_cobrados

if arquivo is None:
    st.info("Envie o arquivo para começar.")
    st.stop()

try:
    base_df, origem, linha_cabecalho = ler_arquivo(arquivo)
except Exception as e:
    st.error(f"Erro ao ler o arquivo: {e}")
    st.stop()

df = base_df.copy()
df["Dias"] = (pd.to_datetime(data_ref) - df["Venc Liq"]).dt.days.astype(int)
df["Faixa"] = df["Dias"].apply(faixa_por_dias)

for cliente in df["Cliente"].astype(str).unique():
    if cliente not in st.session_state["status_manual_v121"]:
        st.session_state["status_manual_v121"][cliente] = "Não cobrado"

df["Situação Manual"] = df["Cliente"].astype(str).map(st.session_state["status_manual_v121"])

clientes_df = (
    df.groupby(["Cliente", "Nome"], as_index=False)
      .agg(
          Qtd_Titulos=("N doc", "count"),
          Valor_total=("Montante", "sum"),
          Maior_Dias=("Dias", "max"),
          Situação_Manual=("Situação Manual", "first"),
      )
)
clientes_df["Faixa_Principal"] = clientes_df["Maior_Dias"].apply(faixa_por_dias)
clientes_df["Situação Manual"] = clientes_df["Cliente"].astype(str).map(st.session_state["status_manual_v121"])

st.markdown('<div class="small-muted">👉 Escolha onde focar agora</div>', unsafe_allow_html=True)

btn_cols = st.columns(6)
for i, (nome, _ini, _fim, legenda, acao) in enumerate(FAIXAS):
    qtd = clientes_df[clientes_df["Faixa_Principal"] == nome]["Cliente"].nunique()
    ativo = nome in st.session_state["faixas_sel_v121"]
    label = f"{ICONES[nome]} {nome}\n{qtd} clientes\n{acao}"

    with btn_cols[i]:
        if st.button(label, key=f"faixa_{i}_{nome}", type="primary" if ativo else "secondary", use_container_width=True):
            selecionadas = list(st.session_state["faixas_sel_v121"])
            if nome in selecionadas:
                selecionadas.remove(nome)
            else:
                selecionadas.append(nome)
            st.session_state["faixas_sel_v121"] = selecionadas
            st.rerun()
        st.markdown(f'<div class="legend-mini">{legenda}</div>', unsafe_allow_html=True)

faixas_ativas = st.session_state["faixas_sel_v121"]

if faixas_ativas:
    filtrado_clientes = clientes_df[clientes_df["Faixa_Principal"].isin(faixas_ativas)].copy()
else:
    filtrado_clientes = clientes_df.copy()

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

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Clientes filtrados</div><div class="metric-value">{filtrado_clientes["Cliente"].nunique():,}</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Títulos filtrados</div><div class="metric-value">{len(filtrado):,}</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Valor total</div><div class="metric-value">{moeda_br(filtrado["Montante"].sum())}</div></div>', unsafe_allow_html=True)

left, right = st.columns([4, 1])

with left:
    st.markdown("### Checklist de cobrança")
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
        key="editor_checklist_v121"
    )

    for _, row in edited.iterrows():
        st.session_state["status_manual_v121"][str(row["Cliente"])] = row["Situação Manual"]

    filtrado["Situação Manual"] = filtrado["Cliente"].astype(str).map(st.session_state["status_manual_v121"])

with right:
    st.markdown("### Mensagem pronta para enviar")
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
        st.caption("Copie e envie no WhatsApp.")

st.markdown("### Lista detalhada")
colunas_finais = safe_cols(
    filtrado,
    ["Cliente", "Nome", "N doc", "Referência", "Tipo", "Data Doc", "Venc Liq", "Montante", "Dias", "Faixa", "Situação Manual"]
)
mostrar = filtrado[colunas_finais].copy()

if "Data Doc" in mostrar.columns:
    mostrar["Data Doc"] = pd.to_datetime(mostrar["Data Doc"], errors="coerce").dt.strftime("%d/%m/%Y")
if "Venc Liq" in mostrar.columns:
    mostrar["Venc Liq"] = pd.to_datetime(mostrar["Venc Liq"], errors="coerce").dt.strftime("%d/%m/%Y")
if "Montante" in mostrar.columns:
    mostrar["Montante"] = mostrar["Montante"].map(moeda_br)

styled = mostrar.style.apply(estilo_linhas, axis=None)
if "Faixa" in mostrar.columns:
    styled = styled.map(estilo_faixa, subset=["Faixa"])

st.dataframe(styled, use_container_width=True, hide_index=True, height=620)

st.download_button(
    "Baixar CSV",
    mostrar.to_csv(index=False).encode("utf-8-sig"),
    file_name="resultado_vencidos.csv",
    mime="text/csv",
    use_container_width=True
)
