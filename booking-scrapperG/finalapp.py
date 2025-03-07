import streamlit as st
import pandas as pd
import json
import asyncio
from datetime import datetime, timedelta
import re
from httpx import AsyncClient
import numpy as np
import altair as alt
import os
import logging
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("hostel_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("hostel_scraper")

# Set page configuration
st.set_page_config(
    page_title="Barcelona Hostel Analysis",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
}

# Debug mode toggle
def toggle_debug_mode():
    st.session_state.debug_mode = not st.session_state.get('debug_mode', False)
    if st.session_state.debug_mode:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    else:
        logger.setLevel(logging.INFO)
        logger.info("Debug mode disabled")

# Initialize session state
if "hostel_data" not in st.session_state:
    st.session_state.hostel_data = []

if "scraping_results" not in st.session_state:
    st.session_state.scraping_results = []

if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = False

# Function to load hostel data from JSON
def load_hostel_data(file_path='Hotels Predifined.json'):
    try:
        logger.info(f"Attempting to load hostel data from: {file_path}")
        st.info(f"Attempting to load from: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract hostels from the data and convert 'link' property to 'url'
        hostels = data.get('hostels', [])
        if not hostels:
            logger.warning("No hostels found in the JSON file or invalid format.")
            st.warning("No hostels found in the JSON file or invalid format.")
            return []
            
        # Make sure every hostel has a URL property
        for hostel in hostels:
            if 'link' in hostel and 'url' not in hostel:
                hostel['url'] = hostel['link']
            
            # Verify essential data
            if not hostel.get('url') and not hostel.get('link'):
                logger.warning(f"Missing URL for hostel: {hostel.get('name', 'Unknown')}")
                st.warning(f"Missing URL for hostel: {hostel.get('name', 'Unknown')}")
                
        logger.info(f"Successfully loaded {len(hostels)} hostels from JSON file.")
        st.success(f"Successfully loaded {len(hostels)} hostels from JSON file.")
        return hostels
    except FileNotFoundError:
        logger.error(f"Error: File '{file_path}' not found. Please check that the file exists.")
        st.error(f"Error: File '{file_path}' not found. Please check that the file exists.")
        # Try alternative filenames
        alternatives = ['hotels predefined.json', 'hotels_predefined.json', 'Hotels Predefined.json']
        for alt_path in alternatives:
            if alt_path != file_path and os.path.exists(alt_path):
                logger.info(f"Found alternative file: {alt_path}. Try changing the filename parameter.")
                st.info(f"Found alternative file: {alt_path}. Try changing the filename parameter.")
        return []
    except json.JSONDecodeError:
        logger.error(f"Error: '{file_path}' is not a valid JSON file.")
        st.error(f"Error: '{file_path}' is not a valid JSON file.")
        return []
    except Exception as e:
        logger.error(f"Error loading hostel data: {str(e)}", exc_info=True)
        st.error(f"Error loading hostel data: {str(e)}")
        return []

# Parse hotel HTML to extract name
def parse_hotel(html):
    # Extract the hotel name using regex
    hotel_name_match = re.search(r'hotelName:\s*"(.+?)"', html)
    if hotel_name_match:
        hotel_name = hotel_name_match.group(1)
    else:
        # Try alternative pattern that might be in the URL
        url_match = re.search(r'hotel/\w+/([^.]+)', html)
        if url_match:
            # Convert URL format (e.g., "sixtytwo-barcelona") to readable name
            hotel_name = ' '.join(url_match.group(1).split('-')).title()
        else:
            hotel_name = "Unknown Hotel"
            
    return {
        "name": hotel_name
    }

# Parse price data into a dataframe
def parse_hotel_prices(price_data):
    if not price_data:
        return pd.DataFrame()
    
    # Create a DataFrame from the price data
    df = pd.DataFrame(price_data)
    
    # Clean and convert the price format
    if 'avgPriceFormatted' in df.columns:
        # Extract numeric values from formatted prices
        df['price'] = df['avgPriceFormatted'].str.extract(r'(\d+\.?\d*)').astype(float)
    
    # Convert checkin to datetime
    if 'checkin' in df.columns:
        df['date'] = pd.to_datetime(df['checkin'])
    
    return df

# Scrape hotels
async def scrape_hotels(hostels, session, start_date, end_date=None, num_adults=2):
    async def scrape_hostel(hostel):
        # Use 'url' property if available, otherwise use 'link'
        url = hostel.get('url', hostel.get('link', ''))
        
        if not url:
            logger.warning(f"Missing URL for hostel: {hostel.get('name', 'Unknown Hostel')}")
            print(f"Missing URL for hostel: {hostel.get('name', 'Unknown Hostel')}")
            return {
                "name": hostel.get('name', 'Unknown Hotel'),
                "type": hostel.get('type', 'Unknown Type'),
                "url": url, 
                "error": "Missing URL"
            }
            
        try:
            logger.debug(f"Fetching URL: {url}")
            resp = await session.get(url)
            
            # Check if the response was successful
            if resp.status_code != 200:
                logger.error(f"Error fetching URL {url}: HTTP status {resp.status_code}")
                print(f"Error fetching URL {url}: HTTP status {resp.status_code}")
                return {
                    "name": hostel.get('name', 'Unknown Hotel'),
                    "type": hostel.get('type', 'Unknown Type'),
                    "url": url, 
                    "error": f"HTTP status {resp.status_code}"
                }
                
            # Parse hotel details
            hotel_info = parse_hotel(resp.text)
            hotel_info["url"] = str(resp.url)
            hotel_info["type"] = hostel.get('type', 'Unknown Type')
            hotel_info["original_name"] = hostel.get('name', 'Unknown Hotel')
            
            # For background requests we need to find some variables
            try:
                _hotel_country = re.findall(r'hotelCountry:\s*"(.+?)"', resp.text)[0]
            except (IndexError, ValueError):
                _hotel_country = "unknown"
                
            try:
                _hotel_name = re.findall(r'hotelName:\s*"(.+?)"', resp.text)[0]
            except (IndexError, ValueError):
                # Try to extract from URL
                url_match = re.search(r'hotel/\w+/([^.]+)', str(resp.url))
                if url_match:
                    _hotel_name = ' '.join(url_match.group(1).split('-')).title()
                else:
                    _hotel_name = hotel_info["original_name"]
            
            try:
                _csrf_token = re.findall(r"b_csrf_token:\s*'(.+?)'", resp.text)[0]
            except (IndexError, ValueError):
                _csrf_token = ""
                
            # Ensure the hotel name is properly set
            if _hotel_name and not hotel_info.get("name"):
                hotel_info["name"] = _hotel_name
                
            # Scrape for 2 adults
            try:
                price_data_2_adults = await scrape_prices(
                    hotel_name=_hotel_name, 
                    hotel_country=_hotel_country, 
                    csrf_token=_csrf_token, 
                    num_adults=2,
                    start_date=start_date,
                    end_date=end_date
                )
                hotel_info["price_2_adults"] = price_data_2_adults
            except Exception as e:
                print(f"Error fetching 2 adult prices for {_hotel_name}: {str(e)}")
                hotel_info["price_2_adults"] = []
                hotel_info["price_2_adults_error"] = str(e)
            
            # Scrape for 1 adult
            try:
                price_data_1_adult = await scrape_prices(
                    hotel_name=_hotel_name, 
                    hotel_country=_hotel_country, 
                    csrf_token=_csrf_token, 
                    num_adults=1,
                    start_date=start_date,
                    end_date=end_date
                )
                hotel_info["price_1_adult"] = price_data_1_adult
            except Exception as e:
                print(f"Error fetching 1 adult prices for {_hotel_name}: {str(e)}")
                hotel_info["price_1_adult"] = []
                hotel_info["price_1_adult_error"] = str(e)
                
            return hotel_info
            
        except Exception as e:
            # Log the error but don't fail the entire process
            error_msg = f"Error processing URL {url}: {str(e)}"
            print(error_msg)
            return {
                "name": hostel.get('name', 'Unknown Hotel'),
                "type": hostel.get('type', 'Unknown Type'),
                "url": url, 
                "error": str(e)
            }

    async def scrape_prices(hotel_name, hotel_country, csrf_token, num_adults, start_date, end_date=None):
        # Calculate days to check
        if end_date:
            price_n_days = (end_date - start_date).days + 1
            logger.debug(f"Scraping date range: {start_date} to {end_date} ({price_n_days} days)")
        else:
            price_n_days = 1
            logger.debug(f"Scraping single date: {start_date}")
            
        # Ensure price_n_days is reasonable (booking.com typically limits to ~30 days)
        if price_n_days > 30:
            logger.warning(f"Date range too long ({price_n_days} days). Limiting to 30 days.")
            price_n_days = 30
            
        try:
            # Make GraphQL query
            gql_body = json.dumps(
                {
                    "operationName": "AvailabilityCalendar",
                    "variables": {
                        "input": {
                            "travelPurpose": 2,
                            "pagenameDetails": {
                                "countryCode": hotel_country,
                                "pagename": hotel_name,
                            },
                            "searchConfig": {
                                "searchConfigDate": {
                                    "startDate": start_date.strftime("%Y-%m-%d"),
                                    "amountOfDays": price_n_days,
                                },
                                "nbAdults": num_adults,
                                "nbRooms": 1,
                            },
                        }
                    },
                    "extensions": {},
                    "query": "query AvailabilityCalendar($input: AvailabilityCalendarQueryInput!) {\n  availabilityCalendar(input: $input) {\n    ... on AvailabilityCalendarQueryResult {\n      hotelId\n      days {\n        available\n        avgPriceFormatted\n        checkin\n        minLengthOfStay\n        __typename\n      }\n      __typename\n    }\n    ... on AvailabilityCalendarQueryError {\n      message\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
                separators=(",", ":"),
            )
            
            logger.debug(f"Sending GraphQL query for {hotel_name} with {num_adults} adults")
            
            # Scrape booking GraphQL
            result_price = await session.post(
                "https://www.booking.com/dml/graphql?lang=en-gb",
                content=gql_body,
                headers={
                    "content-type": "application/json",
                    "x-booking-csrf-token": csrf_token,
                    "origin": "https://www.booking.com",
                },
            )
            
            price_data = json.loads(result_price.content)
            
            # Check if we got a valid response
            if "data" not in price_data or "availabilityCalendar" not in price_data["data"]:
                logger.error(f"Invalid response format from Booking.com API: {price_data}")
                return []
                
            if "days" not in price_data["data"]["availabilityCalendar"]:
                logger.error(f"No 'days' data in Booking.com response: {price_data}")
                return []
                
            days_data = price_data["data"]["availabilityCalendar"]["days"]
            logger.debug(f"Successfully fetched {len(days_data)} days of price data")
            
            return days_data
            
        except Exception as e:
            logger.error(f"Error in GraphQL request: {str(e)}", exc_info=True)
            raise e

    hostels_data = await asyncio.gather(*[scrape_hostel(hostel) for hostel in hostels])
    return hostels_data

# Process the scraped data to add calculated fields
def process_hostel_data(hostels_data, selected_date=None):
    results = []
    error_hostels = []
    
    for hostel in hostels_data:
        if 'error' in hostel:
            error_hostels.append(hostel)
            continue
            
        result = {
            'Nombre Hotel': hostel.get('original_name', hostel.get('name', 'Unknown Hotel')),
            'Tipo': hostel.get('type', 'Unknown Type'),
            'URL': hostel.get('url', '')
        }
        
        # Process prices for 2 adults
        if 'price_2_adults' in hostel and hostel['price_2_adults']:
            df_2_adults = parse_hotel_prices(hostel['price_2_adults'])
            
            if not df_2_adults.empty:
                # Filtramos valores de 0 (sin disponibilidad) antes de calcular
                df_2_adults_filtered = df_2_adults[df_2_adults['price'] > 0.01]
                
                # Si después de filtrar no hay valores, no agregamos precios
                if df_2_adults_filtered.empty:
                    logger.warning(f"No hay precios válidos (>0) para 2 adultos en {hostel.get('name')}")
                    continue
                    
                # Si tenemos una fecha específica, filtramos para esa fecha
                if selected_date and not df_2_adults_filtered.empty:
                    df_2_adults_filtered = df_2_adults_filtered[df_2_adults_filtered['date'].dt.date == selected_date]
                    price_method = "min"  # Para día único, usamos el precio mínimo
                else:
                    # Para rango de fechas, calculamos el promedio diario
                    price_method = "mean"
                
                if not df_2_adults_filtered.empty:
                    # Obtenemos el precio según el método (mínimo o media)
                    if price_method == "min":
                        price_2_adults = df_2_adults_filtered['price'].min()
                    else:
                        price_2_adults = df_2_adults_filtered['price'].mean()
                    
                    # Apply pricing rules based on hostel type
                    if hostel.get('type') == 'Privado':
                        # Private room price is scraped, shared room is calculated
                        result['Precio Hab Baño Privado 2 Adultos'] = round(price_2_adults, 2)
                        result['Precio Hab Baño Compartido 2 Adultos'] = round(price_2_adults * 0.8, 2)
                        result['Precio Hab Baño Compartido 2 Adultos (Calculado)'] = True
                        
                        # Cálculo del precio sin tasa y sin interés (2 adultos)
                        precio_sin_tasa_privado = (price_2_adults - (5.5 * 2))
                        interes_privado = precio_sin_tasa_privado * 0.08
                        precio_sin_tasa_privado_final = precio_sin_tasa_privado - interes_privado
                        result['Precio Sin Tasa Privado 2 Adultos'] = round(precio_sin_tasa_privado_final, 2)
                        result['Tasa Turística 2 Adultos'] = 5.5 * 2
                        result['Interés 8% Privado 2 Adultos'] = round(interes_privado, 2)
                        
                        precio_sin_tasa_compartido = (price_2_adults * 0.8 - (5.5 * 2))
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 2 Adultos'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Interés 8% Compartido 2 Adultos'] = round(interes_compartido, 2)
                        
                    elif hostel.get('type') == 'Compartido':
                        # Shared room price is scraped, private room is calculated
                        result['Precio Hab Baño Compartido 2 Adultos'] = round(price_2_adults, 2)
                        result['Precio Hab Baño Privado 2 Adultos'] = round(price_2_adults * 1.2, 2)
                        result['Precio Hab Baño Privado 2 Adultos (Calculado)'] = True
                        
                        # Cálculo del precio sin tasa y sin interés (2 adultos)
                        precio_sin_tasa_compartido = (price_2_adults - (5.5 * 2))
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 2 Adultos'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Tasa Turística 2 Adultos'] = 5.5 * 2
                        result['Interés 8% Compartido 2 Adultos'] = round(interes_compartido, 2)
                        
                        precio_sin_tasa_privado = (price_2_adults * 1.2 - (5.5 * 2))
                        interes_privado = precio_sin_tasa_privado * 0.08
                        precio_sin_tasa_privado_final = precio_sin_tasa_privado - interes_privado
                        result['Precio Sin Tasa Privado 2 Adultos'] = round(precio_sin_tasa_privado_final, 2)
                        result['Interés 8% Privado 2 Adultos'] = round(interes_privado, 2)
                        
                    elif hostel.get('type') == 'Híbrido' or hostel.get('type') == 'Hibrido':
                        # Assume scraped price is for shared rooms, calculate private
                        result['Precio Hab Baño Compartido 2 Adultos'] = round(price_2_adults, 2)
                        result['Precio Hab Baño Privado 2 Adultos'] = round(price_2_adults * 1.2, 2)
                        result['Precio Hab Baño Privado 2 Adultos (Calculado)'] = True
                        
                        # Cálculo del precio sin tasa y sin interés (2 adultos)
                        precio_sin_tasa_compartido = (price_2_adults - (5.5 * 2))
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 2 Adultos'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Tasa Turística 2 Adultos'] = 5.5 * 2
                        result['Interés 8% Compartido 2 Adultos'] = round(interes_compartido, 2)
                        
                        precio_sin_tasa_privado = (price_2_adults * 1.2 - (5.5 * 2))
                        interes_privado = precio_sin_tasa_privado * 0.08
                        precio_sin_tasa_privado_final = precio_sin_tasa_privado - interes_privado
                        result['Precio Sin Tasa Privado 2 Adultos'] = round(precio_sin_tasa_privado_final, 2)
                        result['Interés 8% Privado 2 Adultos'] = round(interes_privado, 2)
        
        # Process prices for 1 adult
        if 'price_1_adult' in hostel and hostel['price_1_adult']:
            df_1_adult = parse_hotel_prices(hostel['price_1_adult'])
            
            if not df_1_adult.empty:
                # Filtramos valores de 0 (sin disponibilidad) antes de calcular
                df_1_adult_filtered = df_1_adult[df_1_adult['price'] > 0.01]
                
                # Si después de filtrar no hay valores, no agregamos precios
                if df_1_adult_filtered.empty:
                    logger.warning(f"No hay precios válidos (>0) para 1 adulto en {hostel.get('name')}")
                    continue
                    
                # Si tenemos una fecha específica, filtramos para esa fecha
                if selected_date and not df_1_adult_filtered.empty:
                    df_1_adult_filtered = df_1_adult_filtered[df_1_adult_filtered['date'].dt.date == selected_date]
                    price_method = "min"  # Para día único, usamos el precio mínimo
                else:
                    # Para rango de fechas, calculamos el promedio diario
                    price_method = "mean"
                
                if not df_1_adult_filtered.empty:
                    # Obtenemos el precio según el método (mínimo o media)
                    if price_method == "min":
                        price_1_adult = df_1_adult_filtered['price'].min()
                    else:
                        price_1_adult = df_1_adult_filtered['price'].mean()
                    
                    # Apply pricing rules based on hostel type
                    if hostel.get('type') == 'Privado':
                        # Private room price is scraped, shared room is calculated
                        result['Precio Hab Baño Privado 1 Adulto'] = round(price_1_adult, 2)
                        result['Precio Hab Baño Compartido 1 Adulto'] = round(price_1_adult * 0.8, 2)
                        result['Precio Hab Baño Compartido 1 Adulto (Calculado)'] = True
                        
                        # Cálculo del precio sin tasa y sin interés (1 adulto)
                        precio_sin_tasa_privado = (price_1_adult - 5.5)
                        interes_privado = precio_sin_tasa_privado * 0.08
                        precio_sin_tasa_privado_final = precio_sin_tasa_privado - interes_privado
                        result['Precio Sin Tasa Privado 1 Adulto'] = round(precio_sin_tasa_privado_final, 2)
                        result['Tasa Turística 1 Adulto'] = 5.5
                        result['Interés 8% Privado 1 Adulto'] = round(interes_privado, 2)
                        
                        precio_sin_tasa_compartido = (price_1_adult * 0.8 - 5.5)
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 1 Adulto'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Interés 8% Compartido 1 Adulto'] = round(interes_compartido, 2)
                        
                    elif hostel.get('type') == 'Compartido':
                        # Shared room price is scraped, private room is calculated
                        result['Precio Hab Baño Compartido 1 Adulto'] = round(price_1_adult, 2)
                        result['Precio Hab Baño Privado 1 Adulto'] = round(price_1_adult * 1.2, 2)
                        result['Precio Hab Baño Privado 1 Adulto (Calculado)'] = True
                        
                        # Cálculo del precio sin tasa y sin interés (1 adulto)
                        precio_sin_tasa_compartido = (price_1_adult - 5.5)
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 1 Adulto'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Tasa Turística 1 Adulto'] = 5.5
                        result['Interés 8% Compartido 1 Adulto'] = round(interes_compartido, 2)
                        
                        precio_sin_tasa_privado = (price_1_adult * 1.2 - 5.5)
                        interes_privado = precio_sin_tasa_privado * 0.08
                        precio_sin_tasa_privado_final = precio_sin_tasa_privado - interes_privado
                        result['Precio Sin Tasa Privado 1 Adulto'] = round(precio_sin_tasa_privado_final, 2)
                        result['Interés 8% Privado 1 Adulto'] = round(interes_privado, 2)
                        
                    elif hostel.get('type') == 'Híbrido' or hostel.get('type') == 'Hibrido':
                        # Assume scraped price is for shared rooms, calculate private
                        result['Precio Hab Baño Compartido 1 Adulto'] = round(price_1_adult, 2)
                        result['Precio Hab Baño Privado 1 Adulto'] = round(price_1_adult * 1.2, 2)
                        result['Precio Hab Baño Privado 1 Adulto (Calculado)'] = True
                        
                        # Cálculo del precio sin tasa y sin interés (1 adulto)
                        precio_sin_tasa_compartido = (price_1_adult - 5.5)
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 1 Adulto'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Tasa Turística 1 Adulto'] = 5.5
                        result['Interés 8% Compartido 1 Adulto'] = round(interes_compartido, 2)
                        
                        precio_sin_tasa_privado = (price_1_adult * 1.2 - 5.5)
                        interes_privado = precio_sin_tasa_privado * 0.08
                        precio_sin_tasa_privado_final = precio_sin_tasa_privado - interes_privado
                        result['Precio Sin Tasa Privado 1 Adulto'] = round(precio_sin_tasa_privado_final, 2)
                        result['Interés 8% Privado 1 Adulto'] = round(interes_privado, 2)
        
        # Check if prices were found
        if not any(key.startswith('Precio') for key in result.keys()):
            result['Error'] = 'No pricing data available for this hostel'
            
        results.append(result)
    
    # Return both the processed results and any error hostels
    return results, error_hostels

