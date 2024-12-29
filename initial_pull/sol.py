from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
import time


def main():
    # The deck URL
    url = "https://moxfield.com/decks/bNiJEbhB_UOiD7aQOQXLyQ"

    # Configure Chrome options
    chrome_options = Options()
    # Run Chrome in headless mode (no visible browser window)
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--log-level=3")

    # Create a new instance of the Chrome driver with Selenium Wire
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Go to the Moxfield deck page
        driver.get(url)

        # Allow some time for all network requests to finish
        time.sleep(5)

        # Target substring we are looking for
        target_price = "$162.71"

        # Iterate through each request captured by Selenium Wire
        found_in_requests = False
        for request in driver.requests:
            # Some requests may not have a response or body
            if request.response and request.response.body:
                try:
                    body = request.response.body.decode("utf-8", errors="ignore")

                    # Print out request URL and status code
                    print(f"Request URL: {request.url}")
                    print(f"Status Code: {request.response.status_code}")

                    # Check if the target price is in this response
                    if target_price in body:
                        print(f"\n>>> Found price '{target_price}' in request: {request.url}")
                        found_in_requests = True
                        # You can break here if only the first occurrence matters
                        # break
                except Exception as e:
                    # If there's an issue decoding the response body, just skip
                    print(f"Failed to decode response for: {request.url}, error: {e}")

        if not found_in_requests:
            print(f"\nPrice '{target_price}' was not found in any of the network responses.")

    finally:
        # Quit the driver
        driver.quit()


if __name__ == "__main__":
    main()
