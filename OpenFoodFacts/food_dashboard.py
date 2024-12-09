import streamlit as st
import plotly.graph_objects as go
from collections import Counter
import openfoodfacts
from openfoodfacts.types import Country, COUNTRY_CODE_TO_NAME
from openfoodfacts import ProductDataset
import json
from datetime import datetime
import os
from supabase import create_client
from dotenv import load_dotenv
import gzip
import io
import pandas as pd
import requests
from tqdm import tqdm
import tempfile
from pathlib import Path

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

# For Streamlit Cloud, use secrets
if not supabase_url or not supabase_key:
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]

supabase = create_client(supabase_url, supabase_key)

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
st.markdown("""
    <style>
    .title-container {
        background: linear-gradient(to right, #1f77b4, #2ecc71);
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
    }
    .title-text {
        color: white;
        text-align: center;
        font-size: 3rem;
        font-weight: bold;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
    }
    </style>
    <div class="title-container">
        <h1 class="title-text">Food Products Analytics Dashboard</h1>
    </div>
    """, unsafe_allow_html=True)

# Information section
about_text = """
## About this Dashboard

### Data Sources and Performance
This Open Food Facts dashboard provides comprehensive insights into food products across different countries.:

    - 📊 Analyze food products by country
    - 🏷️ View NutriScore distribution
    - 🏢 Explore top brands and categories
    - 🥗 Discover common ingredients

1. **Load Saved Data**: 
   - Instantly access previously saved analysis results
   - Ideal for quick revisits of past insights
   - Minimal loading time

2. **Get data from compressed CSV Database (recommended)**: 
   - Balanced approach for data retrieval
   - Compressed format ensures efficient data transfer
   - Recommended for most use cases
   - Moderate loading time with comprehensive data

3. **Get Data from API Endpoint Search (slow)**: 
   - Direct real-time data retrieval from Open Food Facts API
   - Most up-to-date information
   - Slower performance due to individual API calls and rate limits
   - Under Development: Get food statistics based on keywords entered

4. **Get data from Parquet Database (experimental)**: 
   - Cutting-edge data retrieval using Apache Parquet format
   - Designed for high-performance data processing
   - Experimental feature with potential for faster large dataset handling
   - May have limitations in current implementation

### Technical Details
- **Data Source**: Open Food Facts Global Product Database
- **Update Frequency**: Regularly updated from global crowdsourced data
- **Technologies**: Streamlit, Pandas, PyArrow, Supabase

### Privacy and Transparency
All data is sourced from the Open Food Facts public database. Personal information is never collected or stored.
"""

with st.expander("ℹ️ About this Dashboard"):
    st.markdown(about_text)

# Function to fetch data using OpenFoodFacts API
def fetch_products_by_country(country_code, page_size=100):
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

def is_gzip_file(filepath):
    """Check if file is gzip compressed"""
    with open(filepath, 'rb') as f:
        return f.read(2) == b'\x1f\x8b'

def fetch_products_from_csv(country_code):
    """Fetch products for a specific country from CSV dump"""
    try:
        with st.spinner('Loading CSV dump... This might take a few minutes...'):
            # Get dataset path but don't open it yet
            dataset = ProductDataset(dataset_type="csv")
            dataset_path = dataset.dataset_path
            
            # Create a progress bar
            progress_bar = st.progress(0)
            products = []
            matching_products = 0
            
            # Create a temporary file path
            temp_file_path = os.path.join(os.path.dirname(dataset_path), f'temp_{country_code}.csv')
            
            try:
                country_tag = f'en:{country_code}'
                
                # First get the header
                with gzip.open(dataset_path, 'rt', encoding='utf-8', errors='replace') as f:
                    header = next(f).strip()
                
                # Process file and extract matching lines
                with open(temp_file_path, 'w', encoding='utf-8') as temp_file:
                    temp_file.write(header + '\n')
                    
                    with gzip.open(dataset_path, 'rt', encoding='utf-8', errors='replace') as f:
                        next(f)  # Skip header
                        for line in f:
                            if country_tag.lower() in line:
                                temp_file.write(line)
                                matching_products += 1
                                if matching_products % 100 == 0:
                                    progress_bar.progress(0, f"Found {matching_products} products...")
                
                if matching_products == 0:
                    st.warning(f"No products found for {country_code} in the CSV dump")
                    return []
                
                # Now process the filtered file
                st.info(f"Processing {matching_products} products...")
                progress_bar.progress(0, "Parsing products...")
                
                # Read and parse the filtered data
                with open(temp_file_path, 'r', encoding='utf-8') as f:
                    header = next(f).strip().split('\t')
                    
                    for i, line in enumerate(f):
                        try:
                            # Parse CSV line
                            values = line.strip().split('\t')
                            product = dict(zip(header, values))
                            
                            # Double check if product is from selected country
                            if product.get('countries_tags') and country_tag.lower() in product['countries_tags']:
                                products.append(product)
                                
                                # Update progress every 100 products
                                if len(products) % 100 == 0:
                                    progress = int((i + 1) * 100 / matching_products)
                                    progress_bar.progress(progress, f"Parsed {len(products)} products")
                        except Exception as line_error:
                            continue
                
                progress_bar.empty()
                
                if products:
                    st.success(f"Successfully loaded {len(products)} products from {country_code}")
                    return products
                else:
                    st.warning(f"No valid products found for {country_code} in the CSV dump")
                    return []
            
            except Exception as e:
                st.error(f"Error processing CSV dump: {str(e)}")
                return []
            
            finally:
                # Clean up temp file
                try:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                except:
                    pass
                    
    except Exception as e:
        st.error(f"Error loading CSV dump: {str(e)}")
        return []

