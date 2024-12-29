import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By


class DeckDataFetcher:
    """
    A class to encapsulate the logic for fetching deck data from Moxfield (or other sources).
    """

    def __init__(self, driver_path=None):
        """
        Optionally accept a path to the WebDriver executable.
        If driver_path is not provided, the default ChromeDriver from PATH will be used.
        """
        self.driver_path = driver_path

    def fetch_deck_data(self, url):
        """
        Fetches deck data from the provided URL by using Selenium to load the page
        and retrieving the page source.

        :param url: The URL to fetch data from.
        :return: The raw page source (HTML) containing the JSON data.
        """
        if self.driver_path:
            driver = webdriver.Chrome(self.driver_path)
        else:
            driver = webdriver.Chrome()

        try:
            driver.get(url)
            # Wait for the page to load or handle any JavaScript-based challenges
            driver.implicitly_wait(10)

            # Retrieve page source
            page_source = driver.page_source
            return page_source
        finally:
            driver.quit()

    def extract_data(self, page_source):
        """
        Extracts the JSON dictionary from the page source. The JSON data in the Moxfield
        API response is contained within <pre> tags.

        :param page_source: The raw HTML page source that contains JSON wrapped in <pre> tags.
        :return: A Python dictionary if parsing is successful, otherwise None.
        """
        # Use a regular expression to find the text inside <pre>...</pre>
        match = re.search(r'<pre.*?>(.*?)</pre>', page_source, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                # Parse JSON string into a Python dict
                return json.loads(json_str)
            except json.JSONDecodeError:
                print("Unable to parse JSON data.")
                return None
        else:
            print("No <pre> tags found or no JSON data in the page source.")
            return None

    def run(self):
        """
        A convenience method to demonstrate fetching deck data from a hard-coded URL.
        1) Fetch the page source
        2) Extract JSON data into a Python dict
        3) Do something (print, store, process) with the data
        """
        url = "https://api2.moxfield.com/v3/decks/all/bNiJEbhB_UOiD7aQOQXLyQ"
        page_source = self.fetch_deck_data(url)
        data_dict = self.extract_data(page_source)

        if data_dict:
            print("Extracted JSON Dictionary:\n", data_dict)
        else:
            print("No data extracted.")


def main():
    """
    Main entry point for the script.
    """
    fetcher = DeckDataFetcher()
    fetcher.run()


if __name__ == "__main__":
    main()
