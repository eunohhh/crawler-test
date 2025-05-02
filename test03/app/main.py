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

URL = "https://www.lotteeatz.com/brand/ria"
BASE_URL = "https://www.lotteeatz.com"
CSV_FILE = 'lottelia.csv' # Changed CSV filename
DETAIL_URL_TEMPLATE = BASE_URL + "/products/introductions/{}?rccode=brnd_main"

# --- Selectors for lotteeatz.com ---
CATEGORY_TAB_LIST_SELECTOR = (By.ID, 'categoryList')
CATEGORY_TAB_ITEM_SELECTOR = (By.TAG_NAME, 'li') # Get all tabs within the list
PRODUCT_LIST_CONTAINER_SELECTOR = (By.ID, 'productList')
PRODUCT_ITEM_SELECTOR = (By.CSS_SELECTOR, 'li.prod-item')
PRODUCT_NAME_SELECTOR = (By.CSS_SELECTOR, 'div.prod-tit')
PRODUCT_LINK_ANCHOR_SELECTOR = (By.CSS_SELECTOR, 'a.btn-link[onclick*="goBrandDetail"]')
PRODUCT_ID_REGEX = r"goBrandDetail\('([^']+)'\)" # Regex to extract ID like REP_...

WAIT_TIMEOUT = 30

print(f"Attempting to crawl using Selenium: {URL}")

# --- Selenium Setup ---
options = webdriver.ChromeOptions()
# options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

driver = None
product_data = [] # Initialize list to store data from all categories

try:
    # --- Initialize WebDriver ---
    driver = webdriver.Chrome(options=options)
    driver.get(URL)
    print("WebDriver navigated to the URL.")
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    # --- Wait for initial page load (category tabs) ---
    print(f"Waiting up to {WAIT_TIMEOUT} seconds for category tabs to appear...")
    category_tab_list = wait.until(EC.presence_of_element_located(CATEGORY_TAB_LIST_SELECTOR))
    category_tabs = category_tab_list.find_elements(*CATEGORY_TAB_ITEM_SELECTOR)
    # Filter out potential non-category items if necessary, or get IDs/texts
    category_tab_info = []
    for tab in category_tabs:
        try:
            tab_id = tab.get_attribute('id')
            tab_text = tab.find_element(By.CSS_SELECTOR, 'span.tab-text').text
            if tab_id and tab_text: # Ensure it's a valid tab
                 category_tab_info.append({'id': tab_id, 'text': tab_text, 'element': tab})
        except Exception as e:
             print(f"Warning: Could not process a category tab: {e}")

    print(f"Found {len(category_tab_info)} category tabs: {[info['text'] for info in category_tab_info]}")

    # --- Loop through categories ---
    first_product_list_element = None # To track for staleness

    for i, tab_info in enumerate(category_tab_info):
        print(f"\n--- Processing Category: {tab_info['text']} ({i+1}/{len(category_tab_info)}) ---")

        try:
            # --- Click Category Tab ---
            # Re-find the tab element to avoid staleness, using its ID
            current_tab_element = wait.until(EC.element_to_be_clickable((By.ID, tab_info['id'])))
            print(f"Clicking tab: {tab_info['text']}")
            current_tab_element.click()

            # --- Wait for Product List Update ---
            print("Waiting for product list to update...")
            if first_product_list_element: # If not the first category
                 try:
                     wait.until(EC.staleness_of(first_product_list_element))
                     print("Previous product list element is stale.")
                 except TimeoutException:
                      print("Warning: Did not detect staleness of previous product list. Content might not have updated correctly.")
            
            # Wait for the new product list container and its first item
            try:
                 product_list_container = wait.until(EC.presence_of_element_located(PRODUCT_LIST_CONTAINER_SELECTOR))
                 # Additionally wait for the h3 title inside to potentially match the category text
                 # wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, f'#{PRODUCT_LIST_CONTAINER_SELECTOR[1]} h3'), tab_info['text'])) # This might be too strict if titles don't match exactly
                 # Wait for *any* product item to appear within the container
                 wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f'#{PRODUCT_LIST_CONTAINER_SELECTOR[1]} li.prod-item')))
                 print("Product list updated.")
            except TimeoutException:
                  print("Timeout waiting for the new product list content to appear after clicking tab. Skipping category.")
                  continue # Skip to next category

            # --- Scrape items in the current category ---
            product_elements = product_list_container.find_elements(*PRODUCT_ITEM_SELECTOR)
            first_product_list_element = product_elements[0] if product_elements else None # Store first element for next staleness check
            item_count = len(product_elements)
            print(f"Found {item_count} product items in '{tab_info['text']}'.")
            
            page_items_count = 0
            for item_element in product_elements:
                name = None
                link = None
                product_id = None

                try:
                    # Extract Name
                    try:
                        name_tag = item_element.find_element(*PRODUCT_NAME_SELECTOR)
                        name = name_tag.text.strip()
                    except NoSuchElementException:
                        print(f"Could not find name for an item.")
                    except Exception as name_e:
                        print(f"Error extracting name: {name_e}")

                    # Extract Product ID and Construct Link
                    try:
                        link_anchor = item_element.find_element(*PRODUCT_LINK_ANCHOR_SELECTOR)
                        onclick_attr = link_anchor.get_attribute('onclick')
                        id_match = re.search(PRODUCT_ID_REGEX, onclick_attr)
                        if id_match:
                            product_id = id_match.group(1)
                            link = DETAIL_URL_TEMPLATE.format(product_id)
                        else:
                             print(f"Could not extract product ID from onclick: {onclick_attr}")
                    except NoSuchElementException:
                        print(f"Could not find link anchor/onclick attribute.")
                    except Exception as link_e:
                        print(f"Error extracting ID/link: {link_e}")

                    # Store Data
                    if name or link:
                        print(f"Storing: Name='{name if name else 'Not Found'}', Link='{link if link else 'Not Found'}'")
                        product_data.append({'name': name if name else '', 'link': link if link else ''})
                        page_items_count += 1
                    else:
                        print(f"Skipping item due to missing name and link.")

                except StaleElementReferenceException:
                    print(f"Stale element encountered processing an item. Re-finding might be needed. Skipping item.")
                    continue
                except Exception as item_e:
                    print(f"An unexpected error occurred processing an item: {item_e}")
                    continue
            print(f"Finished processing {page_items_count} items in category '{tab_info['text']}'.")

        except TimeoutException as category_timeout:
             print(f"Timeout occurred processing category '{tab_info['text']}': {category_timeout}. Skipping to next category.")
             continue
        except Exception as category_e:
             print(f"An unexpected error occurred processing category '{tab_info['text']}': {category_e}. Skipping to next category.")
             continue

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
    print(f"\nExtracted a total of {len(product_data)} items across all categories. Appending to {CSV_FILE}...")
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