def fetch_products_from_parquet(country_code):
    """Fetch products for a specific country from Parquet file using efficient batch processing"""
    try:
        import pyarrow.dataset as ds
        import pyarrow.parquet as pq
        import pandas as pd
        import fsspec

        # Create progress indicator
        progress_text = st.empty()
        progress_text.text("Loading data from remote parquet file...")
        
        parquet_url = "https://huggingface.co/datasets/openfoodfacts/product-database/resolve/main/food.parquet"
        
        # Define needed columns for efficient reading
        needed_columns = [
            'countries_tags',
            'nutriscore_grade',
            'brands',
            'categories_tags',
            'ingredients_tags'
        ]
        
        # Create a remote filesystem
        fs = fsspec.filesystem('http')
        
        # Create dataset with remote file system
        dataset = ds.dataset(
            parquet_url,
            format='parquet',
            filesystem=fs
        )
        
        # Prepare country tag
        country_tag = f'en:{country_code.lower()}'
        
        # Initialize products list
        products = []
        total_processed = 0
        
        # Process data in batches
        for batch in dataset.to_batches(
            columns=needed_columns, 
            use_threads=True, 
            batch_size=100_000  # Adjust batch size as needed
        ):
            # Convert batch to pandas DataFrame
            df_batch = batch.to_pandas()
            
            # Filter for country
            country_mask = df_batch['countries_tags'].apply(
                lambda x: country_tag in x if isinstance(x, list) else False
            )
            filtered_batch = df_batch[country_mask]
            
            # Extend products list
            products.extend(filtered_batch.to_dict('records'))
            
            # Update progress
            total_processed += len(df_batch)
            progress_text.text(f"Processed {total_processed} records, found {len(products)} matching products...")
            
            # Optional: Break if you want to limit total products
            # if len(products) >= 10000:
            #     break
        
        if len(products) == 0:
            st.warning(f"No products found for {country_code} in the Parquet file")
            return []
        
        # Clear progress indicator
        progress_text.empty()
        
        st.success(f"Successfully loaded {len(products)} products from {country_code}")
        return products
        
    except Exception as e:
        st.error(f"Error loading Parquet file: {str(e)}")
        return []

def save_data(products, country, timestamp):
    """Save the aggregated graph data to Supabase"""
    try:
        # 1. Calculate NutriScore Distribution
        nutri_scores = [p.get('nutriscore_grade', 'unknown').upper() for p in products if p.get('nutriscore_grade')]
        nutri_score_counts = dict(Counter(nutri_scores))
        
        # 2. Calculate Top 5 Brands
        brands = [item for p in products for item in p.get('brands', '').split(',') if item]
        top_brands = Counter(brands).most_common(5)
        
        # 3. Calculate Top 5 Categories
        categories = [cat.replace('en:', '') for p in products for cat in p.get('categories_tags', '').split(",") if cat]
        top_categories = Counter(categories).most_common(5)
        
        # 4. Calculate Top 5 Ingredients
        ingredients = [ing.replace('en:', '') for p in products for ing in p.get('ingredients_tags', '').split(",") if ing]
        top_ingredients = Counter(ingredients).most_common(5)
        
        # Create display name
        display_name = f"{country} ({len(products)} products) - {timestamp.strftime('%Y-%m-%d %H:%M')}"
        
        # Prepare data for storage
        data = {
            'country': country,
            'timestamp': timestamp.isoformat(),
            'display_name': display_name,
            'total_products': len(products),
            'graph_data': json.dumps({
                'nutriscore_distribution': nutri_score_counts,
                'top_brands': top_brands,
                'top_categories': top_categories,
                'top_ingredients': top_ingredients
            }, separators=(',', ':'))
        }
        
        # Insert data into Supabase
        result = supabase.table('food_data').insert(data).execute()
        
        if hasattr(result, 'error') and result.error is not None:
            raise Exception(f"Supabase error: {result.error}")
            
        st.success("✅ Data saved successfully!")
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

