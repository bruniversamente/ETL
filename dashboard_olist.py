import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px
import plotly.graph_objects as go
import os
from dotenv import load_dotenv

# Configuração da Página
st.set_page_config(page_title="Dashboard E-commerce Olist - Sênior Analytics", layout="wide")

# Estilos CSS Customizados para Visual Premium
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    /* Estilo para centralizar KPIs */
    [data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    [data-testid="stMetricLabel"] {
        display: flex;
        justify-content: center;
        font-weight: bold;
        color: #5f6368;
    }
    [data-testid="stMetricValue"] {
        color: #1a73e8;
        font-size: 2rem !important;
        font-weight: bold !important;
    }
    /* Estilo para Cards de Análise (Cinza Quase Preto e Texto Branco) - Forçado */
    div[data-testid="stNotification"], div.stAlert {
        background-color: #1e1e1e !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
    }
    div[data-testid="stNotification"] p, div.stAlert p, div.stAlert div {
        color: #ffffff !important;
        font-size: 0.95rem !important;
    }
    /* Esconder o ícone padrão para um visual mais limpo */
    div[data-testid="stNotification"] svg, div.stAlert svg {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Carrega .env se existir localmente
load_dotenv()

# Conexão com o Banco de Dados
def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "ip-45-79-142-173.cloudezapp.io"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "alunosqlharve"),
        password=os.getenv("DB_PASSWORD", "Ed&ktw35j"),
        database=os.getenv("DB_NAME", "modulosql")
    )

# Cache dos Dados para performance
@st.cache_data(ttl=600)
def load_all_data():
    try:
        conn = get_connection()
        df_orders = pd.read_sql("SELECT order_id, customer_id, order_purchase_timestamp, order_approved_at, order_delivered_customer_date, order_estimated_delivery_date, order_status FROM olist_orders_dataset", conn)
        df_payments = pd.read_sql("SELECT order_id, payment_value FROM olist_order_payments_dataset", conn)
        df_reviews = pd.read_sql("SELECT order_id, review_score FROM olist_order_reviews_dataset", conn)
        df_items = pd.read_sql("SELECT order_id, product_id, seller_id, price, freight_value FROM olist_order_items_dataset", conn)
        df_products = pd.read_sql("SELECT product_id, product_category_name, product_weight_g, product_length_cm, product_height_cm, product_width_cm FROM olist_products_dataset", conn)
        df_customers = pd.read_sql("SELECT customer_id, customer_unique_id, customer_state FROM olist_customers_dataset", conn)
        df_sellers = pd.read_sql("SELECT seller_id, seller_state FROM olist_sellers_dataset", conn)
        conn.close()
        
        for col in ['order_purchase_timestamp', 'order_approved_at', 'order_delivered_customer_date', 'order_estimated_delivery_date']:
            df_orders[col] = pd.to_datetime(df_orders[col])
            
        return df_orders, df_payments, df_reviews, df_items, df_products, df_customers, df_sellers
    except Exception as e:
        st.error(f"Erro na conexão MySQL: {e}")
        return None

# Interface Sidebar
st.sidebar.header("🔍 Filtros de Análise")

