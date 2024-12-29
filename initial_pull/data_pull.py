import csv
import json
import re
from typing import List

from selenium import webdriver
from dataclasses import dataclass, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

class DeckFormat(Enum):
    STANDARD = "Standard"
    BRAWL = "HistoricBrawl"
    OTHER = "Other"

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
        self.driver_path = driver_path

    def _build_page_url(self, page_number: int, page_size: int = 50) -> str:
        """
        Helper method to build the URL for the given page number.
        """
        base_url = "https://api2.moxfield.com/v2/decks/search"
        params = {
            "includePinned": "true",
            "showIllegal": "true",
            "authorUserNames": self.author_user_name,
            "pageNumber": page_number,
            "pageSize": page_size,
            "sortType": "updated",
            "sortDirection": "descending",
            "board": "mainboard",
        }
        query_string = "&".join([f"{key}={value}" for key, value in params.items()])
        return f"{base_url}?{query_string}"

    def fetch_and_extract_data(self, url) -> dict:
        """
        Fetches deck data from the provided URL by using Selenium to load the page
        and retrieving the page source, then extracts JSON from <pre> tags.
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
            data_dict = self._extract_data(page_source)
            return data_dict
        finally:
            driver.quit()

    def _fetch_page_data(self, page_number: int) -> dict:
        """
        Helper method to fetch JSON data for a single page
        and return it as a Python dictionary.
        """
        url = self._build_page_url(page_number)
        return self.fetch_and_extract_data(url) or {}



    def _extract_data(self, page_source):
        """
        Extracts the JSON dictionary from the page source. The JSON data in the Moxfield
        API response is contained within <pre> tags.
        """
        match = re.search(r'<pre.*?>(.*?)</pre>', page_source, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
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
        deck_name = deck_data.get("name", "Unknown Deck")
        public_url = deck_data.get("publicUrl", "")

        raw_format = deck_data.get("format", "standard")  # e.g., "standard", "brawl", etc.
        try:
            deck_format = DeckFormat.from_string(raw_format)
        except ValueError:
            print(f"Warning: Unrecognized format '{raw_format}'. Defaulting to Other.")
            deck_format = DeckFormat.OTHER

        tally = DeckWildcardTally(
            deck_name=deck_name,
            url=public_url,
            format=deck_format,
            common=0,
            uncommon=0,
            rarity=0,
            mythic=0
        )

        boards = deck_data.get("boards", {})
        mainboard_cards_dict = boards.get("mainboard", {}).get("cards", {})
        sideboard_cards_dict = boards.get("sideboard", {}).get("cards", {})

        mainboard_cards = list(mainboard_cards_dict.values())
        sideboard_cards = list(sideboard_cards_dict.values())

        all_cards = mainboard_cards + sideboard_cards

        for card_entry in all_cards:
            card_info = card_entry.get("card", {})
            rarity_str = card_info.get("rarity", "").lower()
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
                if rarity_str:  # It's not empty
                    print(f"Unexpected rarity: {rarity_str}")
                else:
                    print("Card does not have a rarity specified.")

        return tally

    def run_for_url(self, url: str) -> DeckWildcardTally:
        data_dict = self.fetch_and_extract_data(url)

        if data_dict:
            tally = self.process_data_to_DeckWildcardTally(data_dict)
            print(tally)
            return tally
        else:
            print("No data extracted.")
            return None

    def scan_decklists_from_profile(self, start_page=1, end_page=5):
        """
        Fetch multiple pages in parallel to collect deck metadata from the Moxfield profile.

        :param start_page: first page number to fetch
        :param end_page: last page number to fetch
        :return: A list of all deck metadata from the requested pages.
        """
        decklists = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_page = {
                executor.submit(self._fetch_page_data, page_num): page_num
                for page_num in range(start_page, end_page + 1)
            }

            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    data = future.result()
                except Exception as exc:
                    print(f"Page {page_num} generated an exception: {exc}")
                    continue

                # If valid data, store it
                if data and data.get('data'):
                    decklists.extend(data['data'])
                else:
                    print(f"No data returned for page {page_num}.")
        print(f"Fetched {len(decklists)} decklists.")
        return decklists

    def retrieve_and_process_deck_data(self, decklists) -> List[DeckWildcardTally]:
        deck_tallies: List[DeckWildcardTally] = []

        def process_single_deck(entry):
            url = entry['publicUrl']
            deck_id = url.split('/')[-1]
            decklist_url = f"https://api2.moxfield.com/v3/decks/all/{deck_id}"
            data_dict = self.fetch_and_extract_data(decklist_url)
            if data_dict:
                return self.process_data_to_DeckWildcardTally(data_dict)
            return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_entry = {executor.submit(process_single_deck, entry): entry for entry in decklists}
            for future in as_completed(future_to_entry):
                entry = future_to_entry[future]
                try:
                    result = future.result()
                    if result:
                        deck_tallies.append(result)
                except Exception as e:
                    print(f"Error processing deck {entry['publicUrl']}: {e}")

        return deck_tallies

    @staticmethod
    def export_to_csv(deck_tallies: List[DeckWildcardTally], output_file: str):
        """
        Exports a list of DeckWildcardTally objects to a CSV file.

        :param deck_tallies: List of DeckWildcardTally objects to be exported.
        :param output_file: Path to the output CSV file.
        """
        fieldnames = [field for field in DeckWildcardTally.__dataclass_fields__.keys()]

        try:
            with open(output_file, mode='w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for tally in deck_tallies:
                    writer.writerow(asdict(tally))

            print(f"CSV successfully written to {output_file}")

        except Exception as e:
            print(f"An error occurred while writing to CSV: {e}")

def main():
    """
    Main entry point for the script.
    """
    fetcher = DeckDataFetcher()
    all_deck_data = fetcher.scan_decklists_from_profile(start_page=1, end_page=1)
    print(f"Collected {len(all_deck_data)} deck(s) from pages 1-5.")
    rarity_data = fetcher.retrieve_and_process_deck_data(all_deck_data)
    fetcher.export_to_csv(rarity_data, "data.csv")

if __name__ == "__main__":
    main()
