import streamlit as st
import asyncio
from datetime import datetime
import pandas as pd
import numpy as np
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
from httpx import AsyncClient

# Import our scraping function
from scrape_hotel_link import scrape_hotels, HEADERS, parse_hotel_prices

st.set_page_config(page_title="Hotel Price Analyzer", layout="wide")
st.title("Booking.com Hotel Price Analyzer")

# Initialize session state for hotel URLs
if 'hotel_urls' not in st.session_state:
    st.session_state.hotel_urls = []
if 'all_hotel_data' not in st.session_state:
    st.session_state.all_hotel_data = []

# Function to add a hotel URL to the list
def add_hotel_url():
    if st.session_state.new_hotel_url and st.session_state.new_hotel_url not in st.session_state.hotel_urls:
        st.session_state.hotel_urls.append(st.session_state.new_hotel_url)
        st.session_state.new_hotel_url = ""

# Function to remove a hotel URL from the list
def remove_hotel_url(url_to_remove):
    st.session_state.hotel_urls.remove(url_to_remove)
    # Also remove from all_hotel_data if present
    st.session_state.all_hotel_data = [h for h in st.session_state.all_hotel_data if h['url'] != url_to_remove]

# Function to clear all hotels
def clear_all_hotels():
    st.session_state.hotel_urls = []
    st.session_state.all_hotel_data = []

# Function to load predefined Barcelona hostals and hotels
def load_barcelona_hostals():
    barcelona_hostals = [
        "https://www.booking.com/hotel/es/hostal-ramos.es.html",
        "https://www.booking.com/hotel/es/hostal-santa-ana.es.html",
        "https://www.booking.com/hotel/es/hostal-europa.es.html",
        "https://www.booking.com/hotel/es/hostal-levante-barcelona.es.html",
        "https://www.booking.com/hotel/es/hostal-nuevo-colon.es.html",
        "https://www.booking.com/hotel/es/hostal-benidorm.es.html",
        "https://www.booking.com/hotel/es/hostal-fina.es.html",
        "https://www.booking.com/hotel/es/hostal-paris.es.html",
        "https://www.booking.com/hotel/es/pension-iznajar-barcelona.es.html",
        "https://www.booking.com/hotel/es/lloret.es.html",
        "https://www.booking.com/hotel/es/hostal-lausanne.es.html",
        "https://www.booking.com/hotel/es/hostal-hera.es.html",
        "https://www.booking.com/hotel/es/hostal-marenostrum.es.html",
        "https://www.booking.com/hotel/es/lyon.es.html",
        "https://www.booking.com/hotel/es/pension-45.es.html",
        "https://www.booking.com/hotel/es/hostal-capitol-ramblas.es.html"
    ]
    
    # Clear existing and add new ones
    st.session_state.hotel_urls = []
    st.session_state.all_hotel_data = []
    
    for url in barcelona_hostals:
        if url not in st.session_state.hotel_urls:
            st.session_state.hotel_urls.append(url)

# Main sidebar for inputs
with st.sidebar:
    st.header("Hotel Selection")
    
    # Text input for adding a new hotel URL
    st.text_input("Enter Booking.com Hotel URL", key="new_hotel_url", 
                  placeholder="https://www.booking.com/hotel/...")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("Add Hotel", on_click=add_hotel_url)
    with col2:
        st.button("Clear All", on_click=clear_all_hotels)
    
    # Add a button to load the predefined Barcelona hostals
    st.button("🏨 Load Barcelona Hostals", on_click=load_barcelona_hostals, type="primary")
    
    # Add note about error handling
    st.info("📝 Note: URLs with connection issues will be automatically skipped.")
    
    # Show list of added hotels with remove buttons
    for i, url in enumerate(st.session_state.hotel_urls):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.text(f"Hotel {i+1}: {url[:30]}...")
        with col2:
            st.button("❌", key=f"remove_{i}", on_click=remove_hotel_url, args=(url,))
    
    st.divider()
    
    # Date range inputs
    st.header("Date Range")
    start_date = st.date_input(
        "Start Date",
        value=datetime.now().date()
    )
    
    days_to_check = st.number_input(
        "Number of Days to Check",
        min_value=1,
        max_value=90,
        value=30
    )
    
    num_adults = st.number_input(
        "Number of Adults",
        min_value=1,
        max_value=10,
        value=2
    )
    
    # Scrape button
    scrape_button = st.button("Scrape All Hotels", disabled=len(st.session_state.hotel_urls) == 0)

# Main content area with tabs
tab1, tab2, tab3 = st.tabs(["Hotel Comparison", "Price Analytics", "Individual Hotels"])

# Function to process all hotels
async def process_all_hotels(hotel_urls, start_date, days_to_check, num_adults):
    async with AsyncClient(headers=HEADERS) as session:
        hotels = await scrape_hotels(
            hotel_urls,
            session,
            start_date.strftime("%Y-%m-%d"),
            days_to_check,
            num_adults
        )
        return hotels