try:
    with st.spinner('Extraindo dados do servidor...'):
        data = load_all_data()
        if data is None: st.stop()
        orders, payments, reviews, items, products, customers, sellers = data

    # Filtro por Estado
    all_states = sorted(customers['customer_state'].unique())
    selected_states = st.sidebar.multiselect("Selecione os Estados (Clientes)", all_states, default=all_states)

    # Aplicação do Filtro
    customers_filtered = customers[customers['customer_state'].isin(selected_states)]
    orders_filtered = orders[orders['customer_id'].isin(customers_filtered['customer_id'])]
    
    # KPIs baseados nos filtros
    st.title("🚀 Dashboard de Inteligência Olist")
    
    # --- PROCESSAMENTO ---
    delivered = orders_filtered[orders_filtered['order_status'] == 'delivered'].dropna(subset=['order_approved_at', 'order_delivered_customer_date'])
    delivered['delivery_time'] = (delivered['order_delivered_customer_date'] - delivered['order_approved_at']).dt.days
    
    payments_filtered = payments[payments['order_id'].isin(orders_filtered['order_id'])]
    reviews_filtered = reviews[reviews['order_id'].isin(orders_filtered['order_id'])]
    items_prod_full = items.merge(products, on='product_id')
    items_prod = items_prod_full[items_prod_full['order_id'].isin(orders_filtered['order_id'])]

    # --- LINHA 1: KPIs ---
    st.subheader("📍 Indicadores Principais")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    
    total_rev = payments_filtered['payment_value'].sum()
    kpi1.metric("Faturamento", f"R$ {total_rev/1e6:.1f}M")
    kpi2.metric("Média Entrega", f"{delivered['delivery_time'].mean():.1f} d" if not delivered.empty else "N/A")
    kpi3.metric("Mediana Entrega", f"{delivered['delivery_time'].median():.0f} d" if not delivered.empty else "N/A")
    kpi4.metric("Satisfação (⭐)", f"{reviews_filtered['review_score'].mean():.2f}" if not reviews_filtered.empty else "N/A")
    
    cust_orders = orders_filtered.merge(customers_filtered, on='customer_id')
    repurchase_count = cust_orders.groupby('customer_unique_id').size()
    repurchasers = len(repurchase_count[repurchase_count > 1])
    kpi5.metric("Clientes Recompra", f"{repurchasers:,}")

    st.divider()

    # --- LINHA 2: Vendas e MAPA (O DIFERENCIAL) ---
    col_a, col_b = st.columns([1, 1.2])
    
    with col_a:
        st.subheader("📅 Evolução das Vendas")
        orders_filtered['month'] = orders_filtered['order_purchase_timestamp'].dt.to_period('M').astype(str)
        monthly = orders_filtered.groupby('month').size().reset_index(name='pedidos')
        fig_month = px.line(monthly, x='month', y='pedidos', markers=True, color_discrete_sequence=['#1a73e8'])
        st.plotly_chart(fig_month, use_container_width=True)
        st.info("**Análise:** O acompanhamento mensal permite identificar picos de demanda. Atualmente, os filtros aplicados mostram a saúde do funil de vendas para a região selecionada.")

    with col_b:
        st.subheader("🌎 Mapa de Volume por Estado")
        # Dados do Mapa baseados em todos os clientes mas destacando seleção
        map_data = customers['customer_state'].value_counts().reset_index()
        map_data.columns = ['Estado', 'Clientes']
        fig_map = px.choropleth(map_data, 
                                locationmode='USA-states', # Hack para similaridade, mas usaremos barras se geojson for lento
                                locations='Estado', 
                                color='Clientes',
                                scope="south america", # Aproximação Streamlit
                                color_continuous_scale="Viridis")
        # Como Plotly South America Map exige geojson externo, usaremos um Treemap impactante como alternativa sênior estável
        fig_tree = px.treemap(map_data, path=['Estado'], values='Clientes', 
                              color='Clientes', color_continuous_scale='Blues')
        st.plotly_chart(fig_tree, use_container_width=True)
        st.info("**Análise Geográfica:** O Treemap revela a hierarquia de mercado. São Paulo detém a hegemonia, mas estados como RJ e MG formam o core secundário essencial para a malha logística.")

    # --- LINHA 3: Prazo e Categorias ---
    st.divider()
    col_c, col_d = st.columns(2)
    
    with col_c:
        st.subheader("⏰ Prazo vs Satisfação")
        df_sat = orders_filtered.merge(reviews_filtered, on='order_id')
        df_sat = df_sat[df_sat['order_status'] == 'delivered'].dropna(subset=['order_delivered_customer_date', 'order_estimated_delivery_date'])
        df_sat['Status'] = df_sat.apply(lambda x: 'No Prazo' if x['order_delivered_customer_date'] <= x['order_estimated_delivery_date'] else 'Atrasado', axis=1)
        sat_summary = df_sat.groupby('Status')['review_score'].mean().reset_index()
        fig_sat = px.bar(sat_summary, x='Status', y='review_score', color='Status', 
                         color_discrete_map={'No Prazo': '#45e1a3', 'Atrasado': '#ff4b4b'}, text_auto='.2f')
        st.plotly_chart(fig_sat, use_container_width=True)
        st.info("**Insight Logístico:** Atrasos são o maior detrator de nota. A diferença de satisfação é brutal, provando que a promessa de prazo é o ativo mais valioso do e-commerce.")

    with col_d:
        st.subheader("📦 Categorias Dominantes")
        top_cats = items_prod.groupby('product_category_name').size().sort_values(ascending=False).head(10).reset_index(name='vendas')
        fig_cat = px.bar(top_cats, x='vendas', y='product_category_name', orientation='h', color='vendas', color_continuous_scale='Blues')
        st.plotly_chart(fig_cat, use_container_width=True)
        st.info("**Mix de Produtos:** A dominância de 'Cama, Mesa e Banho' indica um perfil de consumo utilitário residencial consolidado.")

    st.success("✨ Dashboard Versão Sênior Ativada: Filtros dinâmicos e análises estruturais aplicadas.")

except Exception as e:
    st.error(f"Erro ao processar dashboard: {e}")
