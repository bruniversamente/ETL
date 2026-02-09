import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px
import plotly.graph_objects as go

# Configuração da Página
st.set_page_config(page_title="Dashboard E-commerce Olist - Full Analytics", layout="wide")

# Estilos CSS Customizados para Visual Premium
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricValue"] {
        color: #1a73e8;
    }
    </style>
    """, unsafe_allow_html=True)

import os
from dotenv import load_dotenv

# Carrega .env se existir localmente
load_dotenv()

# Conexão com o Banco de Dados (Seguro para Deploy)
def get_connection():
    # Tenta ler do st.secrets (Streamlit Cloud) ou das variáveis de ambiente local (.env)
    return mysql.connector.connect(
        host=st.secrets.get("DB_HOST", os.getenv("DB_HOST", "ip-45-79-142-173.cloudezapp.io")),
        port=int(st.secrets.get("DB_PORT", os.getenv("DB_PORT", 3306))),
        user=st.secrets.get("DB_USER", os.getenv("DB_USER", "alunosqlharve")),
        password=st.secrets.get("DB_PASSWORD", os.getenv("DB_PASSWORD", "Ed&ktw35j")),
        database=st.secrets.get("DB_NAME", os.getenv("DB_NAME", "modulosql"))
    )

# Cache dos Dados para performance
@st.cache_data(ttl=600)
def load_all_data():
    try:
        conn = get_connection()
        
        # Carregando tabelas
        df_orders = pd.read_sql("SELECT order_id, customer_id, order_purchase_timestamp, order_approved_at, order_delivered_customer_date, order_estimated_delivery_date, order_status FROM olist_orders_dataset", conn)
        df_payments = pd.read_sql("SELECT order_id, payment_value FROM olist_order_payments_dataset", conn)
        df_reviews = pd.read_sql("SELECT order_id, review_score, review_comment_message FROM olist_order_reviews_dataset", conn)
        df_items = pd.read_sql("SELECT order_id, product_id, seller_id, price, freight_value FROM olist_order_items_dataset", conn)
        df_products = pd.read_sql("SELECT product_id, product_category_name, product_weight_g, product_length_cm, product_height_cm, product_width_cm FROM olist_products_dataset", conn)
        df_customers = pd.read_sql("SELECT customer_id, customer_unique_id, customer_state FROM olist_customers_dataset", conn)
        df_sellers = pd.read_sql("SELECT seller_id, seller_state FROM olist_sellers_dataset", conn)
        
        conn.close()
        
        # Conversões de Datas
        for col in ['order_purchase_timestamp', 'order_approved_at', 'order_delivered_customer_date', 'order_estimated_delivery_date']:
            df_orders[col] = pd.to_datetime(df_orders[col])
            
        return df_orders, df_payments, df_reviews, df_items, df_products, df_customers, df_sellers
    except Exception as e:
        st.error(f"Erro na conexão MySQL: {e}")
        return None

# Interface
st.title("🚀 Dashboard de Inteligência Olist")
st.markdown("Análise robusta baseada nos 9 desafios propostos.")

try:
    with st.spinner('Extraindo dados do servidor...'):
        data = load_all_data()
        if data is None:
            st.stop()
        orders, payments, reviews, items, products, customers, sellers = data

    # --- PROCESSAMENTO ---
    delivered = orders[orders['order_status'] == 'delivered'].dropna(subset=['order_approved_at', 'order_delivered_customer_date'])
    delivered['delivery_time'] = (delivered['order_delivered_customer_date'] - delivered['order_approved_at']).dt.days
    
    order_values = payments.groupby('order_id')['payment_value'].sum().reset_index()
    orders_val = orders.merge(order_values, on='order_id')
    
    items_prod = items.merge(products, on='product_id')
    items_prod['volume'] = items_prod['product_length_cm'] * items_prod['product_height_cm'] * items_prod['product_width_cm']

    # --- LINHA 1: KPIs ---
    st.subheader("📍 Indicadores Principais")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    
    total_rev = payments['payment_value'].sum()
    kpi1.metric("Faturamento", f"R$ {total_rev/1e6:.1f}M")
    kpi2.metric("Média Entrega", f"{delivered['delivery_time'].mean():.1f} dias")
    kpi3.metric("Mediana Entrega", f"{delivered['delivery_time'].median():.0f} dias")
    kpi4.metric("Satisfação (⭐)", f"{reviews['review_score'].mean():.2f}")
    
    # Recompra (Questão 9)
    cust_orders = orders.merge(customers, on='customer_id')
    repurchase_count = cust_orders.groupby('customer_unique_id').size()
    repurchasers = len(repurchase_count[repurchase_count > 1])
    kpi5.metric("Clientes Recompra", f"{repurchasers:,}")

    st.divider()

    # --- LINHA 2: Vendas e Satisfação ---
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("📅 Vendas por Mês (Qtd vs Valor)")
        orders_val['month'] = orders_val['order_purchase_timestamp'].dt.to_period('M').astype(str)
        monthly = orders_val.groupby('month').agg({'order_id': 'count', 'payment_value': 'sum'}).reset_index()
        
        fig_month = go.Figure()
        fig_month.add_trace(go.Scatter(x=monthly['month'], y=monthly['order_id'], name="Pedidos", line=dict(color="#1a73e8")))
        fig_month.add_trace(go.Bar(x=monthly['month'], y=monthly['payment_value'], name="Faturamento", yaxis="y2", opacity=0.3, marker_color="#45e1a3"))
        
        fig_month.update_layout(
            yaxis2=dict(overlaying='y', side='right'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_month, use_container_width=True)

    with col_b:
        st.subheader("⏰ Prazo vs Satisfação")
        df_sat = orders.merge(reviews, on='order_id')
        df_sat = df_sat[df_sat['order_status'] == 'delivered'].dropna(subset=['order_delivered_customer_date'])
        df_sat['Status'] = df_sat.apply(lambda x: 'No Prazo' if x['order_delivered_customer_date'] <= x['order_estimated_delivery_date'] else 'Atrasado', axis=1)
        
        sat_summary = df_sat.groupby('Status')['review_score'].mean().reset_index()
        fig_sat = px.bar(sat_summary, x='Status', y='review_score', color='Status', 
                         color_discrete_map={'No Prazo': '#45e1a3', 'Atrasado': '#ff4b4b'},
                         text_auto='.2f')
        st.plotly_chart(fig_sat, use_container_width=True)

    # --- LINHA 3: Categorias e Frete ---
    col_c, col_d = st.columns(2)
    
    with col_c:
        st.subheader("📦 Top 10 Categorias")
        top_cats = items_prod.groupby('product_category_name').size().sort_values(ascending=False).head(10).reset_index(name='vendas')
        fig_cat = px.bar(top_cats, x='vendas', y='product_category_name', orientation='h',
                        color='vendas', color_continuous_scale='Viridis')
        st.plotly_chart(fig_cat, use_container_width=True)

    with col_d:
        st.subheader("🚚 Análise de Frete (Peso vs Valor)")
        # Amostra para não travar o gráfico
        sample_freight = items_prod.sample(min(2000, len(items_prod)))
        fig_freight = px.scatter(sample_freight, x='product_weight_g', y='freight_value', 
                                 trendline="ols", opacity=0.4, color_discrete_sequence=['#1a73e8'])
        st.plotly_chart(fig_freight, use_container_width=True)

    # --- LINHA 4: Geografia e Atrasos Interestaduais ---
    col_e, col_f = st.columns(2)
    
    with col_e:
        st.subheader("🌎 Distribuição de Clientes (Estados)")
        state_counts = customers['customer_state'].value_counts().reset_index()
        state_counts.columns = ['Estado', 'Clientes']
        fig_geo = px.pie(state_counts.head(7), values='Clientes', names='Estado', hole=0.4)
        st.plotly_chart(fig_geo, use_container_width=True)

    with col_f:
        st.subheader("🚩 Atrasos: Mesmo Estado vs Diferentes")
        merged_full = orders.merge(items, on='order_id').merge(customers, on='customer_id').merge(sellers, on='seller_id')
        merged_full = merged_full[merged_full['order_status'] == 'delivered'].dropna(subset=['order_delivered_customer_date'])
        merged_full['Atraso'] = merged_full['order_delivered_customer_date'] > merged_full['order_estimated_delivery_date']
        merged_full['Rota'] = merged_full.apply(lambda x: 'Mesmo Estado' if x['customer_state'] == x['seller_state'] else 'Interestadual', axis=1)
        
        delay_stats = merged_full.groupby('Rota')['Atraso'].mean().reset_index()
        delay_stats['% Atraso'] = delay_stats['Atraso'] * 100
        fig_inter = px.bar(delay_stats, x='Rota', y='% Atraso', color='Rota', text_auto='.1f')
        st.plotly_chart(fig_inter, use_container_width=True)

    st.success("Dashboard atualizado com sucesso! Todos os 9 desafios estão cobertos visualmente.")

except Exception as e:
    st.error(f"Ocorreu um erro: {e}")
