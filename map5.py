import time
import csv
import argparse  # For better arg parsing and -h help
import requests  # For Nominatim API (free geocoding)
from selenium import webdriver
from selenium.webdriver.firefox.options import Options  # Use Firefox options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Configure Selenium with headless Firefox
firefox_options = Options()
firefox_options.add_argument("--headless")  # Headless mode
firefox_options.add_argument("--no-sandbox")  # Required in Termux
firefox_options.add_argument("--disable-dev-shm-usage")  # Overcome limited /dev/shm in Android
firefox_options.add_argument("--disable-gpu")  # Disable GPU (helps on ARM)
firefox_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")

# Initialize WebDriver (GeckoDriver should be in PATH)
driver = webdriver.Firefox(options=firefox_options)
# If GeckoDriver not found, uncomment and set path: 
# driver = webdriver.Firefox(options=firefox_options, executable_path="/data/data/com.termux/files/usr/bin/geckodriver")

# Output file
output_file = 'urls_scraped.csv'  # Generalized filename

# Function to get location coordinates using free Nominatim API
def get_location_coordinates(location):
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        data = response.json()
        if data:
            lat = data[0]['lat']
            lng = data[0]['lon']
            print(f"Geocoded '{location}' to coordinates: {lat}, {lng}")
            return lat, lng
        else:
            raise ValueError("No coordinates found")
    except Exception as e:
        print(f"Geocoding failed for '{location}': {str(e)}. Falling back to Pakistan coordinates.")
        return "30.3753", "69.3451"  # Default to Pakistan

# Function to scrape Google Maps (with deep scanning)
def scrape_google_maps_urls(query, lat, lng, max_results=50):
    results = []
    url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}/@{lat},{lng},6z"  # Dynamic coords, country/city-level zoom (6z)
    
    print(f"Navigating to: {url}")
    driver.get(url)
    
    try:
        # Wait for search results to load (increased timeout for slower ARM devices)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "hfpxzc"))  # Place result links
        )
        
        # Deep scanning: Scroll deeply to load more results
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scrolls = 20  # Increased for deep scanning (loads more places unrestricted)
        
        while scroll_attempts < max_scrolls:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)  # Increased delay for loading on mobile/ARM
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("No more results to load after deep scan.")
                break
            last_height = new_height
            scroll_attempts += 1
            print(f"Deep scan scroll {scroll_attempts}/{max_scrolls} complete.")
        
        # Parse page source with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        place_elements = soup.find_all('a', class_='hfpxzc')  # Links to place details
        
        print(f"Found {len(place_elements)} place elements after deep scan.")
        
        for i, place in enumerate(place_elements[:max_results]):
            place_url = place.get('href')
            if not place_url:
                continue
                
            print(f"Processing place {i+1}/{min(max_results, len(place_elements))}...")
            driver.get(place_url)
            time.sleep(3)  # Increased delay for place details to load on slower connections
            
            # Parse place details page
            place_soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Extract place name
            name_elem = place_soup.find('h1', class_='DUwDvf')
            name = name_elem.text.strip() if name_elem else 'N/A'
            
            # Extract website URL (updated selector for reliability; may need tweaks if Google changes)
            website_elem = place_soup.find('a', {'data-item-id': lambda x: x and 'authority' in x})
            website = website_elem.get('href') if website_elem else 'No website available'
            
            # Extract address
            address_elem = place_soup.find('div', class_='Io6YTe')
            address = address_elem.text.strip() if address_elem else 'N/A'
            
            results.append({
                'name': name,
                'website': website,
                'address': address
            })
            print(f"Found: {name} | Website: {website}")
            
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
    
    return results

# Save results to CSV
def save_to_csv(results, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'website', 'address'])
        writer.writeheader()
        for result in results:
            writer.writerow(result)
    print(f"Results saved to {filename}")

# Main execution with argparse for -h and better args
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Google Maps URL Scraper: Scrapes business/place URLs from Google Maps for a specified country and optional city, with dynamic coordinates and deep scanning.",
        epilog="Examples:\n"
               "  python map.py business 10 --country Pakistan --city Karachi  # Scrapes 10 businesses in Karachi, Pakistan\n"
               "  python map.py restaurant 20 --country USA --city New York  # Scrapes 20 restaurants in New York, USA\n"
               "  python map.py hotel 15 --country India  # Scrapes 15 hotels in India (country-level, no city)\n"
               "  python map.py -h  # Shows this help guide",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("term", nargs="?", default="business", help="Search term (e.g., 'business', 'restaurant'). Default: 'business'")
    parser.add_argument("num", nargs="?", type=int, default=50, help="Maximum number of results to scrape. Default: 50")
    parser.add_argument("--country", default="Pakistan", help="Country to focus the search on (e.g., 'USA', 'India'). Default: 'Pakistan'")
    parser.add_argument("--city", default=None, help="Optional city within the country (e.g., 'Karachi', 'New York'). If provided, search focuses on the city.")
    
    args = parser.parse_args()
    
    # Construct query and location for geocoding
    term = args.term
    country = args.country
    city = args.city
    if city:
        location = f"{city}, {country}"
        query = f"{term}s in {city}, {country}" if not term.endswith('s') else f"{term} in {city}, {country}"
    else:
        location = country
        query = f"{term}s in {country}" if not term.endswith('s') else f"{term} in {country}"
    max_results = args.num
    
    # Get dynamic coordinates
    lat, lng = get_location_coordinates(location)
    
    print(f"Using query: '{query}' with max_results: {max_results} and coordinates: {lat}, {lng}")
    
    try:
        results = scrape_google_maps_urls(query, lat, lng, max_results=max_results)
        save_to_csv(results, output_file)
        print(f"Scraping complete. Found {len(results)} places with URLs.")
    finally:
        driver.quit()  # Close the browser
