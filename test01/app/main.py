import requests # Keep requests for potential future use or fallback
from bs4 import BeautifulSoup, Tag
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, StaleElementReferenceException
import time

URL = "https://www.bottlebunker.co.kr/search?type=WINE&keyword=&page=5"
BASE_URL = "https://www.bottlebunker.co.kr"
CSV_FILE = 'wines.csv'
# More specific selector: Wait for the container AND the first button inside it
CONTAINER_SELECTOR_STR = '.grid-cols-4'
# Wait for the first button within the container as a sign that items are loading
FIRST_BUTTON_SELECTOR = (By.CSS_SELECTOR, f'{CONTAINER_SELECTOR_STR} button')
# Name selector - using raw string or double escapes
NAME_SELECTOR = r'div.text-\[1\.3rem\]' # Raw string approach
# NAME_SELECTOR = 'div.text-\\[1\\.3rem\\]' # Double escape approach
WAIT_TIMEOUT = 30 # Increased timeout

print(f"Attempting to crawl using Selenium: {URL}")

# --- Selenium Setup ---
options = webdriver.ChromeOptions()
# options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

driver = None
wine_data = []

try:
    # --- Initialize WebDriver ---
    driver = webdriver.Chrome(options=options)
    driver.get(URL)
    print("WebDriver navigated to the URL.")
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    # --- Wait for initial page load (wait for the first button) ---
    print(f"Waiting up to {WAIT_TIMEOUT} seconds for the first wine item button to appear...")
    wait.until(EC.presence_of_element_located(FIRST_BUTTON_SELECTOR))
    print("First wine item button found. Page should be loaded with items.")

    # --- Get initial button count ---
    button_count = 0
    try:
        wine_list_container_selenium = driver.find_element(By.CSS_SELECTOR, CONTAINER_SELECTOR_STR)
        initial_button_elements = wine_list_container_selenium.find_elements(By.TAG_NAME, 'button')
        button_count = len(initial_button_elements)
        print(f"Found container and initially found {button_count} wine item buttons.")
    except Exception as e:
        print(f"Error finding initial buttons after wait: {e}")
        # If count fails, maybe proceed with 0 or raise error depending on desired behavior

    # --- Loop through items by index ---
    for i in range(button_count):
        print(f"\nProcessing item {i + 1}/{button_count}...")
        name = None
        link = None

        try:
            # --- Re-find elements in each iteration to avoid staleness ---
            print("Waiting for container presence before finding buttons...")
            # Ensure container is still there (quick check)
            wine_list_container_selenium = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, CONTAINER_SELECTOR_STR)))
            print("Container found. Finding buttons again...")

            # Find all buttons *within this specific container* again
            current_buttons = wine_list_container_selenium.find_elements(By.TAG_NAME, 'button')

            if i >= len(current_buttons):
                print(f"Error: Button index {i} out of range after re-finding ({len(current_buttons)} found). Skipping.")
                continue

            # It's safer to get the button reference again
            button_to_click = current_buttons[i]
            print(f"Found button for item {i + 1}.")

            # Extract Name before clicking
            try:
                name_tag = button_to_click.find_element(By.CSS_SELECTOR, NAME_SELECTOR)
                name = name_tag.text.strip()
                print(f"Extracted name: {name}")
            except NoSuchElementException:
                print(f"Could not find name element with selector '{NAME_SELECTOR}' for item {i + 1}.")
                # Optional: Try fallback selector here if needed
            except Exception as name_e:
                print(f"Error extracting name for item {i + 1}: {name_e}")

            # --- Click and Get URL ---
            if button_to_click:
                print(f"Clicking button {i + 1}...")
                try:
                    # Scroll into view
                    driver.execute_script("arguments[0].scrollIntoView(true);", button_to_click)
                    time.sleep(0.5) # Short pause
                    wait.until(EC.element_to_be_clickable(button_to_click)).click()

                    # Wait for the product page URL
                    print("Waiting for product page URL...")
                    wait.until(EC.url_contains("/product?item_cd="))
                    link = driver.current_url
                    print(f"Product page URL found: {link}")

                    # Navigate back
                    print("Navigating back to search results...")
                    driver.back()

                    # Wait for the search results page to load again (check for first button again)
                    print("Waiting for search results page to reload (first button)...")
                    wait.until(EC.presence_of_element_located(FIRST_BUTTON_SELECTOR))
                    time.sleep(1) # Allow page JS to potentially finish loading
                    print("Search results page reloaded.")

                except StaleElementReferenceException:
                    print(f"Error: Button for item {i + 1} became stale before/during click. Skipping.")
                    # Attempt to recover by just continuing the loop, assuming back navigation wasn't needed
                    continue # Go to next item
                except TimeoutException:
                     print(f"Timeout occurred waiting for URL or page reload for item {i + 1}. Skipping.")
                     # Try to navigate back if stuck on product page
                     if "/product?item_cd=" in driver.current_url:
                          try:
                              print("Attempting to navigate back after URL timeout...")
                              driver.back()
                              wait.until(EC.presence_of_element_located(FIRST_BUTTON_SELECTOR))
                              time.sleep(1)
                          except Exception as back_err:
                              print(f"Failed to navigate back after URL timeout: {back_err}")
                     continue # Go to next item

            # --- Store Data --- 
            if name and link:
                print(f"Storing: Name='{name}', Link='{link}'")
                wine_data.append({'name': name, 'link': link})
            elif name:
                print(f"Storing with missing link: Name='{name}', Link='Not Found'")
                wine_data.append({'name': name, 'link': ''})
            else:
                print(f"Skipping item {i+1} due to missing name (and likely link).")

        # --- General Error Handling for the item ---
        except StaleElementReferenceException:
             print(f"Stale element encountered processing item {i + 1}. Re-finding elements might be needed earlier or waiting strategy adjusted. Skipping item.")
             continue
        except Exception as e:
            print(f"An unexpected error occurred processing item {i + 1}: {e}")
            # Attempt basic recovery: try to get back to search results page
            try:
                if "/product?item_cd=" in driver.current_url or "/search" not in driver.current_url:
                    print("Attempting to navigate back to search page after unexpected error...")
                    # Go back potentially multiple times if needed, or directly to search URL?
                    # Going back is simpler for now
                    driver.back()
                    wait.until(EC.presence_of_element_located(FIRST_BUTTON_SELECTOR))
                    time.sleep(1)
                    print("Navigated back after error.")
                else:
                     print("Already on search page or unknown state after error.")
            except Exception as recovery_e:
                print(f"Failed to navigate back after error: {recovery_e}. Loop might be unstable.")
            continue # Skip to the next item

