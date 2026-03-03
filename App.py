# ================================================================
# APP Streamlit: Controle de Contratos - Consolidado 2026
# ================================================================
import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
import plotly.express as px

# ====================== CONFIGURAÇÕES ======================
GITHUB_RAW_URL = "https://raw.githubusercontent.com/bluemetrixgit/LevantamentoBluemetrix/main/Controle%20de%20Contratos%20-%20Atualizado%202026.xlsx"
LOGO_URL = "https://raw.githubusercontent.com/bluemetrixgit/Levantamento-Bluemetrix/main/logo.branca.png"

USD_TO_BRL = 5.25

SHEETS = ["BTG", "XP", "Safra", "Ágora", "XP Internacional", "Pershing", "Interactive Brokers"]
# =============================================================================

st.set_page_config(page_title="Controle de Contratos 2026", layout="wide", page_icon="📊")
st.image(LOGO_URL, use_column_width=True)
st.title("📊 Controle de Contratos - Consolidado 2026")
st.markdown("**Dados lidos diretamente do GitHub • Atualização automática**")

# ====================== CARREGAMENTO + FILTRO DE LINHAS DE RESUMO ======================
@st.cache_data(ttl=3600)
def carregar_dados():
    try:
        response = requests.get(GITHUB_RAW_URL)
        response.raise_for_status()
        excel_bytes = BytesIO(response.content)

        dfs = []
        for sheet_name in SHEETS:
            try:
                df = pd.read_excel(excel_bytes, sheet_name=sheet_name, header=1)
                
                # PARA DE LER APÓS A PRIMEIRA LINHA COMPLETAMENTE EM BRANCO
                df = df.dropna(how='all').reset_index(drop=True)
                
                # NÃO LER LINHAS DE RESUMO NO FINAL DAS ABAS (coluna B = Cliente)
                palavras_resumo = ['Contas Ativas', 'Contas Inativas', 'Contas Encerradas', 'Contas Pode Operar']
                df = df[~df.iloc[:, 1].astype(str).str.contains('|'.join(palavras_resumo), case=False, na=False)]
                
                df["Corretora"] = sheet_name
                dfs.append(df)
            except Exception as e:
                st.warning(f"Erro na aba '{sheet_name}': {e}")
        
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao baixar do GitHub: {e}")
        return pd.DataFrame()

df = carregar_dados()
if df.empty:
    st.stop()

# ====================== FORMATAÇÃO DE DATAS (sem hora) ======================
for col in ['Início da Gestão', 'Data distrato']:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')

# ====================== LIMPEZA DA COLUNA CONTA (sem ponto e sem .00) ======================
if 'Conta' in df.columns:
    df['Conta'] = pd.to_numeric(df['Conta'], errors='coerce').fillna(0).astype(int).astype(str)

# ====================== EXTRAÇÃO DO PL (mantém funcionalidade de seleção de mês) ======================
def extrair_datas_pl(df):
    datas_pl = set()
    for col in df.columns:
        col_str = str(col).strip()
        if "/" in col_str and len(col_str.split("/")) == 3:
            try:
                dt = pd.to_datetime(col_str, dayfirst=True, errors='coerce')
                if pd.notna(dt):
                    mes_ano = dt.strftime("%B/%Y")
                    datas_pl.add((dt, mes_ano, col_str))
            except:
                continue
    return sorted(datas_pl, key=lambda x: x[0], reverse=True)

datas_pl_disponiveis = extrair_datas_pl(df)
opcoes_periodo = ["Mais recente"] + [f"{mes_ano} ({col})" for _, mes_ano, col in datas_pl_disponiveis]

periodo_selecionado = st.sidebar.selectbox("Selecione o período do PL", opcoes_periodo)

if periodo_selecionado == "Mais recente":
    coluna_pl = datas_pl_disponiveis[0][2] if datas_pl_disponiveis else None
else:
    coluna_pl = periodo_selecionado.split("(")[-1].strip(")")

def extrair_pl_especifico(row, col_pl):
    if col_pl is None or col_pl not in row.index:
        return 0, None
    valor = pd.to_numeric(row[col_pl], errors='coerce')
    return round(valor) if pd.notna(valor) else 0, col_pl

df[["PL", "Data_PL"]] = df.apply(lambda row: pd.Series(extrair_pl_especifico(row, coluna_pl)), axis=1)

# Conversão internacional
internacional = ["Interactive Brokers", "Pershing", "XP Internacional"]
df.loc[df["Corretora"].isin(internacional), "PL"] = (df.loc[df["Corretora"].isin(internacional), "PL"] * USD_TO_BRL).round(0)

# ====================== COLUNAS DE EXIBIÇÃO ======================
colunas_exibicao = [
    "Corretora", "Cliente", "Conta", "Escritório", "UF", "Assessor", "Carteira",
    "Status", "Início da Gestão", "Data distrato", "PL", "Data_PL"
]

