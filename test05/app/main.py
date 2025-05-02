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

# URL for the first page (pagination is handled by clicking links)
URL = "https://www.oliveyoung.co.kr/store/display/getBrandShopDetail.do?onlBrndCd=A000729"
BASE_URL = "https://www.oliveyoung.co.kr"
CSV_FILE = 'oliveyoung.csv'
TOTAL_PAGES = 4 # As stated by the user
WAIT_TIMEOUT = 20 # Increased timeout for potential dynamic loading

# --- Selectors for oliveyoung.co.kr ---
# Container for the entire product grid
PRODUCT_CONTAINER_SELECTOR = (By.ID, 'allGoodsList')
# Selector for individual product list items (li) within the container
PRODUCT_ITEM_SELECTOR = (By.CSS_SELECTOR, 'div#allGoodsList ul.prod-list.goodsProd li')
# Selectors relative to the item (li)
PRODUCT_LINK_ANCHOR_SELECTOR = (By.CSS_SELECTOR, 'a.thumb') # The anchor tag within the li
PRODUCT_IMG_SELECTOR = (By.CSS_SELECTOR, 'a.thumb > img.pic-thumb') # The image tag within the anchor
PAGINATION_CONTAINER_SELECTOR = (By.CSS_SELECTOR, 'div.pageing')
PAGINATION_LINK_SELECTOR_TEMPLATE = "a[data-page-no='{}']" # Template for page links

