import asyncio
import json
import re
from datetime import datetime
from typing import List
import pandas as pd

from httpx import AsyncClient

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Connection": "keep-alive",
    "Accept-Language": "en-US,en;q=0.9,lt;q=0.8,et;q=0.7,de;q=0.6",
}


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


async def scrape_hotels(
    urls: List[str], session: AsyncClient, price_start_dt: str, price_n_days=30, num_adults=2
):
    async def scrape_hotel(url: str):
        try:
            resp = await session.get(url)
            
            # Check if the response was successful
            if resp.status_code != 200:
                print(f"Error fetching URL {url}: HTTP status {resp.status_code}")
                return {"url": url, "error": f"HTTP status {resp.status_code}", "name": f"Error: {url[-30:]}"}
                
            hotel = parse_hotel(resp.text)
            hotel["url"] = str(resp.url)
            
            # for background requests we need to find some variables with error handling:
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
                    _hotel_name = "Unknown Hotel"
            
            try:
                _csrf_token = re.findall(r"b_csrf_token:\s*'(.+?)'", resp.text)[0]
            except (IndexError, ValueError):
                _csrf_token = ""
                
            # Ensure the hotel name is set to the extracted name from hotelName
            if _hotel_name and not hotel.get("name"):
                hotel["name"] = _hotel_name
                
            # Try to get price data, but continue if it fails
            try:
                hotel["price"] = await scrape_prices(
                    hotel_name=_hotel_name, hotel_country=_hotel_country, csrf_token=_csrf_token, num_adults=num_adults
                )
            except Exception as e:
                print(f"Error fetching prices for {_hotel_name}: {str(e)}")
                hotel["price"] = []  # Empty price data
                hotel["price_error"] = str(e)
                
            return hotel
            
        except Exception as e:
            # Log the error but don't fail the entire process
            error_msg = f"Error processing URL {url}: {str(e)}"
            print(error_msg)
            return {"url": url, "error": str(e), "name": f"Error: {url[-30:]}"}

    async def scrape_prices(hotel_name, hotel_country, csrf_token, num_adults):
        # make graphql query from our variables
        gql_body = json.dumps(
            {
                "operationName": "AvailabilityCalendar",
                # hotel varialbes go here
                # you can adjust number of adults, room number etc.
                "variables": {
                    "input": {
                        "travelPurpose": 2,
                        "pagenameDetails": {
                            "countryCode": hotel_country,
                            "pagename": hotel_name,
                        },
                        "searchConfig": {
                            "searchConfigDate": {
                                "startDate": price_start_dt,
                                "amountOfDays": price_n_days,
                            },
                            "nbAdults": num_adults,
                            "nbRooms": 1,
                        },
                    }
                },
                "extensions": {},
                # this is the query itself, don't alter it
                "query": "query AvailabilityCalendar($input: AvailabilityCalendarQueryInput!) {\n  availabilityCalendar(input: $input) {\n    ... on AvailabilityCalendarQueryResult {\n      hotelId\n      days {\n        available\n        avgPriceFormatted\n        checkin\n        minLengthOfStay\n        __typename\n      }\n      __typename\n    }\n    ... on AvailabilityCalendarQueryError {\n      message\n      __typename\n    }\n    __typename\n  }\n}\n",
            },
            # note: this removes unnecessary whitespace in JSON output
            separators=(",", ":"),
        )
        # scrape booking graphql
        result_price = await session.post(
            "https://www.booking.com/dml/graphql?lang=en-gb",
            content=gql_body,
            # note that we need to set headers to avoid being blocked
            headers={
                "content-type": "application/json",
                "x-booking-csrf-token": csrf_token,
                "origin": "https://www.booking.com",
            },
        )
        price_data = json.loads(result_price.content)
        return price_data["data"]["availabilityCalendar"]["days"]

    hotels = await asyncio.gather(*[scrape_hotel(url) for url in urls])
    return hotels


def parse_hotel_prices(price_data):
    if not price_data:
        return pd.DataFrame()
    
    # Create a DataFrame from the price data
    df = pd.DataFrame(price_data)
    
    # Convert checkin to datetime
    df['checkin'] = pd.to_datetime(df['checkin'])
    
    # Format the date
    df['date'] = df['checkin'].dt.strftime('%Y-%m-%d')
    
    # Remove the __typename column
    if '__typename' in df.columns:
        df = df.drop(columns=['__typename'])
    
    # Reorder columns
    cols = ['date', 'available', 'avgPriceFormatted', 'minLengthOfStay']
    df = df[cols]
    
    # Rename columns for better display
    df.columns = ['Date', 'Available', 'Price', 'Min Stay (Nights)']
    
    df['Price Value'] = df['Price'].str.extract(r'(\d+\.?\d*)').astype(float)
    
    return df


# example use:
if __name__ == "__main__":

    async def run():
        async with AsyncClient(headers=HEADERS) as session:
            hotels = await scrape_hotels(
                ["https://www.booking.com/hotel/gb/gardencourthotel.html"],
                session,
                datetime.now().strftime("%Y-%m-%d"),  # today
            )
            print(json.dumps(hotels, indent=2))
            with open("hotels.json", "w") as f:
                json.dump(hotels, f, indent=2)
            print(parse_hotel_prices(hotels[0]["price"]))

    asyncio.run(run())