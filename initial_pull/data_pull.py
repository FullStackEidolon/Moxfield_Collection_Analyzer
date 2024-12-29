import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from dataclasses import dataclass
from enum import Enum

class DeckFormat(Enum):
    STANDARD = "Standard"
    BRAWL = "Brawl"

    @classmethod
    def from_string(cls, value: str):
        normalized_value = value.strip().capitalize()
        for format in cls:
            if format.value.lower() == normalized_value.lower():
                return format
        raise ValueError(f"{value} is not a valid DeckFormat")


@dataclass
class DeckWildcardTally:
    deck_name: str
    url: str
    format: DeckFormat
    common: int = 0
    uncommon: int = 0
    rarity: int = 0
    mythic: int = 0


class DeckDataFetcher:
    """
    A class to encapsulate the logic for fetching deck data from Moxfield (or other sources).
    """


    def __init__(self, driver_path=None):
        """
        Optionally accept a path to the WebDriver executable.
        If driver_path is not provided, the default ChromeDriver from PATH will be used.
        """
        self.author_user_name = "CovertGoBlue"
        profile_url = "https://api2.moxfield.com/v2/decks/search?includePinned=true&showIllegal=true&authorUserNames=CovertGoBlue&pageNumber=1&pageSize=1200&sortType=updated&sortDirection=descending&board=mainboard"
        self.driver_path = driver_path


    def fetch_and_extract_data(self, url) -> dict:
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
            data_dict = self.extract_data(page_source)
            return data_dict
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

    def process_data_to_DeckWildcardTally(self, deck_data):
        """
        Pulls info from the deck_data dictionary to create and return a DeckWildcardTally object.
        1. Extract deck name and public URL.
        2. Convert deck_data.format to a DeckFormat enum.
        3. Gather cards from the mainboard and sideboard.
        4. For each card, increment counts based on rarity AND the card's quantity.
        5. Log unexpected rarities.
        """
        # 1. Extract basic info
        deck_name = deck_data.get("name", "Unknown Deck")
        public_url = deck_data.get("publicUrl", "")

        # 2. Convert deck_data.format to a DeckFormat enum (fall back to Standard on error)
        raw_format = deck_data.get("format", "standard")  # e.g., "standard", "brawl", etc.
        try:
            deck_format = DeckFormat.from_string(raw_format)
        except ValueError:
            print(f"Warning: Unrecognized format '{raw_format}'. Defaulting to Standard.")
            deck_format = DeckFormat.STANDARD

        # Create the DeckWildcardTally object with default wildcard counts of 0
        tally = DeckWildcardTally(
            deck_name=deck_name,
            url=public_url,
            format=deck_format,
            common=0,
            uncommon=0,
            rarity=0,
            mythic=0
        )

        # 3. Collect all cards from mainboard and sideboard
        boards = deck_data.get("boards", {})
        mainboard_cards_dict = boards.get("mainboard", {}).get("cards", {})
        sideboard_cards_dict = boards.get("sideboard", {}).get("cards", {})

        # Convert the dict values to lists
        mainboard_cards = list(mainboard_cards_dict.values())
        sideboard_cards = list(sideboard_cards_dict.values())

        all_cards = mainboard_cards + sideboard_cards

        # 4. For each card, increment counts based on rarity and quantity
        for card_entry in all_cards:
            # The actual card data is usually under "card"
            card_info = card_entry.get("card", {})

            # Rarity is typically a string (e.g., "common", "uncommon", "rare", "mythic")
            rarity_str = card_info.get("rarity", "").lower()

            # Quantity is how many copies of this card the deck uses
            quantity = card_entry.get("quantity", 1)

            if rarity_str == "common":
                tally.common += quantity
            elif rarity_str == "uncommon":
                tally.uncommon += quantity
            elif rarity_str == "rare":
                tally.rarity += quantity
            elif rarity_str == "mythic":
                tally.mythic += quantity
            else:
                # 5. Log unexpected rarities
                if rarity_str:  # It's not an empty string
                    print(f"Unexpected rarity: {rarity_str}")
                else:
                    print("Card does not have a rarity specified.")

        return tally

    def run_for_url(self, url: str) -> DeckWildcardTally:
        url = "https://api2.moxfield.com/v3/decks/all/bNiJEbhB_UOiD7aQOQXLyQ"
        data_dict = self.fetch_and_extract_data(url)

        if data_dict:
            # Create the tally DTO
            tally = self.process_data_to_DeckWildcardTally(data_dict)
            print(tally)
            return tally
        else:
            print("No data extracted.")


    def scan_decklinks_from_profile(self):

        base_url = "https://api2.moxfield.com/v2/decks/search"
        initial_params = {
            "includePinned": "true",
            "showIllegal": "true",
            "authorUserNames": self.author_user_name,
            "pageSize": 12,
            "sortType": "updated",
            "sortDirection": "descending",
            "board": "mainboard"
        }

        decklists = []
        page_number = 1

        while True:
            # Update the page number in the parameters
            initial_params['pageNumber'] = page_number

            # Construct the full URL with parameters
            current_url = f"{base_url}?"
            current_url += "&".join([f"{key}={value}" for key, value in initial_params.items()])

            # Fetch data from the current page
            print(f"Fetching page {page_number}...")
            data = self.fetch_and_extract_data(current_url)

            if not data or not data.get('data'):  # Stop if no data or decks returned
                print("No more data to fetch.")
                break

            # Add the fetched data to the list
            decklists.extend(data.get('data', []))
            page_number += 1  # Move to the next page
            print(decklists)
        return decklists

def main():
    """
    Main entry point for the script.
    """
    fetcher = DeckDataFetcher()
    # fetcher.run()
    fetcher.scan_decklinks_from_profile()


if __name__ == "__main__":
    main()