print(f"Attempting to crawl {TOTAL_PAGES} pages from Olive Young (Physiogel)...")

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

    # --- Load Initial Page ---
    print(f"Navigating to initial page: {URL}")
    driver.get(URL)

    # --- Loop through pages ---
    for page_num in range(1, TOTAL_PAGES + 1):
        print(f"\n--- Processing Page {page_num}/{TOTAL_PAGES} ---")

        try:
            # --- Wait for page elements to be ready ---
            print(f"Waiting for product container: {PRODUCT_CONTAINER_SELECTOR[1]}")
            product_container_present = WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located(PRODUCT_CONTAINER_SELECTOR)
            )

            # Wait for the first product item (li) inside the container
            print(f"Waiting for first product item using selector: {PRODUCT_ITEM_SELECTOR[1]}")
            first_item_present = WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located(PRODUCT_ITEM_SELECTOR)
            )
            print("Product container and first item loaded.")

            # --- Scrape items on the current page ---
            # Find ALL li elements within the container directly
            product_elements = driver.find_elements(*PRODUCT_ITEM_SELECTOR)
            item_count = len(product_elements)
            print(f"Found {item_count} product items (li) on page {page_num}.")

            if not product_elements:
                 print(f"No product items found on page {page_num}. Check selectors or page structure.")
                 break

            page_items_count = 0
            # The item_element is now the <li>
            for i, item_element in enumerate(product_elements):
                # Small check to ensure it's a valid item li (has data-goods-idx)
                if not item_element.get_attribute('data-goods-idx'):
                    print(f"  Skipping element {i+1} as it lacks 'data-goods-idx' (likely not a product item).")
                    continue

                print(f"Processing item {i + 1}/{item_count}...")
                name = None
                link = None

                try:
                    # Find link and image relative to the li
                    link_anchor = item_element.find_element(*PRODUCT_LINK_ANCHOR_SELECTOR)
                    href = link_anchor.get_attribute('href')
                    if href and href.startswith('http'):
                        link = href
                    elif href and href.startswith('/'):
                        link = BASE_URL + href
                    elif href:
                         print(f"  Warning: Unexpected href format: {href}. Using as is.")
                         link = href

                    img_tag = item_element.find_element(*PRODUCT_IMG_SELECTOR)
                    name = img_tag.get_attribute('alt')

                except NoSuchElementException as e:
                    # It's possible some li might be spacers or ads, treat missing link/img as skippable
                    print(f"  - Element missing in item {i + 1} (e.g., link or image within expected li structure): {e}. Skipping item.")
                    continue
                except Exception as e:
                    print(f"  - Error extracting data from item {i + 1}: {e}")
                    continue

                if name and link:
                    print(f"  - Extracted: Name='{name[:30]}...', Link='{link}'")
                    product_data.append({'name': name.strip(), 'link': link.strip()})
                    page_items_count += 1
                else:
                    # This case might happen if img alt is empty or href is missing but elements exist
                    print(f"  - Failed to extract name or link for item {i + 1} (valid elements found but data missing).")

            print(f"Finished processing {page_items_count} valid items on page {page_num}.")

            # --- Navigate to the next page (if not the last page) ---
            if page_num < TOTAL_PAGES:
                next_page_num = page_num + 1
                print(f"Attempting to navigate to page {next_page_num}...")
                try:
                    pagination_container = driver.find_element(*PAGINATION_CONTAINER_SELECTOR)
                    next_page_link_selector = (By.CSS_SELECTOR, PAGINATION_LINK_SELECTOR_TEMPLATE.format(next_page_num))
                    next_page_link = pagination_container.find_element(*next_page_link_selector)

                    # Use the first product item (li) found on the current page as reference for staleness check
                    if product_elements: # Ensure we have elements to check against
                         first_product_element_li = product_elements[0]
                         staleness_check_possible = True
                    else:
                        staleness_check_possible = False
                        print("Warning: Cannot perform staleness check as no product elements were found on the current page.")

                    print(f"Clicking page {next_page_num} link...")
                    # Use JavaScript click as a fallback if direct click fails sometimes
                    try:
                         next_page_link.click()
                    except Exception as click_err:
                         print(f"Direct click failed ({click_err}), attempting JavaScript click...")
                         driver.execute_script("arguments[0].click();", next_page_link)

                    # Wait for the page to change by checking if the old element becomes stale
                    if staleness_check_possible:
                        print("Waiting for page transition (staleness check)...")
                        WebDriverWait(driver, WAIT_TIMEOUT).until(
                            EC.staleness_of(first_product_element_li) # Check staleness of the li
                        )
                        print(f"Successfully navigated to page {next_page_num}.")
                    else:
                        print("Skipping staleness check. Pausing briefly before proceeding...")
                        time.sleep(2) # Add a fixed delay if staleness check isn't possible

                    time.sleep(0.5) # Small additional pause

                except NoSuchElementException:
                    print(f"Could not find pagination link for page {next_page_num}. Stopping.")
                    break
                except TimeoutException:
                    print(f"Timed out waiting for page {next_page_num} transition. Stopping.")
                    break
                except Exception as nav_e:
                    print(f"An error occurred during pagination to page {next_page_num}: {nav_e}")
                    break
            else:
                print("\nLast page reached.")

        except TimeoutException:
             print(f"Error: Timed out waiting for product container or first item on page {page_num}. Stopping.")
             break
        except Exception as page_e:
             print(f"An unexpected error occurred processing page {page_num}: {page_e}")
             break

except WebDriverException as e:
    print(f"WebDriver error: {e}")
    print("Please ensure ChromeDriver is installed and accessible in your PATH or configured correctly.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    if driver:
        print("\nClosing WebDriver...")
        driver.quit()
        print("WebDriver closed.")

# --- CSV Writing (Append Mode) ---
if not product_data:
     print("\nNo product data extracted. Check logs for errors during processing.")
else:
    print(f"\nExtracted {len(product_data)} items in total. Appending to {CSV_FILE}...")
    try:
        try:
             script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
             script_dir = os.getcwd()

        csv_path = os.path.join(script_dir, CSV_FILE)
        print(f"CSV file location: {csv_path}")

        file_exists = os.path.exists(csv_path)
        try:
            file_size = os.path.getsize(csv_path) if file_exists else 0
        except OSError:
            file_size = 0
            file_exists = False

        write_header = not file_exists or file_size == 0

        with open(csv_path, 'a', newline='', encoding='utf-8-sig') as file:
            fieldnames = ['name', 'link']
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            if write_header:
                print("Writing header row.")
                writer.writeheader()

            print(f"Appending {len(product_data)} rows...")
            writer.writerows(product_data)
        print(f"Successfully appended data to {CSV_FILE}")

    except IOError as e:
        print(f"Error writing to CSV file {CSV_FILE}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during CSV writing: {e}")

print("\nScript finished.")


