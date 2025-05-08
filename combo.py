import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random
import os
from datetime import datetime

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_ID = "1HKAWAfLBIgd85UsVuBR0C8FDFxdtJhOsEDaA7jWh8rw"
RANGE_NAME = "A1:A"

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    chrome_options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {e}")
        print("\nPlease make sure Chrome is installed at /Applications/Google Chrome.app")
        raise

def find_prices(driver, wait):
    price_selectors = [
        "sc-581c4cd4-0.sc-2daeb340-0.bIYFRr.JFPeK",
        "price-range",
        "ticket-price",
        "[data-test='price-range']", 
        ".price-range__text" 
    ]
    
    for selector in price_selectors:
        try:
            elements = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, selector))
            )
            if elements:
                return elements
        except TimeoutException:
            try:
                elements = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                if elements:
                    return elements
            except TimeoutException:
                continue
    
    return None

def get_google_sheets_service():
    """Authenticate and return the Google Sheets service."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES,
                redirect_uri="http://localhost:3000"
            )
            creds = flow.run_local_server(port=3000)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
    
    return build("sheets", "v4", credentials=creds)

def insert_new_column(service):
    """Insert a new column to the left of column A."""
    try:
        request = {
            "insertDimension": {
                "range": {
                    "sheetId": 0,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 1 
                },
                "inheritFromBefore": False
            }
        }
        
        body = {
            "requests": [request]
        }
        
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body=body
        ).execute()
        
        print("Successfully inserted new column to the left of column A")
        return True
        
    except HttpError as err:
        print(f"An error occurred while inserting column: {err}")
        return False

def write_prices_to_sheet(service, prices):
    """Write the scraped prices to the new column A."""
    if not prices:
        print("No prices to write to the spreadsheet.")
        return

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    values = [[current_time]] + [[price] for price in prices]
    
    body = {
        'values': values
    }
    
    try:
        result = service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        print(f"Successfully updated {result.get('updatedCells')} cells in column A")
    except HttpError as err:
        print(f"An error occurred while writing to the spreadsheet: {err}")

def scrape_ticketmaster_prices():
    url = 'https://www.ticketmaster.com/event/Z7r9jZ1A7oJvP'
    prices = []
    
    try:
        print("Starting browser...")
        driver = setup_driver()
        
        print("Accessing Ticketmaster...")
        driver.get(url)
        time.sleep(5)
        
        wait = WebDriverWait(driver, 30)
        price_elements = find_prices(driver, wait)
        
        if price_elements:
            print("\nFound price elements:")
            for element in price_elements:
                price_text = element.text.strip()
                if price_text:
                    print(price_text)
                    prices.append(price_text)
        else:
            print("No price elements found. The page structure might have changed.")
            print("\nPage source preview:")
            print(driver.page_source[:1000])
        
        return prices
        
    except Exception as e:
        print(f"An error occurred: {e}")
        if 'driver' in locals():
            print("\nPage source at time of error:")
            print(driver.page_source[:1000])
        return []
    finally:
        if 'driver' in locals():
            driver.quit()

def main():
    prices = scrape_ticketmaster_prices()
    
    if prices:
        service = get_google_sheets_service()
        
        if insert_new_column(service):

            write_prices_to_sheet(service, prices)
        else:
            print("Failed to insert new column, aborting write operation")
    else:
        print("No prices were scraped, so nothing was written to the spreadsheet.")

if __name__ == "__main__":
    main()