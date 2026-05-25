import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from pandasql import sqldf
from streamlit_lottie import st_lottie
import plotly.graph_objects as go

#SETUP
st.set_page_config(
    page_title="Dashboard de Vendas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Mono:wght@100;200;300;400;500;600;700;800;900&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# PALETA DE CORES
CORES_PALETA = [
    "#6D6DED",  # Roxo primário (brand)
    '#FF006E',  # Rosa forte
    "#FC4F9A",
    "#FFA10A",
    "#FFCA0B",  # Amarelo destaque
]

#FUNÇÕES
def format_num(valor, prefixo=''):
    """Formata número para escala (mil, milhões)"""
    for unidade in ['', 'mil']:
        if valor < 1000:
            return f'{prefixo} {valor:.2f} {unidade}'
        valor /= 1000
    return f'{prefixo} {valor:.2f} milhões'

#DADOS
@st.cache_data
def carregar_dados():
    """Carrega dados da API e processa"""
    url = 'https://labdados.com/produtos'
    response = requests.get(url)
    dados = pd.DataFrame.from_dict(response.json())
    dados['Data da Compra'] = pd.to_datetime(dados['Data da Compra'], format='%d/%m/%Y')
    return dados

@st.cache_data
def carregar_lottie(url):
    """Carrega animação Lottie"""
    return requests.get(url).json()

dados = carregar_dados()

with st.sidebar:
    st.header("Filtros")
    anos = st.multiselect("Ano",
        options=sorted(dados['Data da Compra'].dt.year.unique()),
        key="filtro_ano")
    cats = st.multiselect("Categoria",
        options=sorted(dados['Categoria do Produto'].unique()),
        key="filtro_categoria")
    
df = dados.copy()
if anos:
    dados = dados[dados['Data da Compra'].dt.year.isin(anos)]
if cats:
    dados = dados[dados['Categoria do Produto'].isin(cats)]

# QUERIES SQL
q_receita_total = """
SELECT SUM(Preço) as total 
FROM dados
"""
receita_total = sqldf(q_receita_total, locals())['total'].values[0]

q_total_vendas = """
SELECT COUNT(*) as total 
FROM dados
"""
total_vendas = sqldf(q_total_vendas, locals())['total'].values[0]

q_receita_estados = """
SELECT 
    "Local da compra" as estado,
    SUM(Preço) as receita,
    COUNT(*) as quantidade
FROM dados
GROUP BY "Local da compra"
ORDER BY receita DESC
"""
receita_estados = sqldf(q_receita_estados, locals())

q_tabela = """
SELECT * 
FROM dados
"""
tabela_dados = sqldf(q_tabela, locals())

# QUERY DE RECEITA MENSAL
q_receita_mensal = """
SELECT 
    strftime('%Y', "Data da Compra") as ano,
    strftime('%m', "Data da Compra") as mes,
    SUM(Preço) as receita
FROM dados
GROUP BY strftime('%Y', "Data da Compra"), strftime('%m', "Data da Compra")
ORDER BY ano, mes
"""
receita_mensal = sqldf(q_receita_mensal, locals())
receita_mensal['mes'] = receita_mensal['mes'].astype(int)

# Agregar dados por estado para o mapa
q_mapa = """
SELECT 
    "Local da compra" as estado,
    SUM(Preço) as receita,
    COUNT(*) as quantidade,
    AVG(lat) as lat,
    AVG(lon) as lon
FROM dados
GROUP BY "Local da compra"
"""
mapa_dados = sqldf(q_mapa, locals())

# Query para Top 10 vendedores (estados) - para pie
q_top10_vendedores = """
SELECT 
    "Vendedor" as vendedor,
    SUM(Preço) as value
FROM dados
GROUP BY "vendedor"
ORDER BY value DESC
LIMIT 10
"""
top10_vendedores = sqldf(q_top10_vendedores, locals())

q_compras_por_estado = """
SELECT
    "Local da compra" as estado,
    SUM(Preço) as receita
FROM dados
GROUP BY "Local da compra"
ORDER BY receita DESC
LIMIT 20
"""
compras_por_estado =sqldf(q_compras_por_estado, locals())

# Formatar receita e quantidade usando format_num
mapa_dados['Receita'] = mapa_dados['receita'].apply(lambda x: format_num(x, 'R$'))
mapa_dados['Quantidade'] = mapa_dados['quantidade'].apply(lambda x: format_num(x))

# GRAFICOS PLOTLY
fig_mapa_receita = px.scatter_geo(mapa_dados,
                                  lat='lat',
                                  lon='lon',
                                  size='receita',
                                  scope='south america',
                                  fitbounds='locations',
                                  template='plotly_dark',
                                  hover_name='estado',
                                  hover_data={'Receita': True, 'Quantidade': True, 'lat': False, 'lon': False, 'receita': False, 'quantidade': False},
                                  title='Receita por estado',
                                  color='receita',
                                  color_continuous_scale=CORES_PALETA,
                                  size_max=80
                                  )

fig_mapa_receita.update_layout(
    height=860,
    margin=dict(l=0, r=0, t=30, b=0),
    clickmode='event+select'
)
fig_mapa_receita.update_traces(marker=dict(opacity=0.8), selected=dict(marker=dict(opacity=1, size=15)))

# x='ano'/'mes' = eixo horizontal (período temporal)
# y='receita' = eixo vertical (valor da receita em R$)
fig_receita_mensal = px.line(receita_mensal,
                             x='mes',
                             y='receita',
                             color='ano',
                             markers=True,
                             line_dash='ano',
                             line_shape='linear',
                             template='plotly_dark',
                             title='Receita por Mês',
                             labels={'mes': 'Mês', 'receita': 'Receita (R$)', 'ano': 'Ano'},
                             color_discrete_sequence=CORES_PALETA
                             )

# Customizar layout do gráfico mensal
fig_receita_mensal.update_layout(
    height=400,
    title_font_size=20,
    hovermode='x unified',
    margin=dict(l=0, r=0, t=30, b=0),
    clickmode='event+select'
)
fig_receita_mensal.update_traces(marker=dict(size=10, opacity=0.8), selected=dict(marker=dict(size=15, opacity=1)))

# PIE CHART TOP 10 VENDEDORES
fig_pie = px.pie(
    top10_vendedores,
    names='vendedor',
    values='value',
    template='plotly_dark',
    title='Top 10 Vendedores',
    color_discrete_sequence=CORES_PALETA
)
fig_pie.update_layout(
    title_font_size=20,
    height=360,
    margin=dict(l=0, r=0, t=30, b=0)
)

fig_pie.update_traces(hoverinfo='label+percent', textinfo='percent', textfont_size=18,
                  marker=dict(colors=CORES_PALETA, line=dict(color="#333333", width=1)))

fig_bar_estados = px.bar(
    compras_por_estado,
    y='receita',
    x='estado',
    text_auto='.2s',
    title="Desempenho de Vendas por Região",
    template='plotly_dark',
    labels={'estado': 'Estado', 'receita': 'Receita (R$)'},
    color='receita',
    color_continuous_scale=CORES_PALETA)

fig_bar_estados.update_layout(
    hovermode='x unified',
    title_font_size=15,
    height=500,
    margin=dict(l=0, r=0, t=40, b=0)
)
fig_bar_estados.update_traces(textfont_size=18)

# INTERFACE
col1, col2 = st.columns([1.1, 0.9])

with col1:
    st.markdown("""<h1 style="font-family: 'Noto Sans Mono', monospace; font-size: 5rem; text-align: left; font-weight: 200; margin: 0; padding: 0; letter-spacing: -1px;"><span style="border-bottom: 3px solid #7B7FF5;">Dashboard</span> de <span style="font-weight: 900; font-style: italic; background: linear-gradient(135deg, #7B7FF5, #B0C4DE); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">Vendas</span></h1>""", unsafe_allow_html=True)
    st.markdown("""<h2 style="font-family: 'Inter', sans-serif; font-size: 1.1rem; text-align: left; font-weight: 100; margin: 0; background: #F7F7FF0; border-radius: 5px; padding: 5px; letter-spacing: 0px;"><span style="border-bottom: 1.3px;">construído com python, sql e <span style="font-style: italic; color: #FF006E;">curiosidade</span>.</span></h2>""", unsafe_allow_html=True)
with col2:
    lottie_data = carregar_lottie('https://lottie.host/38267cdd-483d-4709-8803-b3f2828e4960/fSGX5sLHJc.json')
    st_lottie(lottie_data, height=350, speed=2, loop=True)

# TABS
tab1, tab2= st.tabs(["📊 Visão Geral", "🗺️ Regiões"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.metric('Receita', format_num(receita_total, 'R$'))
        st.plotly_chart(fig_mapa_receita, use_container_width=True, config={'displayModeBar': False})
    with col2:
        st.metric('Quantidade de vendas', format_num(total_vendas))
        st.plotly_chart(fig_receita_mensal, use_container_width=True, config={'displayModeBar': False})
        st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

with tab2:
    st.markdown("# Desempenho de Vendas por Região")
    st.markdown("""
    <p style="font-family: 'Noto Sans Mono', monospace; font-size: 1.1rem; font-weight: 100;">
        Os estados com maior receita concentram-se no <b>Sudeste</b> e <b>Sul</b>.
        O ranking abaixo detalha o faturamento por estado, do maior para o menor.
    </p>
    """, unsafe_allow_html=True)
    st.plotly_chart(fig_bar_estados, use_container_width=True, config={'displayModeBar': False})
    
    st.dataframe(
        tabela_dados[['Produto', 'Categoria do Produto', 'Preço', 'Vendedor', 'Local da compra', 'Tipo de pagamento']],
        use_container_width=True
    )