except WebDriverException as e:
    print(f"WebDriver error occurred: {e}")
    print("Please ensure WebDriver (e.g., chromedriver) is installed and accessible.")
except TimeoutException:
    print(f"Timeout waiting for initial page load (first button). Check selectors or increase WAIT_TIMEOUT.")
except Exception as e:
     print(f"An unexpected error occurred during the main process: {e}")
finally:
    # --- WebDriver Quit (ensure it runs) ---
    if driver:
        driver.quit()
        print("WebDriver closed.")

# --- CSV Writing (remains the same) ---
if not wine_data:
     print("\nNo wine data extracted. Check logs for errors during processing.")

# Write data to CSV (Append Mode)
if wine_data:
    print(f"\nExtracted {len(wine_data)} items. Appending to {CSV_FILE}...")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(script_dir, CSV_FILE)
        print(f"CSV file location: {csv_path}")

        # Check if file exists and is not empty to decide whether to write header
        file_exists = os.path.exists(csv_path)
        write_header = not file_exists or os.path.getsize(csv_path) == 0

        # Open in append mode ('a')
        with open(csv_path, 'a', newline='', encoding='utf-8-sig') as file:
            writer = csv.DictWriter(file, fieldnames=['name', 'link'])
            
            if write_header:
                print("Writing header row...")
                writer.writeheader()
            else:
                 print("File exists and is not empty, skipping header.")

            writer.writerows(wine_data)
            print(f"Data successfully appended to {csv_path}")
    except IOError as e:
        print(f"Error writing to CSV file {csv_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during CSV writing: {e}")
else:
     # This case means wine_data list was empty after the loop
     # No message needed here as the one above covers it, unless specific feedback is desired
     pass
    # print("\nNo new wine data extracted in this run to append.")