# Handle scraping when the button is clicked
if scrape_button and st.session_state.hotel_urls:
    with st.spinner("Scraping prices from all hotels... This may take a moment."):
        try:
            # Run the async function to scrape all hotels
            all_hotel_data = asyncio.run(process_all_hotels(
                st.session_state.hotel_urls,
                start_date,
                days_to_check,
                num_adults
            ))
            
            # Save to session state
            st.session_state.all_hotel_data = all_hotel_data
            
            # Show success message
            st.success(f"Successfully scraped data from {len(all_hotel_data)} hotels!")
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please check if all URLs are valid and try again.")

# Function to create a combined dataframe with all hotel prices
def create_combined_price_df(all_hotel_data):
    if not all_hotel_data:
        return None
    
    all_prices = []
    error_hotels = []
    
    for hotel in all_hotel_data:
        # Check for errors
        if 'error' in hotel:
            error_hotels.append({
                'name': hotel.get('name', 'Unknown Hotel'),
                'url': hotel.get('url', 'Unknown URL'),
                'error': hotel.get('error', 'Unknown error')
            })
            continue
            
        if 'price' in hotel and hotel['price']:
            price_df = parse_hotel_prices(hotel['price'])
            if not price_df.empty:
                # Add hotel name
                hotel_name = hotel.get('name', 'Unknown Hotel')
                price_df['Hotel'] = hotel_name
                all_prices.append(price_df)
        elif 'price_error' in hotel:
            error_hotels.append({
                'name': hotel.get('name', 'Unknown Hotel'),
                'url': hotel.get('url', 'Unknown URL'),
                'error': hotel.get('price_error', 'Unknown price error')
            })
    
    # Display info about problematic URLs if any
    if error_hotels:
        st.warning(f"{len(error_hotels)} hotels had issues and were ignored:")
        for err_hotel in error_hotels:
            st.warning(f"⚠️ {err_hotel['name']}: {err_hotel['error']}")
    
    if not all_prices:
        return None
    
    # Combine all dataframes
    combined_df = pd.concat(all_prices, ignore_index=True)
    return combined_df

# Hotel Comparison Tab
with tab1:
    if st.session_state.all_hotel_data:
        st.header("Hotel Price Comparison")
        
        # Create combined dataframe
        combined_df = create_combined_price_df(st.session_state.all_hotel_data)
        
        if combined_df is not None:
            # Display filter options
            st.subheader("Filter Options")
            
            col1, col2 = st.columns(2)
            with col1:
                selected_hotels = st.multiselect(
                    "Select Hotels to Compare",
                    options=combined_df['Hotel'].unique(),
                    default=combined_df['Hotel'].unique()
                )
            
            with col2:
                only_available = st.checkbox("Show Only Available Dates", value=True)
            
            # Filter the data
            filtered_df = combined_df[combined_df['Hotel'].isin(selected_hotels)]
            if only_available:
                filtered_df = filtered_df[filtered_df['Available'] == True]
            
            if not filtered_df.empty:
                # Line chart for price comparison
                st.subheader("Price Comparison Across Hotels")
                
                chart = alt.Chart(filtered_df).mark_line(point=True).encode(
                    x='Date:T',
                    y='Price Value:Q',
                    color='Hotel:N',
                    tooltip=['Hotel', 'Date', 'Price', 'Price Value', 'Available']
                ).properties(height=400)
                
                st.altair_chart(chart, use_container_width=True)
                
                # Table with price comparison
                st.subheader("Price Comparison Table")
                
                # Pivot table to show all hotels side by side
                pivot_df = filtered_df.pivot_table(
                    index='Date', 
                    columns='Hotel',
                    values='Price Value',
                    aggfunc='first'
                ).reset_index()
                
                # Add price difference column if there are exactly 2 hotels
                if len(selected_hotels) == 2:
                    hotel1, hotel2 = selected_hotels
                    pivot_df['Price Difference'] = pivot_df[hotel1] - pivot_df[hotel2]
                
                st.dataframe(pivot_df, use_container_width=True)
                
                # Add download button for CSV
                csv = pivot_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download comparison as CSV",
                    csv,
                    "hotel_price_comparison.csv",
                    "text/csv",
                    key="download-comparison-csv"
                )
            else:
                st.warning("No data available for the selected filters.")
        else:
            st.warning("No price data available for comparison.")
    else:
        st.info("Add hotels and click 'Scrape All Hotels' to see comparison data.")

