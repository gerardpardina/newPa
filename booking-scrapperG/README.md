# Barcelona Hostel Price Analysis

A Streamlit application to analyze prices of hostels in Barcelona, providing comparative pricing for private and shared rooms.

## Features

- Load predefined Barcelona hostels from JSON file
- Scrape current prices from Booking.com for single or multiple dates
- Analyze prices for both 1 and 2 adults
- Apply pricing rules based on hostel type (Privado, Compartido, Híbrido)
- Calculate estimated prices for room types not directly offered
- Display results in a clear, sortable table
- Visualize price comparisons with interactive charts
- Export results to CSV

## How to Use

1. **Installation**:
   ```
   pip install -r requirements.txt
   ```

2. **Run the Application**:
   ```
   streamlit run finalapp.py
   ```

3. **Usage Steps**:
   - Click "Load Hostel Data" to load the predefined list of Barcelona hostels
   - Select either a single day or a date range for analysis
   - Click "Scrape Hostel Prices" to fetch the current pricing data
   - View the results in the table and charts
   - Use the "Download Results as CSV" button to export data

## Pricing Rules

The application applies the following rules for price calculations:

- **Privado** (Private hostels): 
  - Scrapes private room prices directly
  - Calculates shared room prices by reducing the private room price by 20%

- **Compartido** (Shared hostels):
  - Scrapes shared room prices directly
  - Calculates private room prices by increasing the shared room price by 20%

- **Híbrido** (Hybrid hostels):
  - Assumes the lowest scraped price is for shared rooms
  - Calculates private room prices by increasing the shared room price by 20%

Calculated prices are highlighted in the table for transparency.

## Data Structure

The hostel data is stored in `hotels predefined.json` with the following structure:
```json
[
  {
    "name": "Hostal Example",
    "type": "Privado",
    "url": "https://www.booking.com/hotel/es/example.es.html"
  }
]
```

## Requirements

- Python 3.8+
- Libraries: streamlit, pandas, httpx, asyncio, and others (see requirements.txt)

## Troubleshooting

- If you encounter errors during scraping, the application will display warning messages.
- URLs with connection issues will be automatically skipped.
- The application handles rate limiting by implementing proper delays between requests.

# Booking.com Scraper

This scraper is using [scrapfly.io](https://scrapfly.io/) and Python to scrape hotel data from booking.com. 

Booking.com can be difficult to scrape because of scraper blocking so this scraper is using Scrapfly's [Anti Scraping Protection Bypass](https://scrapfly.io/docs/scrape-api/anti-scraping-protection) feature.

Full tutorial: <https://scrapfly.io/blog/how-to-scrape-bookingcom/>

The scraping code is located in the `bookingcom.py` file. It's fully documented and simplified for educational purposes and the example scraper run code can be found in `run.py` file.

This scraper scrapes:
- Booking.com search for finding hotels from search queries.
- Booking.com hotel listing details:  
    - hotel info: description, rating, features etc.
    - prices

For output examples see the `./results` directory.

## Fair Use Disclaimer

Note that this code is provided free of charge as is, and Scrapfly does __not__ provide free web scraping support or consultation. For any bugs, see the issue tracker.

## Setup and Use

This Booking scraper uses __Python 3.10__ with [scrapfly-sdk](https://pypi.org/project/scrapfly-sdk/) package which is used to scrape and parse Booking.com's data.

0. Ensure you have __Python 3.10__ and [poetry Python package manager](https://python-poetry.org/docs/#installation) on your system.
1. Retrieve your Scrapfly API key from <https://scrapfly.io/dashboard> and set `SCRAPFLY_KEY` environment variable:
    ```shell
    $ export SCRAPFLY_KEY="YOUR SCRAPFLY KEY"
    ```
2. Clone and install Python environment:
    ```shell
    $ git clone https://github.com/scrapfly/scrapfly-scrapers.git
    $ cd scrapfly-scrapers/bookingcom-scraper
    $ poetry install
    ```
3. Run example scrape:
    ```shell
    $ poetry run python run.py
    ```
4. Run tests:
    ```shell
    $ poetry install --with dev
    $ poetry run pytest test.py
    # or specific scraping areas
    $ poetry run pytest test.py -k test_hotel_scraping
    $ poetry run pytest test.py -k test_search_scraping
    ```