def load_saved_data():
    """Load saved graph data from Supabase"""
    try:
        # Fetch all saved data entries
        result = supabase.table('food_data').select('*').order('timestamp', desc=True).execute()
        
        if not result.data:
            st.warning("No saved data found.")
            return None, None, None
        
        # Create selection options
        options = [entry['display_name'] for entry in result.data]
        
        # Create columns for selection and delete button
        col1, col2 = st.columns([4, 1])
        
        with col1:
            selected_option = st.selectbox("Select saved data to load:", options)
        
        with col2:
            st.write("")  # Add some spacing
            st.write("")  # Add some spacing
            if st.button("🗑️ Delete", key="delete_btn"):
                if delete_saved_data(selected_option):
                    st.success(f"Deleted: {selected_option}")
                    st.rerun()  # Refresh the page
                    return None, None, None
        
        # Find the selected entry
        selected_entry = next(entry for entry in result.data if entry['display_name'] == selected_option)
        
        # Parse the timestamp
        try:
            timestamp_str = selected_entry['timestamp'].split('+')[0]  # Remove timezone part
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S')
        except Exception:
            timestamp = datetime.now()
        
        # Parse the graph data
        graph_data = json.loads(selected_entry['graph_data'])
        
        # Create two columns for the layout
        col1, col2 = st.columns(2)
        
        # 1. NutriScore Distribution
        with col1:
            st.subheader("NutriScore Distribution")
            nutri_score_counts = graph_data['nutriscore_distribution']
            
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
            top_brands = graph_data['top_brands']
            
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
            top_categories = graph_data['top_categories']
            
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
            top_ingredients = graph_data['top_ingredients']
            
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
        
        # Return minimal data structure for compatibility
        return [], selected_entry['country'], timestamp
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None, None

def delete_saved_data(display_name):
    """Delete a saved data entry from Supabase"""
    try:
        result = supabase.table('food_data').delete().eq('display_name', display_name).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting data: {str(e)}")
        return False

# Initialize session state for products if not exists
if 'products' not in st.session_state:
    st.session_state.products = None

# Mode selection
mode = st.radio(
    "Select Mode", 
    [
        "Load Saved Data",
        "Get data from compressed CSV Database (recommended)",
        "Get Data from API Endpoint Search (slow)",
        "Get data from Parquet Database (experimental)"
    ]
)

if mode == "Load Saved Data":
    # Load saved data
    loaded_products, loaded_country, loaded_timestamp = load_saved_data()
    if loaded_products:
        st.session_state.products = loaded_products
        products = loaded_products
    else:
        st.session_state.products = None
        products = None
else:
    # Country selection
    countries = {}
    for key, val in COUNTRY_CODE_TO_NAME.items():
        new_key = val.replace('en:', '').replace('-', ' ').capitalize()
        countries[new_key] = key

    options = sorted(list(countries.keys()))
    def_option = "India"
    
    if mode == "Get Data from API Endpoint Search (slow)":
        selected_country_name = st.selectbox("Select a Country", options, index=options.index(def_option))
        fetch_col1, fetch_col2 = st.columns([4, 1])
        
        with fetch_col1:
            if st.button("Fetch Data"):
                # Fetch data
                with st.spinner('Fetching data from OpenFoodFacts...'):
                    products = fetch_products_by_country(countries[selected_country_name])
                    if products:
                        st.session_state.products = products
        
        # Only show save button if we have products
        if st.session_state.products:
            with fetch_col2:
                if st.button("💾 Save Data"):
                    timestamp = datetime.now()
                    save_data(st.session_state.products, selected_country_name, timestamp)
    
    elif mode == "Get data from compressed CSV Database (.gz)":
        selected_country_name = st.selectbox("Select a Country", options, index=options.index(def_option))
        fetch_col1, fetch_col2 = st.columns([4, 1])
        
        with fetch_col1:
            if st.button("Load from CSV"):
                products = fetch_products_from_csv(selected_country_name)
                if products:
                    st.session_state.products = products
        
        # Only show save button if we have products
        if st.session_state.products:
            with fetch_col2:
                if st.button("💾 Save Data"):
                    timestamp = datetime.now()
                    save_data(st.session_state.products, selected_country_name, timestamp)
    
    elif mode == "Get data from Parquet Database (fast)":
        selected_country_name = st.selectbox("Select a Country", options, index=options.index(def_option))
        fetch_col1, fetch_col2 = st.columns([4, 1])
        
        with fetch_col1:
            if st.button("Load from Parquet"):
                products = fetch_products_from_parquet(selected_country_name)
                if products:
                    st.session_state.products = products
        
        # Only show save button if we have products
        if st.session_state.products:
            with fetch_col2:
                if st.button("💾 Save Data"):
                    timestamp = datetime.now()
                    save_data(st.session_state.products, selected_country_name, timestamp)

# Only show visualizations if we have products
if st.session_state.products:
    products = st.session_state.products
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
        brands = [item for sublist in products for item in sublist.get('brands', '').split(',') if item]
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
        categories.extend([cat.replace('en:', '') for proddict in products for cat in proddict.get('categories_tags', '').split(",") if cat])
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
        ingredients = [ing.replace('en:', '') for proddict in products for ing in proddict.get('ingredients_tags', '').split(",") if ing]
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
