import requests # Keep requests for potential future use or fallback
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, StaleElementReferenceException
import csv # Import csv module
import time
import re # Import regex module

URL_TEMPLATE = "https://ckdmall.co.kr/product/list.html?cate_no=53&page={}" # URL template for pagination
BASE_URL = "https://ckdmall.co.kr"
CSV_FILE = 'ckd.csv' # Changed CSV filename
TOTAL_PAGES = 8 # Total number of pages to crawl
WAIT_TIMEOUT = 30

# --- Selectors for ckdmall.co.kr ---
# Target the main product list, not the recommended one
PRODUCT_LIST_SELECTOR = (By.CSS_SELECTOR, 'div.xans-product-listnormal ul.prdList')
# Items within the main list
PRODUCT_ITEM_SELECTOR = (By.CSS_SELECTOR, 'li.xans-record-')
# Selectors relative to the item
PRODUCT_LINK_ANCHOR_SELECTOR = (By.CSS_SELECTOR, 'div.prdImg > a')
PRODUCT_IMG_SELECTOR = (By.CSS_SELECTOR, 'div.prdImg > a > img')

print(f"Attempting to crawl {TOTAL_PAGES} pages using Selenium...")

# --- Selenium Setup ---
options = webdriver.ChromeOptions()
# options.add_argument('--headless') # Uncomment for headless mode
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")

driver = None
product_data = [] # Initialize list to store data from all pages

try:
    print("Initializing WebDriver...")
    driver = webdriver.Chrome(options=options)
    print("WebDriver initialized.")

    # Loop through pages
    for page_num in range(1, TOTAL_PAGES + 1):
        page_url = URL_TEMPLATE.format(page_num)
        print(f"\nNavigating to page {page_num}: {page_url}")
        driver.get(page_url)

        try:
            # Wait for the *main* product list AND the first item within it to be present
            print(f"Waiting for main product list container: {PRODUCT_LIST_SELECTOR[1]}")
            product_list_present = WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located(PRODUCT_LIST_SELECTOR)
            )
            print(f"Waiting for first product item in main list: {PRODUCT_ITEM_SELECTOR[1]}")
            # Wait specifically for the first li inside the main list ul
            # The selector for the first item needs context from the main list selector
            first_item_css_selector = f"{PRODUCT_LIST_SELECTOR[1]} > {PRODUCT_ITEM_SELECTOR[1]}"
            print(f"Waiting for selector: {first_item_css_selector}")
            first_item_present = WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, first_item_css_selector))
            )
            print("Main product list and first item loaded.")

            # --- Re-find elements after page load ---
            product_list_element = driver.find_element(*PRODUCT_LIST_SELECTOR)
            product_elements = product_list_element.find_elements(*PRODUCT_ITEM_SELECTOR)
            print(f"Found {len(product_elements)} product items on page {page_num}.")

            if not product_elements:
                print(f"No product items found on page {page_num}, stopping pagination.")
                break # Stop if a page has no items

            # Loop through items found on the current page
            for item_index, element in enumerate(product_elements):
                name = None
                link = None

                try:
                    # Extract Link
                    link_anchor = element.find_element(*PRODUCT_LINK_ANCHOR_SELECTOR)
                    href = link_anchor.get_attribute('href')
                    if href and href.startswith('/'):
                        link = BASE_URL + href
                    elif href:
                        link = href # Assume it's absolute if it doesn't start with /

                    # Extract Name from img alt
                    img_tag = element.find_element(*PRODUCT_IMG_SELECTOR)
                    name = img_tag.get_attribute('alt')

                except NoSuchElementException:
                    print(f"  - Element missing in item {item_index + 1} on page {page_num}, skipping.")
                    continue # Skip this item if essential elements are missing
                except Exception as e:
                    print(f"  - Error extracting data from item {item_index + 1} on page {page_num}: {e}")
                    continue # Skip item on other errors

                if name and link:
                    print(f"  - Extracted: Name='{name[:30]}...', Link='{link}'")
                    product_data.append({'name': name.strip(), 'link': link.strip()})
                else:
                    print(f"  - Failed to extract name or link for item {item_index + 1} on page {page_num}.")

            # Optional: Add a small delay between pages if needed, though waits should handle most cases
            # time.sleep(1)

        except TimeoutException:
            print(f"Error: Timed out waiting for product list or first item on page {page_num}. Stopping.")
            break # Stop pagination if content doesn't load
        except Exception as e:
            print(f"An error occurred processing page {page_num}: {e}")
            # Optionally decide whether to continue or break based on the error
            # break

except WebDriverException as e:
    print(f"WebDriver error occurred: {e}")
    print("Please ensure WebDriver (e.g., chromedriver) is installed and accessible.")
except Exception as e:
     print(f"An unexpected error occurred during the main process: {e}")
finally:
    # --- WebDriver Quit (ensure it runs) ---
    if driver:
        driver.quit()
        print("WebDriver closed.")

# --- CSV Writing (Append Mode) ---
if not product_data:
     print("\nNo product data extracted overall. Check logs for errors.")

# Write data to CSV
if product_data:
    print(f"\nExtracted a total of {len(product_data)} items across {TOTAL_PAGES} pages. Appending to {CSV_FILE}...")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(script_dir, CSV_FILE)
        print(f"CSV file location: {csv_path}")

        # Check if file exists and is not empty to decide whether to write header
        file_exists = os.path.exists(csv_path)
        write_header = not file_exists or os.path.getsize(csv_path) == 0

        with open(csv_path, 'a', newline='', encoding='utf-8-sig') as file:
            writer = csv.DictWriter(file, fieldnames=['name', 'link'])
            
            if write_header:
                print("Writing header row...")
                writer.writeheader()
            else:
                 print("File exists and is not empty, skipping header.")

            writer.writerows(product_data)
            print(f"Data successfully appended to {csv_path}")
    except IOError as e:
        print(f"Error writing to CSV file {csv_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during CSV writing: {e}")
else:
     print("\nNo product data was extracted in this run.")