# ====================== TABS ======================
tab_geral, tab_cliente, tab_status, tab_grafico = st.tabs([
    "📊 Visão Geral", "👤 Por Cliente", "📋 Status das Contas", "📈 Fluxo Mensal/Anual"
])

# ────────────────────────────────────────────────
# ABA 1: VISÃO GERAL
# ────────────────────────────────────────────────
with tab_geral:
    st.header("Visão Geral")
    st.sidebar.header("🔎 Filtros Gerais")
    
    filtro_escritorio = st.sidebar.multiselect("Escritório", sorted(df["Escritório"].dropna().unique()))
    filtro_corretora = st.sidebar.multiselect("Corretora", sorted(df["Corretora"].unique()))
    filtro_uf = st.sidebar.multiselect("UF", sorted(df["UF"].dropna().unique()))

    df_filtrado = df.copy()
    if filtro_escritorio: df_filtrado = df_filtrado[df_filtrado["Escritório"].isin(filtro_escritorio)]
    if filtro_corretora: df_filtrado = df_filtrado[df_filtrado["Corretora"].isin(filtro_corretora)]
    if filtro_uf: df_filtrado = df_filtrado[df_filtrado["UF"].isin(filtro_uf)]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Clientes", len(df_filtrado))
    col2.metric("Patrimônio Total", f"R$ {df_filtrado['PL'].sum():,.0f}")
    col3.metric("Período do PL", periodo_selecionado)

    st.dataframe(
        df_filtrado[colunas_exibicao].style.format({"PL": "R$ {:,.0f}"}),
        hide_index=True
    )

# ────────────────────────────────────────────────
# ABA 2: POR CLIENTE
# ────────────────────────────────────────────────
with tab_cliente:
    st.header("Consolidado por Cliente")
    busca = st.text_input("🔍 Nome (ou parte)", placeholder="Ex: Alessandra Charbel")
    
    if busca.strip():
        mask = df["Cliente"].astype(str).str.contains(busca.strip(), case=False, na=False)
        df_cliente = df[mask].copy()
        
        if not df_cliente.empty:
            total_pl = df_cliente["PL"].sum()
            st.success(f"**Patrimônio Total Consolidado ({periodo_selecionado}): R$ {total_pl:,.0f}**")
            st.dataframe(
                df_cliente[colunas_exibicao].style.format({"PL": "R$ {:,.0f}"}),
                hide_index=True
            )
        else:
            st.warning("Nenhuma conta encontrada.")

# ────────────────────────────────────────────────
# ABA 3: STATUS DAS CONTAS
# ────────────────────────────────────────────────
with tab_status:
    st.header("Status das Contas")
    status_count = df["Status"].value_counts().reindex(["Ativo", "Encerrado", "Inativo"], fill_value=0)
    col1, col2, col3 = st.columns(3)
    col1.metric("Ativas", int(status_count.get("Ativo", 0)))
    col2.metric("Encerradas", int(status_count.get("Encerrado", 0)))
    col3.metric("Inativas", int(status_count.get("Inativo", 0)))

# ────────────────────────────────────────────────
# ABA 4: GRÁFICO DE BARRAS (mantido exatamente como solicitado)
# ────────────────────────────────────────────────
with tab_grafico:
    st.header("Contas Novas × Encerramentos por Mês/Ano")
    
    df["Início da Gestão"] = pd.to_datetime(df["Início da Gestão"], errors='coerce', dayfirst=True)
    df["Data distrato"]     = pd.to_datetime(df["Data distrato"],     errors='coerce', dayfirst=True)
    
    novos = df[df["Início da Gestão"].notna()].copy()
    novos["Ano-Mês"] = novos["Início da Gestão"].dt.to_period("M").astype(str)
    novos_por_mes = novos.groupby("Ano-Mês").size().reset_index(name="Novas")
    
    encerrados = df[df["Data distrato"].notna()].copy()
    encerrados["Ano-Mês"] = encerrados["Data distrato"].dt.to_period("M").astype(str)
    encerrados_por_mes = encerrados.groupby("Ano-Mês").size().reset_index(name="Encerradas")
    
    fluxo = pd.merge(novos_por_mes, encerrados_por_mes, on="Ano-Mês", how="outer").fillna(0)
    fluxo = fluxo.sort_values("Ano-Mês")
    
    fig = px.bar(
        fluxo, x="Ano-Mês", y=["Novas", "Encerradas"],
        title="Contas Novas × Encerradas por Mês",
        barmode="group",
        color_discrete_sequence=["#00CC66", "#FF3333"]
    )
    st.plotly_chart(fig, use_container_width=True)

# ====================== RODAPÉ ======================
st.caption(f"""
    • PL exibido como número inteiro • Conta sem ponto/decimal • 
    Datas formatadas como DD/MM/YYYY • Linhas de resumo ignoradas automaticamente
""")