# Price Analytics Tab
with tab2:
    if st.session_state.all_hotel_data:
        st.header("Price Analytics")
        
        # Create combined dataframe
        combined_df = create_combined_price_df(st.session_state.all_hotel_data)
        
        if combined_df is not None:
            # Only use available dates
            available_df = combined_df[combined_df['Available'] == True]
            
            if not available_df.empty:
                # Daily average prices across all hotels
                st.subheader("Daily Average Prices")
                
                daily_avg = available_df.groupby('Date')['Price Value'].agg(['mean', 'min', 'max', 'count']).reset_index()
                daily_avg.columns = ['Date', 'Average Price', 'Min Price', 'Max Price', 'Number of Hotels']
                
                # Create a multi-line chart
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=daily_avg['Date'], y=daily_avg['Average Price'], 
                                         mode='lines+markers', name='Average Price'))
                fig.add_trace(go.Scatter(x=daily_avg['Date'], y=daily_avg['Min Price'], 
                                         mode='lines', name='Min Price'))
                fig.add_trace(go.Scatter(x=daily_avg['Date'], y=daily_avg['Max Price'], 
                                         mode='lines', name='Max Price'))
                
                fig.update_layout(
                    title='Price Trends Over Time',
                    xaxis_title='Date',
                    yaxis_title='Price',
                    legend_title='Price Type',
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Price distribution by hotel
                st.subheader("Price Distribution by Hotel")
                
                fig = px.box(available_df, x='Hotel', y='Price Value', 
                             title='Price Distribution by Hotel', height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                # Price heatmap calendar
                st.subheader("Price Heatmap Calendar")
                
                # Get the hotel with the most data points for the heatmap
                if 'hotel_for_heatmap' not in st.session_state or \
                   st.session_state.hotel_for_heatmap not in available_df['Hotel'].unique():
                    st.session_state.hotel_for_heatmap = available_df['Hotel'].value_counts().index[0]
                
                selected_hotel = st.selectbox(
                    "Select Hotel for Heatmap",
                    options=available_df['Hotel'].unique(),
                    index=list(available_df['Hotel'].unique()).index(st.session_state.hotel_for_heatmap)
                )
                
                # Update session state
                st.session_state.hotel_for_heatmap = selected_hotel
                
                # Filter data for selected hotel
                hotel_df = available_df[available_df['Hotel'] == selected_hotel]
                
                # Create heatmap data
                date_objects = pd.to_datetime(hotel_df['Date'])
                hotel_df['Day'] = date_objects.dt.day_name()
                hotel_df['Week'] = date_objects.dt.isocalendar().week
                
                # Pivot for heatmap
                heatmap_df = hotel_df.pivot_table(
                    index='Week', 
                    columns='Day',
                    values='Price Value',
                    aggfunc='mean'
                )
                
                # Reorder days
                days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                heatmap_df = heatmap_df.reindex(columns=days_order)
                
                # Create heatmap
                fig = px.imshow(
                    heatmap_df,
                    labels=dict(x="Day of Week", y="Week", color="Price"),
                    x=heatmap_df.columns,
                    y=heatmap_df.index,
                    color_continuous_scale=px.colors.sequential.Viridis,
                    title=f"Price Heatmap for {selected_hotel}"
                )
                
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                # Statistical summary
                st.subheader("Statistical Summary")
                
                # Prepare stats by hotel
                stats_by_hotel = available_df.groupby('Hotel')['Price Value'].describe().reset_index()
                stats_by_hotel = stats_by_hotel.round(2)
                
                st.dataframe(stats_by_hotel, use_container_width=True)
                
                # Best day to book
                st.subheader("Best Day to Book")
                
                # Calculate average price by day of week
                available_df['Weekday'] = pd.to_datetime(available_df['Date']).dt.day_name()
                day_avg = available_df.groupby(['Hotel', 'Weekday'])['Price Value'].mean().reset_index()
                
                # Pivot for easier viewing
                day_pivot = day_avg.pivot(index='Weekday', columns='Hotel', values='Price Value')
                
                # Reorder days
                day_pivot = day_pivot.reindex(days_order)
                
                # Add overall average
                day_pivot['Average'] = day_pivot.mean(axis=1)
                
                # Format to 2 decimal places
                day_pivot = day_pivot.round(2)
                
                st.dataframe(day_pivot, use_container_width=True)
                
                # Identify the best day to book (lowest average price)
                best_day = day_pivot['Average'].idxmin()
                best_price = day_pivot['Average'].min()
                
                st.info(f"📊 Overall, {best_day} appears to be the cheapest day with an average price of {best_price:.2f}")
                
                # Download buttons for analytics data
                col1, col2 = st.columns(2)
                with col1:
                    csv = daily_avg.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "Download daily averages as CSV",
                        csv,
                        "daily_avg_prices.csv",
                        "text/csv",
                        key="download-daily-avg-csv"
                    )
                
                with col2:
                    csv = day_pivot.to_csv().encode('utf-8')
                    st.download_button(
                        "Download day of week analysis as CSV",
                        csv,
                        "day_of_week_prices.csv",
                        "text/csv",
                        key="download-dow-csv"
                    )
                
            else:
                st.warning("No available dates found in the selected period.")
        else:
            st.warning("No price data available for analysis.")
    else:
        st.info("Add hotels and click 'Scrape All Hotels' to see price analytics.")

# Individual Hotels Tab
with tab3:
    if st.session_state.all_hotel_data:
        st.header("Individual Hotel Details")
        
        # Create a selectbox for choosing a hotel
        hotel_names = [h.get('name', f"Hotel {i+1}") for i, h in enumerate(st.session_state.all_hotel_data)]
        selected_index = st.selectbox("Select Hotel", range(len(hotel_names)), format_func=lambda i: hotel_names[i])
        
        # Get the selected hotel data
        hotel_data = st.session_state.all_hotel_data[selected_index]
        
        # Display hotel information
        if 'name' in hotel_data:
            st.subheader(hotel_data['name'])
        st.markdown(f"[View on Booking.com]({hotel_data['url']})")
        
        # Parse and display price data
        if 'price' in hotel_data and hotel_data['price']:
            price_df = parse_hotel_prices(hotel_data['price'])
            
            if not price_df.empty:
                # Price information card
                st.subheader("Price Information")
                
                # Calculate price statistics
                available_prices = price_df[price_df['Available'] == True]['Price Value']
                if len(available_prices) > 0:
                    min_price = available_prices.min()
                    max_price = available_prices.max()
                    avg_price = available_prices.mean()
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Minimum Price", f"{min_price:.2f}")
                    with col2:
                        st.metric("Average Price", f"{avg_price:.2f}")
                    with col3:
                        st.metric("Maximum Price", f"{max_price:.2f}")
                
                # Display as table
                st.subheader("Daily Prices")
                st.dataframe(price_df, use_container_width=True)
                
                # Create interactive price chart without trendline
                st.subheader("Price Trend")
                
                available_df = price_df[price_df['Available'] == True].copy()
                if not available_df.empty:
                    # Create a line chart without the trendline
                    fig = px.line(available_df, x='Date', y='Price Value', 
                                   title='Price Trend Over Time',
                                   markers=True, line_shape='linear')
                    
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Weekend vs. Weekday Analysis
                    st.subheader("Weekend vs. Weekday Analysis")
                    
                    # Add day of week
                    available_df['Weekday'] = pd.to_datetime(available_df['Date']).dt.day_name()
                    available_df['is_weekend'] = available_df['Weekday'].isin(['Saturday', 'Sunday'])
                    
                    # Group by weekend/weekday
                    weekend_analysis = available_df.groupby('is_weekend')['Price Value'].agg(['mean', 'min', 'max', 'count'])
                    weekend_analysis.index = ['Weekday', 'Weekend']
                    weekend_analysis.columns = ['Average Price', 'Min Price', 'Max Price', 'Number of Days']
                    weekend_analysis = weekend_analysis.round(2)
                    
                    st.dataframe(weekend_analysis, use_container_width=True)
                    
                    # Visualize weekend vs weekday
                    fig = px.bar(
                        weekend_analysis.reset_index(), 
                        x='index', 
                        y='Average Price',
                        color='index',
                        text_auto=True,
                        title='Average Price: Weekend vs. Weekday',
                        labels={'index': 'Day Type', 'Average Price': 'Price'}
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Add download button for CSV
                    csv = price_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "Download hotel prices as CSV",
                        csv,
                        f"{hotel_data.get('name', 'hotel')}_prices.csv",
                        "text/csv",
                        key=f"download-{selected_index}"
                    )
                else:
                    st.warning("No available dates found for the selected period.")
            else:
                st.warning("No price data found for this hotel.")
        else:
            st.warning("No price data found for this hotel.")
        
        # Show hotel details in an expander
        with st.expander("Hotel Details"):
            hotel_info = {k: v for k, v in hotel_data.items() if k != 'price'}
            st.json(hotel_info)
    else:
        st.info("Add hotels and click 'Scrape All Hotels' to see individual hotel details.")

# Add instructions
with st.sidebar:
    with st.expander("How to use this app"):
        st.write("""
        ### Basic Usage:
        1. Enter Booking.com hotel URLs in the sidebar
        2. Click "Add Hotel" for each URL
        3. Select a start date and number of days
        4. Click "Scrape All Hotels"
        5. Explore the comparison, analytics, and individual hotel tabs
        
        ### Tips:
        - You can compare multiple hotels side by side
        - The Price Analytics tab provides trends and statistical analysis
        - For detailed information on a specific hotel, use the Individual Hotels tab
        - You can download data as CSV files for further analysis
        
        Note: This app is for educational purposes only. Please respect Booking.com's terms of service.
        """) 