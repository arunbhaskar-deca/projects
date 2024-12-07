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
def fetch_products_by_country(country_code, page_size=5):
    import time
    
    # Configure the API
    api = openfoodfacts.API("food_dashboard", country=country_code)
    
    try:
        # Initial search to get total number of pages
        search_result = api.product.text_search(query="food", page_size=page_size, page=1)
        
        all_products = []
        total_pages = search_result.get('page_count', 1)  # Limit to first 5 pages to avoid rate limits
        
        # Create a placeholder for the progress message
        progress_placeholder = st.empty()
        
        # Collect products from all pages
        for page in range(1, total_pages + 1):
            try:
                if page > 1:  # Skip first page since we already have it
                    progress_placeholder.info(f"Fetching page {page} of {total_pages}...")
                    time.sleep(7)  # Add 7 second delay between requests (< 10 requests/minute)
                    search_result = api.product.text_search(query="food", page_size=page_size, page=page)
                
                current_products = search_result.get('products', [])
                all_products.extend(current_products)
                
            except Exception as e:
                st.warning(f"Error fetching page {page}: {str(e)}")
                break
        
        # Clear the progress message when done
        progress_placeholder.empty()
        
        if not all_products:
            st.error("No products found. Please try again later.")
            return []
            
        return all_products
        
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return []

# Country selection
countries = {}
for key, val in COUNTRY_CODE_TO_NAME.items():
    new_key = val.replace('en:', '').replace('-', ' ').capitalize()
    countries[new_key] = key

options = sorted(list(countries.keys()))
def_option = 'India'
selected_country = st.selectbox("Select a Country", options, index=options.index(def_option))

# Add a button to trigger data fetching
products = []  # Initialize products list
if st.button("Fetch Data"):
    # Fetch data
    with st.spinner('Fetching data from OpenFoodFacts...'):
        products = fetch_products_by_country(countries[selected_country])

# Create two columns for the layout
col1, col2 = st.columns(2)

# 1. NutriScore Distribution
with col1:
    st.subheader("NutriScore Distribution")
    nutri_scores = [p.get('nutriscore_grade','X') for p in products]
    nutri_score_counts = Counter(nutri_scores)
    
    # Sort the scores in ascending order (A to E, with X at the end)
    sorted_scores = sorted(nutri_score_counts.items(), key=lambda x: ('X' if x[0] == 'X' else x[0]))
    
    fig1 = go.Figure(data=[
        go.Bar(
            x=[score[0] for score in sorted_scores],
            y=[score[1] for score in sorted_scores],
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
    brands = [item for sublist in products for item in sublist.get('brands', '').split(',')]
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
    categories.extend([cat.replace('en:', '') for proddict in products for cat in proddict.get('categories_tags', '')])
    top_categories = Counter(categories).most_common(5)
    
    fig3 = go.Figure(data=[
        go.Bar(
            x=[cat[1] for cat in top_categories],
            y=[cat[0] for cat in top_categories],
            orientation='h',
            marker_color=['#2ecc71', '#3498db', '#e74c3c', '#f1c40f', '#9b59b6']  # Green, Blue, Red, Yellow, Purple
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
    ingredients.extend([ing.replace('en:', '') for proddict in products for ing in proddict.get('ingredients_tags', '')])
    top_ingredients = Counter(ingredients).most_common(5)
    
    fig4 = go.Figure(data=[
        go.Bar(
            x=[ing[1] for ing in top_ingredients],
            y=[ing[0] for ing in top_ingredients],
            orientation='h',
            marker_color=['#e67e22', '#16a085', '#8e44ad', '#d35400', '#27ae60']  # Orange, Turquoise, Purple, Dark Orange, Dark Green
        )
    ])
    fig4.update_layout(
        title_text="Top 5 Ingredients",
        xaxis_title="Frequency",
        yaxis_title="Ingredient",
        template="plotly_white"
    )
    st.plotly_chart(fig4, use_container_width=True)
