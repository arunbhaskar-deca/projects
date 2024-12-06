import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from collections import Counter
import openfoodfacts
from openfoodfacts.types import Country, COUNTRY_CODE_TO_NAME

# Set page config for a wider layout
st.set_page_config(layout="wide", page_title="Food Products Dashboard")

# Custom CSS for styling
st.markdown("""
    <style>
    .stPlotlyChart {
        background-color: #ffffff;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 10px;
    }
    .st-emotion-cache-1y4p8pa {
        padding: 2rem 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Title with custom styling
st.title("🍽️ Global Food Products Analysis")
st.markdown("---")

# Function to fetch data using OpenFoodFacts API
def fetch_products_by_country(country_code, page_size=1000):
    # Configure the API
    api = openfoodfacts.API("food_dashboard", country=country_code)

    # Search products
    search_result = api.product.text_search(query="food", page_size=page_size)
    
    return search_result['products']

# Country selection
countries = {}
for key, val in COUNTRY_CODE_TO_NAME.items():
    new_key = val.replace('en:', '').replace('-', ' ').capitalize()
    countries[new_key] = key

selected_country = st.selectbox("Select a Country", sorted(list(countries.keys())))

# Add a button to trigger data fetching
if st.button("Fetch Data"):
    # Fetch data
    with st.spinner('Fetching data from OpenFoodFacts...'):
        products = fetch_products_by_country(countries[selected_country])

# Create two columns for the layout
col1, col2 = st.columns(2)

# 1. NutriScore Distribution
with col1:
    st.subheader("NutriScore Distribution")
    nutri_scores = [p.nutriscore_grade.upper() if hasattr(p, 'nutriscore_grade') and p.nutriscore_grade else 'Unknown' for p in products]
    nutri_score_counts = Counter(nutri_scores)
    
    fig1 = go.Figure(data=[
        go.Bar(
            x=list(nutri_score_counts.keys()),
            y=list(nutri_score_counts.values()),
            marker_color=['#2ecc71', '#27ae60', '#f1c40f', '#e67e22', '#e74c3c', '#95a5a6'],
        )
    ])
    fig1.update_layout(
        title_text="Distribution of NutriScore",
        xaxis_title="NutriScore",
        yaxis_title="Number of Products",
        template="plotly_white"
    )
    st.plotly_chart(fig1, use_container_width=True)

# 2. Top 5 Brands
with col2:
    st.subheader("Top 5 Food Brands")
    brands = [p.brands.split(',')[0].strip() if hasattr(p, 'brands') and p.brands else 'Unknown' for p in products]
    top_brands = Counter(brands).most_common(5)
    
    fig2 = go.Figure(data=[
        go.Pie(
            labels=[brand[0] for brand in top_brands],
            values=[brand[1] for brand in top_brands],
            hole=.3
        )
    ])
    fig2.update_layout(
        title_text="Top 5 Brands by Product Count",
        template="plotly_white"
    )
    st.plotly_chart(fig2, use_container_width=True)

# 3. Top 5 Categories
with col1:
    st.subheader("Top 5 Food Categories")
    categories = []
    for p in products:
        if hasattr(p, 'categories_tags') and p.categories_tags:
            categories.extend([cat.replace('en:', '') for cat in p.categories_tags])
    top_categories = Counter(categories).most_common(5)
    
    fig3 = go.Figure(data=[
        go.Bar(
            x=[cat[1] for cat in top_categories],
            y=[cat[0] for cat in top_categories],
            orientation='h',
            marker_color='#3498db'
        )
    ])
    fig3.update_layout(
        title_text="Top 5 Categories by Product Count",
        xaxis_title="Number of Products",
        yaxis_title="Category",
        template="plotly_white"
    )
    st.plotly_chart(fig3, use_container_width=True)

# 4. Top 5 Ingredients
with col2:
    st.subheader("Top 5 Ingredients")
    ingredients = []
    for p in products:
        if hasattr(p, 'ingredients_tags') and p.ingredients_tags:
            ingredients.extend([i.replace('en:', '') for i in p.ingredients_tags])
    top_ingredients = Counter(ingredients).most_common(5)
    
    fig4 = go.Figure(data=[
        go.Bar(
            x=[ing[1] for ing in top_ingredients],
            y=[ing[0] for ing in top_ingredients],
            orientation='h',
            marker_color='#9b59b6'
        )
    ])
    fig4.update_layout(
        title_text="Top 5 Ingredients",
        xaxis_title="Frequency",
        yaxis_title="Ingredient",
        template="plotly_white"
    )
    st.plotly_chart(fig4, use_container_width=True)
