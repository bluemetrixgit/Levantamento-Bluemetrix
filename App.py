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

# ====================== CARREGAMENTO COM PARADA NA LINHA EM BRANCO ======================
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

# ====================== EXTRAÇÃO DO PL + COLUNAS NOVAS ======================
def pegar_pl_mais_recente(row):
    valores = {}
    for col in row.index:
        col_str = str(col).strip()
        if "/" in col_str and len(col_str.split("/")) == 3:
            try:
                data = pd.to_datetime(col_str, dayfirst=True, errors="coerce")
                if pd.notna(data):
                    val = pd.to_numeric(row[col], errors="coerce")
                    if pd.notna(val) and val != 0:
                        valores[data] = val
            except:
                continue
    if valores:
        data_max = max(valores.keys())
        return round(valores[data_max]), data_max.strftime("%d/%m/%Y")  # arredonda para inteiro
    return 0, None

df[["PL", "Data_PL"]] = df.apply(lambda row: pd.Series(pegar_pl_mais_recente(row)), axis=1)

# Conversão internacional
internacional = ["Interactive Brokers", "Pershing", "XP Internacional"]
df.loc[df["Corretora"].isin(internacional), "PL"] = (df.loc[df["Corretora"].isin(internacional), "PL"] * USD_TO_BRL).round(0)

# ====================== COLUNAS QUE VAMOS EXIBIR ======================
colunas_exibicao = [
    "Corretora", "Cliente", "Conta", "Escritório", "UF", "Assessor", "Carteira",
    "Status", "Início da Gestão", "Data distrato", "PL", "Data_PL"
]

# ====================== TABS ======================
tab_geral, tab_cliente, tab_status, tab_grafico = st.tabs([
    "📊 Visão Geral", 
    "👤 Por Cliente", 
    "📋 Status das Contas",
    "📈 Fluxo Mensal/Anual"
])

# ────────────────────────────────────────────────
# ABA 1: VISÃO GERAL
# ────────────────────────────────────────────────
with tab_geral:
    st.header("Visão Geral")
    st.sidebar.header("🔎 Filtros")
    
    filtro_esc = st.sidebar.multiselect("Escritório", sorted(df["Escritório"].dropna().unique()))
    filtro_corr = st.sidebar.multiselect("Corretora", sorted(df["Corretora"].unique()))
    filtro_uf = st.sidebar.multiselect("UF", sorted(df["UF"].dropna().unique()))

    df_f = df.copy()
    if filtro_esc:  df_f = df_f[df_f["Escritório"].isin(filtro_esc)]
    if filtro_corr: df_f = df_f[df_f["Corretora"].isin(filtro_corr)]
    if filtro_uf:   df_f = df_f[df_f["UF"].isin(filtro_uf)]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Clientes", len(df_f))
    col2.metric("Patrimônio Total", f"R$ {df_f['PL'].sum():,.0f}")
    col3.metric("Dólar", f"R$ {USD_TO_BRL}")

    st.dataframe(
        df_f[colunas_exibicao].style.format({"PL": "{:,.0f}"}),
        hide_index=True
    )

# ────────────────────────────────────────────────
# ABA 2: POR CLIENTE
# ────────────────────────────────────────────────
with tab_cliente:
    st.header("Consolidado por Cliente")
    busca = st.text_input("🔍 Nome do cliente", placeholder="Alessandra Charbel")
    
    if busca.strip():
        mask = df["Cliente"].astype(str).str.contains(busca.strip(), case=False, na=False)
        df_c = df[mask].copy()
        
        if not df_c.empty:
            st.success(f"**Total Consolidado: R$ {df_c['PL'].sum():,.0f}** ({len(df_c)} contas)")
            st.dataframe(df_c[colunas_exibicao].style.format({"PL": "{:,.0f}"}), hide_index=True)
            
            csv = df_c[colunas_exibicao].to_csv(index=False).encode()
            st.download_button("Baixar este cliente", csv, f"{busca.replace(' ','_')}.csv", "text/csv")
        else:
            st.warning("Nenhuma conta encontrada.")

# ────────────────────────────────────────────────
# ABA 3: STATUS DAS CONTAS
# ────────────────────────────────────────────────
with tab_status:
    st.header("Status das Contas")
    
    status_count = df["Status"].value_counts().reindex(["Ativo", "Encerrado", "Inativo"], fill_value=0)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ativas", status_count.get("Ativo", 0))
    col2.metric("Encerradas", status_count.get("Encerrado", 0))
    col3.metric("Inativas", status_count.get("Inativo", 0))
    
    st.dataframe(status_count.reset_index(), hide_index=True)

# ────────────────────────────────────────────────
# ABA 4: GRÁFICO DE FLUXO (NOVAS × ENCERRADAS)
# ────────────────────────────────────────────────
with tab_grafico:
    st.header("Contas Novas × Encerramentos por Mês/Ano")
    
    # Converter datas
    df["Início da Gestão"] = pd.to_datetime(df["Início da Gestão"], errors="coerce", dayfirst=True)
    df["Data distrato"]     = pd.to_datetime(df["Data distrato"],     errors="coerce", dayfirst=True)
    
    # Contagem de novas contas por mês
    novos = df[df["Início da Gestão"].notna()].copy()
    novos["Ano-Mês"] = novos["Início da Gestão"].dt.to_period("M").astype(str)
    novos_por_mes = novos.groupby("Ano-Mês").size().reset_index(name="Novas")
    
    # Contagem de encerramentos por mês
    encerrados = df[df["Data distrato"].notna()].copy()
    encerrados["Ano-Mês"] = encerrados["Data distrato"].dt.to_period("M").astype(str)
    encerrados_por_mes = encerrados.groupby("Ano-Mês").size().reset_index(name="Encerradas")
    
    # Merge e gráfico
    fluxo = pd.merge(novos_por_mes, encerrados_por_mes, on="Ano-Mês", how="outer").fillna(0)
    fluxo = fluxo.sort_values("Ano-Mês")
    
    fig = px.bar(
        fluxo, x="Ano-Mês", y=["Novas", "Encerradas"],
        title="Contas Novas × Encerradas por Mês",
        labels={"value": "Quantidade", "variable": "Tipo"},
        barmode="group",
        color_discrete_sequence=["#00CC66", "#FF3333"]
    )
    st.plotly_chart(fig, use_container_width=True)

# ====================== RODAPÉ ======================
st.caption(f"""
    • PL exibido como número inteiro • Parada automática na primeira linha em branco  
    • Inclui Status, Início da Gestão e Data distrato • 
    Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}
""")




