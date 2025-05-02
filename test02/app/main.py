import requests # Keep requests for potential future use or fallback
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, StaleElementReferenceException
import csv # Import csv module
import time

URL = "https://www.happyconstore.com/brand/main.do?brandSeq=1474297546090049"
BASE_URL = "https://www.happyconstore.com"
CSV_FILE = 'icecreams.csv' # Changed CSV filename
TOTAL_PAGES = 6 # Total number of pages to crawl

# --- Updated Selectors for happyconstore.com ---
ITEM_LIST_CONTAINER_SELECTOR = (By.CSS_SELECTOR, 'div.prd_list#nowGoods ul')
ITEM_SELECTOR = (By.TAG_NAME, 'li')
NAME_SELECTOR = (By.CSS_SELECTOR, 'dd.t_nm')
ID_INPUT_SELECTOR = (By.CSS_SELECTOR, 'input[name="goodsNo"]')
PAGINATION_WRAPPER_SELECTOR = (By.CSS_SELECTOR, 'div.page_wrap')
PAGE_NUMBER_LINK_XPATH_TEMPLATE = ".//a[contains(@class, 'page') and contains(@class, 'number') and text()='{}']"
CURRENT_PAGE_SELECTOR = (By.CSS_SELECTOR, 'a.page.number.on')

WAIT_TIMEOUT = 30

print(f"Attempting to crawl using Selenium: {URL}")

# --- Selenium Setup ---
options = webdriver.ChromeOptions()
# options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

driver = None
icecream_data = [] # Initialize list to store data from all pages

try:
    # --- Initialize WebDriver ---
    driver = webdriver.Chrome(options=options)
    driver.get(URL)
    print("WebDriver navigated to the URL.")
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    # --- Loop through pages --- 
    for page_num in range(1, TOTAL_PAGES + 1):
        print(f"\n--- Processing Page {page_num}/{TOTAL_PAGES} ---")

        try:
            # --- Wait for page content to load ---
            if page_num > 1:
                # For subsequent pages, wait for the content to refresh after click
                print(f"Waiting for page {page_num} content to load...")
                # Wait for the previous page's element to become stale
                if 'old_first_item' in locals() and old_first_item:
                     try:
                         wait.until(EC.staleness_of(old_first_item))
                         print("Previous content is stale.")
                     except TimeoutException:
                          print("Warning: Did not detect staleness of old content. Proceeding anyway.")
                # Wait for the new container/items to be present
                item_list_container = wait.until(EC.presence_of_element_located(ITEM_LIST_CONTAINER_SELECTOR))
                # Optional: wait for the current page number indicator to update
                wait.until(EC.text_to_be_present_in_element(CURRENT_PAGE_SELECTOR, str(page_num)))
                print(f"Page {page_num} content loaded.")
            else:
                # For the first page, just wait for the initial load
                print(f"Waiting up to {WAIT_TIMEOUT} seconds for the item list container to appear...")
                item_list_container = wait.until(EC.presence_of_element_located(ITEM_LIST_CONTAINER_SELECTOR))
                print("Initial item list container found.")

            # --- Scrape items on the current page ---
            print(f"Finding items on page {page_num}...")
            item_elements = item_list_container.find_elements(*ITEM_SELECTOR)
            # Store reference to first item to check for staleness later
            old_first_item = item_elements[0] if item_elements else None 
            item_count = len(item_elements)
            print(f"Found {item_count} potential items on page {page_num}.")

            if item_count == 1 and "empty" in item_elements[0].get_attribute("class"):
                 print("Page contains 'empty' message, skipping item processing.")
                 item_count = 0 # Treat as zero items found
            
            page_items_count = 0
            for i, item_element in enumerate(item_elements):
                if "empty" in item_element.get_attribute("class"): continue # Skip empty placeholder
                
                print(f"Processing item {i + 1}/{item_count} on page {page_num}...")
                name = None
                link = None
                goods_id = None

                try:
                    # Extract Name
                    try:
                        name_tag = item_element.find_element(*NAME_SELECTOR)
                        name = driver.execute_script("return arguments[0].firstChild.textContent;", name_tag).strip()
                    except NoSuchElementException:
                        print(f"Could not find name element.")
                    except Exception as name_e:
                        print(f"Error extracting name: {name_e}")

                    # Extract Goods ID
                    try:
                        id_input = item_element.find_element(*ID_INPUT_SELECTOR)
                        goods_id = id_input.get_attribute('value')
                    except NoSuchElementException:
                        print(f"Could not find ID input.")
                    except Exception as id_e:
                        print(f"Error extracting ID: {id_e}")

                    # Construct Link
                    if goods_id:
                        link = f"{BASE_URL}/goods/detail.do?goodsNo={goods_id}"

                    # Store Data
                    if name or link:
                        print(f"Storing: Name='{name if name else 'Not Found'}', Link='{link if link else 'Not Found'}'")
                        icecream_data.append({'name': name if name else '', 'link': link if link else ''})
                        page_items_count += 1
                    else:
                        print(f"Skipping item due to missing name and link.")

                except StaleElementReferenceException:
                    print(f"Stale element encountered processing item. Might need to re-find item_elements. Skipping item.")
                    continue
                except Exception as item_e:
                    print(f"An unexpected error occurred processing an item: {item_e}")
                    continue
            print(f"Finished processing {page_items_count} items on page {page_num}.")

            # --- Navigate to the next page (if not the last page) ---
            if page_num < TOTAL_PAGES:
                print(f"Trying to navigate to page {page_num + 1}...")
                try:
                    pagination_wrapper = driver.find_element(*PAGINATION_WRAPPER_SELECTOR)
                    next_page_link_xpath = PAGE_NUMBER_LINK_XPATH_TEMPLATE.format(page_num + 1)
                    next_page_link = pagination_wrapper.find_element(By.XPATH, next_page_link_xpath)
                    
                    # Scroll pagination into view if needed
                    driver.execute_script("arguments[0].scrollIntoView();", pagination_wrapper)
                    time.sleep(0.5)
                    wait.until(EC.element_to_be_clickable(next_page_link)).click()
                    print(f"Clicked link for page {page_num + 1}.")
                except NoSuchElementException:
                     print(f"Could not find link for page {page_num + 1}. Ending pagination loop.")
                     break # Exit page loop if link not found
                except Exception as nav_e:
                     print(f"Error clicking next page link: {nav_e}. Ending pagination loop.")
                     break # Exit page loop on other errors
            else:
                 print("Reached the last page.")

        except TimeoutException as page_timeout:
             print(f"Timeout loading content for page {page_num}: {page_timeout}. Stopping.")
             break # Exit page loop on timeout
        except Exception as page_e:
             print(f"An unexpected error occurred processing page {page_num}: {page_e}. Stopping.")
             break # Exit page loop on other errors

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
if not icecream_data:
     print("\nNo ice cream data extracted overall. Check logs for errors.")

# Write data to CSV
if icecream_data:
    print(f"\nExtracted a total of {len(icecream_data)} items. Appending to {CSV_FILE}...")
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

            writer.writerows(icecream_data)
            print(f"Data successfully appended to {csv_path}")
    except IOError as e:
        print(f"Error writing to CSV file {csv_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during CSV writing: {e}")
else:
     # This case means icecream_data list was empty after the loop
     print("\nNo ice cream data was extracted in this run.") # More specific message