# Function to run the scraping process
async def run_scrape(hostels, start_date, end_date=None):
    async with AsyncClient(headers=HEADERS) as session:
        hostels_data = await scrape_hotels(
            hostels,
            session,
            start_date,
            end_date
        )
        return hostels_data

# Main application
def main():
    st.title("🏨 Barcelona Hostel Price Analysis")
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("Settings")
        
        # Debug mode toggle
        st.checkbox("Debug Mode", value=st.session_state.debug_mode, on_change=toggle_debug_mode)
        if st.session_state.debug_mode:
            st.info("Debug mode enabled - check console and log file for details")
        
        # File selection
        st.subheader("Hostel Data")
        file_options = ["Hotels Predifined.json", "hotels predefined.json", "Custom path"]
        selected_file = st.selectbox("Choose JSON file", file_options)
        
        if selected_file == "Custom path":
            custom_path = st.text_input("Enter path to JSON file", "")
            file_path = custom_path if custom_path else "Hotels Predifined.json"
        else:
            file_path = selected_file
        
        # Load hostel data
        if st.button("Load Hostel Data"):
            st.session_state.hostel_data = load_hostel_data(file_path)
            if st.session_state.hostel_data:
                st.success(f"Loaded {len(st.session_state.hostel_data)} hostels")
        
        # Display loaded hostels
        if "hostel_data" in st.session_state and st.session_state.hostel_data:
            st.info(f"Loaded {len(st.session_state.hostel_data)} hostels:")
            for i, hostel in enumerate(st.session_state.hostel_data[:5]):  # Show first 5
                st.write(f"{i+1}. {hostel.get('name', 'Unknown')}")
            if len(st.session_state.hostel_data) > 5:
                st.write(f"...and {len(st.session_state.hostel_data) - 5} more")
        
        st.divider()
        
        # Date selection
        st.subheader("Date Selection")
        date_option = st.radio(
            "Choose date option:",
            ["Single Day", "Date Range"]
        )
        
        if date_option == "Single Day":
            selected_date = st.date_input(
                "Select Date",
                value=datetime.now().date()
            )
            end_date = None
            st.info("Se mostrarán los precios mínimos para el día seleccionado.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                selected_date = st.date_input(
                    "Start Date",
                    value=datetime.now().date()
                )
            with col2:
                end_date = st.date_input(
                    "End Date",
                    value=datetime.now().date() + timedelta(days=7)
                )
            
            # Validate date range
            if end_date < selected_date:
                st.error("End date must be after start date")
                end_date = selected_date
            else:
                days_in_range = (end_date - selected_date).days + 1
                st.info(f"Se mostrará el PROMEDIO de precios para los {days_in_range} días seleccionados.")
        
        # Scrape button
        scrape_button = st.button(
            "Scrape Hostel Prices", 
            disabled=len(st.session_state.hostel_data) == 0,
            type="primary"
        )
    
    # Handle scraping when the button is clicked
    if scrape_button and st.session_state.hostel_data:
        with st.spinner("Scraping prices from hostels... This may take a moment."):
            try:
                # Run the async function to scrape all hostels
                hostels_data = asyncio.run(run_scrape(
                    st.session_state.hostel_data,
                    selected_date,
                    end_date
                ))
                
                # Save to session state
                st.session_state.hostels_data = hostels_data
                
                # Process the data
                if date_option == "Single Day":
                    results, error_hostels = process_hostel_data(hostels_data, selected_date)
                    price_description = f"para el día {selected_date.strftime('%d/%m/%Y')}"
                else:
                    results, error_hostels = process_hostel_data(hostels_data)
                    days_in_range = (end_date - selected_date).days + 1
                    price_description = f"promedio para el período del {selected_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')} ({days_in_range} días)"
                
                # Save results to session state
                st.session_state.scraping_results = results
                st.session_state.error_hostels = error_hostels
                
                # Show success message
                st.success(f"¡Se obtuvieron datos de {len(hostels_data) - len(error_hostels)} hostales correctamente!")
                
                # Show errors if any
                if error_hostels:
                    st.warning(f"{len(error_hostels)} hostales tuvieron problemas y fueron ignorados:")
                    for err_hostel in error_hostels:
                        st.warning(f"⚠️ {err_hostel.get('name', 'Unknown Hostel')}: {err_hostel.get('error', 'Unknown error')}")
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.error("Please check if all URLs are valid and try again.")
    
    # Main content area
    if "scraping_results" in st.session_state and st.session_state.scraping_results:
        results = st.session_state.scraping_results
        
        if date_option == "Single Day":
            st.header(f"Análisis de precios de hostales para {selected_date.strftime('%d/%m/%Y')}")
        else:
            days_in_range = (end_date - selected_date).days + 1
            st.header(f"Análisis de precios PROMEDIO de hostales ({selected_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}, {days_in_range} días)")
        
        # Convert to DataFrame
        df_results = pd.DataFrame(results)
        
        if df_results.empty:
            st.warning("No hay resultados para mostrar. El análisis no ha devuelto ningún dato válido.")
        else:
            # Drop the calculated flags for display
            calculated_cols = [col for col in df_results.columns if '(Calculado)' in col]
            display_df = df_results.drop(columns=calculated_cols, errors='ignore')
            
            # Round price columns to 2 decimal places
            round_cols = [col for col in display_df.columns if col.startswith('Precio')]
            for col in round_cols:
                if display_df[col].dtype in [float, int, 'float64', 'int64']:
                    display_df[col] = display_df[col].round(2)
            
            # Display a simple message about calculated values
            if date_option == "Single Day":
                st.info("ℹ️ Las habitaciones privadas en hostales 'Compartido' y las habitaciones compartidas en hostales 'Privado' muestran precios estimados. Se muestra el precio mínimo del día seleccionado.")
            else:
                days_in_range = (end_date - selected_date).days + 1
                st.info(f"ℹ️ Las habitaciones privadas en hostales 'Compartido' y las habitaciones compartidas en hostales 'Privado' muestran precios estimados. Se muestra el PRECIO PROMEDIO de los {days_in_range} días seleccionados.")
            
            # Información sobre el cálculo del precio sin tasa y sin interés
            st.info("💰 Se han añadido los siguientes cálculos para cada tipo de habitación:")
            st.markdown("""
            - **Tasa Turística**: 5,5€ por adulto
            - **Interés 8%**: El 8% del precio con la tasa turística ya descontada
            - **Precio Sin Tasa**: Precio final sin tasa turística y sin interés. Fórmula: (Precio - (5.5 × adultos)) - 8% de (Precio - (5.5 × adultos))
            """)
            
            # Display a simple table without styling
            st.dataframe(display_df, use_container_width=True)
            
            # Download button for CSV export
            try:
                csv = display_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Descargar resultados como CSV",
                    csv,
                    "hostel_prices.csv",
                    "text/csv",
                    key="download-csv"
                )
            except Exception as e:
                st.error(f"Error al crear descarga CSV: {str(e)}")
            
            # ----- SECCIÓN DE ANÁLISIS DE PRECIOS MEDIOS (MOVIDA AL PRINCIPIO) -----
            # Análisis estadístico - Precios Medios
            st.subheader("Análisis de Precios Medios")
            
            # Crear un diccionario para almacenar los cálculos de precios medios
            precio_medio = {}
            
            # Columnas de precios que queremos analizar
            columnas_precio = [
                "Precio Hab Baño Privado 1 Adulto", 
                "Precio Hab Baño Compartido 1 Adulto",
                "Precio Hab Baño Privado 2 Adultos", 
                "Precio Hab Baño Compartido 2 Adultos",
                "Precio Sin Tasa Privado 1 Adulto",
                "Precio Sin Tasa Compartido 1 Adulto",
                "Precio Sin Tasa Privado 2 Adultos",
                "Precio Sin Tasa Compartido 2 Adultos"
            ]
            
            # Calcular precio medio para cada columna
            for col in columnas_precio:
                if col in display_df.columns:
                    try:
                        # Filtrar valores que sean cero o muy cercanos a cero (sin disponibilidad)
                        valores_filtrados = display_df[col].dropna()
                        valores_filtrados = valores_filtrados[valores_filtrados > 0.01]
                        
                        if len(valores_filtrados) > 0:  # Verificar si hay valores después de filtrar
                            valor = valores_filtrados.astype(float).mean()
                            precio_medio[col] = round(valor, 2)
                        else:
                            logger.warning(f"No hay valores válidos (>0) para calcular la media de {col}")
                            precio_medio[col] = None
                    except Exception as e:
                        logger.warning(f"Error calculando promedio para {col}: {str(e)}")
                        precio_medio[col] = None
                else:
                    precio_medio[col] = None
            
            # Crear un DataFrame con los resultados
            df_precios_medios = pd.DataFrame({
                "Tipo de Habitación": [
                    "Habitación Baño Privado (1 Adulto)",
                    "Habitación Baño Compartido (1 Adulto)",
                    "Habitación Baño Privado (2 Adultos)",
                    "Habitación Baño Compartido (2 Adultos)"
                ],
                "Precio Medio (€)": [
                    precio_medio["Precio Hab Baño Privado 1 Adulto"],
                    precio_medio["Precio Hab Baño Compartido 1 Adulto"],
                    precio_medio["Precio Hab Baño Privado 2 Adultos"],
                    precio_medio["Precio Hab Baño Compartido 2 Adultos"]
                ],
                "Precio Medio Sin Tasa (€)": [
                    precio_medio["Precio Sin Tasa Privado 1 Adulto"],
                    precio_medio["Precio Sin Tasa Compartido 1 Adulto"],
                    precio_medio["Precio Sin Tasa Privado 2 Adultos"],
                    precio_medio["Precio Sin Tasa Compartido 2 Adultos"]
                ]
            })
            
            # Mostrar la tabla de precios medios
            st.write("Precios medios calculados para todos los hostales analizados:")
            st.info("ℹ️ Los valores con precio 0 (que indican falta de disponibilidad) no se han tenido en cuenta para el cálculo de los promedios.")
            st.dataframe(df_precios_medios, use_container_width=True)
            
            # Crear gráfico de precios medios
            try:
                # Convertir DataFrame a formato largo para gráfico
                df_chart = pd.melt(
                    df_precios_medios, 
                    id_vars=["Tipo de Habitación"],
                    value_vars=["Precio Medio (€)", "Precio Medio Sin Tasa (€)"],
                    var_name="Tipo de Precio",
                    value_name="Precio"
                )
                
                # Crear gráfico de barras comparativo
                chart = alt.Chart(df_chart).mark_bar().encode(
                    x=alt.X("Tipo de Habitación:N", sort=None),
                    y=alt.Y("Precio:Q", title="Precio (€)"),
                    color=alt.Color("Tipo de Precio:N", legend=alt.Legend(title="Tipo de Precio")),
                    tooltip=["Tipo de Habitación", "Tipo de Precio", alt.Tooltip("Precio:Q", format=",.2f")]
                ).properties(
                    title="Comparación de Precios Medios",
                    height=400
                )
                
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.error(f"Error al crear gráfico de precios medios: {str(e)}")
            
            # ----- SECCIÓN DE COMPARACIÓN DE PRECIOS INDIVIDUALES -----
            st.subheader("Comparación de Precios por Hostal")
            
            # ----- COMPARACIÓN PARA 1 ADULTO (NUEVA SECCIÓN) -----
            st.markdown("### Habitaciones para 1 Adulto")
            
            # Create comparison chart for private rooms (1 adult)
            if "Precio Hab Baño Privado 1 Adulto" in display_df.columns:
                try:
                    # Filtrar valores cero que indican no disponibilidad
                    private_df_1 = display_df[["Nombre Hotel", "Precio Hab Baño Privado 1 Adulto"]].dropna()
                    private_df_1 = private_df_1[private_df_1["Precio Hab Baño Privado 1 Adulto"] > 0.01]
                    
                    if not private_df_1.empty:
                        # Extraer solo el valor numérico para el gráfico
                        private_df_1["Precio"] = private_df_1["Precio Hab Baño Privado 1 Adulto"].astype(float)
                        
                        private_chart_1 = alt.Chart(private_df_1).mark_bar().encode(
                            x=alt.X("Nombre Hotel:N", sort='-y', axis=alt.Axis(labelAngle=-45, labelLimit=150)),
                            y=alt.Y("Precio:Q", title="Precio (€)"),
                            tooltip=["Nombre Hotel", alt.Tooltip("Precio:Q", format=",.2f")]
                        ).properties(
                            title="Precios de Habitaciones Privadas (1 Adulto)",
                            height=400
                        )
                        st.altair_chart(private_chart_1, use_container_width=True)
                    else:
                        st.info("No hay datos de precios para habitaciones privadas (1 adulto) disponibles para visualización.")
                except Exception as e:
                    st.error(f"Error al crear gráfico de habitaciones privadas (1 adulto): {str(e)}")
            
            # Create comparison chart for shared rooms (1 adult)
            if "Precio Hab Baño Compartido 1 Adulto" in display_df.columns:
                try:
                    # Filtrar valores cero que indican no disponibilidad
                    shared_df_1 = display_df[["Nombre Hotel", "Precio Hab Baño Compartido 1 Adulto"]].dropna()
                    shared_df_1 = shared_df_1[shared_df_1["Precio Hab Baño Compartido 1 Adulto"] > 0.01]
                    
                    if not shared_df_1.empty:
                        # Extraer solo el valor numérico para el gráfico
                        shared_df_1["Precio"] = shared_df_1["Precio Hab Baño Compartido 1 Adulto"].astype(float)
                        
                        shared_chart_1 = alt.Chart(shared_df_1).mark_bar().encode(
                            x=alt.X("Nombre Hotel:N", sort='-y', axis=alt.Axis(labelAngle=-45, labelLimit=150)),
                            y=alt.Y("Precio:Q", title="Precio (€)"),
                            tooltip=["Nombre Hotel", alt.Tooltip("Precio:Q", format=",.2f")]
                        ).properties(
                            title="Precios de Habitaciones Compartidas (1 Adulto)",
                            height=400
                        )
                        st.altair_chart(shared_chart_1, use_container_width=True)
                    else:
                        st.info("No hay datos de precios para habitaciones compartidas (1 adulto) disponibles para visualización.")
                except Exception as e:
                    st.error(f"Error al crear gráfico de habitaciones compartidas (1 adulto): {str(e)}")
            
            # ----- COMPARACIÓN PARA 2 ADULTOS -----
            st.markdown("### Habitaciones para 2 Adultos")
            
            # Create comparison chart for private rooms (2 adults)
            if "Precio Hab Baño Privado 2 Adultos" in display_df.columns:
                try:
                    # Filtrar valores cero que indican no disponibilidad
                    private_df = display_df[["Nombre Hotel", "Precio Hab Baño Privado 2 Adultos"]].dropna()
                    private_df = private_df[private_df["Precio Hab Baño Privado 2 Adultos"] > 0.01]
                    
                    if not private_df.empty:
                        # Extraer solo el valor numérico para el gráfico
                        private_df["Precio"] = private_df["Precio Hab Baño Privado 2 Adultos"].astype(float)
                        
                        private_chart = alt.Chart(private_df).mark_bar().encode(
                            x=alt.X("Nombre Hotel:N", sort='-y', axis=alt.Axis(labelAngle=-45, labelLimit=150)),
                            y=alt.Y("Precio:Q", title="Precio (€)"),
                            tooltip=["Nombre Hotel", alt.Tooltip("Precio:Q", format=",.2f")]
                        ).properties(
                            title="Precios de Habitaciones Privadas (2 Adultos)",
                            height=400
                        )
                        st.altair_chart(private_chart, use_container_width=True)
                    else:
                        st.info("No hay datos de precios para habitaciones privadas (2 adultos) disponibles para visualización.")
                except Exception as e:
                    st.error(f"Error al crear gráfico de habitaciones privadas (2 adultos): {str(e)}")
            
            # Create comparison chart for shared rooms (2 adults)
            if "Precio Hab Baño Compartido 2 Adultos" in display_df.columns:
                try:
                    # Filtrar valores cero que indican no disponibilidad
                    shared_df = display_df[["Nombre Hotel", "Precio Hab Baño Compartido 2 Adultos"]].dropna()
                    shared_df = shared_df[shared_df["Precio Hab Baño Compartido 2 Adultos"] > 0.01]
                    
                    if not shared_df.empty:
                        # Extraer solo el valor numérico para el gráfico
                        shared_df["Precio"] = shared_df["Precio Hab Baño Compartido 2 Adultos"].astype(float)
                        
                        shared_chart = alt.Chart(shared_df).mark_bar().encode(
                            x=alt.X("Nombre Hotel:N", sort='-y', axis=alt.Axis(labelAngle=-45, labelLimit=150)),
                            y=alt.Y("Precio:Q", title="Precio (€)"),
                            tooltip=["Nombre Hotel", alt.Tooltip("Precio:Q", format=",.2f")]
                        ).properties(
                            title="Precios de Habitaciones Compartidas (2 Adultos)",
                            height=400
                        )
                        st.altair_chart(shared_chart, use_container_width=True)
                    else:
                        st.info("No hay datos de precios para habitaciones compartidas (2 adultos) disponibles para visualización.")
                except Exception as e:
                    st.error(f"Error al crear gráfico de habitaciones compartidas (2 adultos): {str(e)}")
    
    # Show initial instructions when no data is loaded
    elif not st.session_state.hostel_data:
        st.info("👈 Please load hostel data using the button in the sidebar to begin.")
        
        # Example JSON format
        st.subheader("Expected JSON format:")
        example_json = [
            {
                "name": "Hostal Example",
                "type": "Privado",
                "url": "https://www.booking.com/hotel/es/example.es.html"
            }
        ]
        st.code(json.dumps(example_json, indent=2))
        
        st.write("Hostel types can be 'Privado', 'Compartido', or 'Híbrido'")

if __name__ == "__main__":
    main() 