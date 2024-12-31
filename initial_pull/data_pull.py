import csv
import json
import re
import logging
from datetime import datetime
from typing import List, Dict

from selenium import webdriver
from dataclasses import dataclass, asdict, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Rarity(Enum):
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    MYTHIC = "MYTHIC"
    SPECIAL = "SPECIAL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, value: str):
        normalized_value = value.strip().upper()
        for rarity in cls:
            if rarity.value == normalized_value:
                return rarity
        return cls.UNKNOWN


class DeckFormat(Enum):
    STANDARD = "Standard"
    BRAWL = "HistoricBrawl"
    PIONEER = "Pioneer"
    COMMANDER = "Commander"
    TIMELESS = "Timeless"
    ALCHEMY = "Alchemy"
    HISTORIC = "Historic"
    NONE = "None"
    OTHER = "Other"

    @classmethod
    def from_string(cls, value: str):
        normalized_value = value.strip().capitalize()
        for format in cls:
            if format.value.lower() == normalized_value.lower():
                return format
        raise ValueError(f"{value} is not a valid DeckFormat")


@dataclass
class Card:
    unique_id: str
    scryfall_id: str
    name: str
    cmc: int
    type_line: str
    colors: List[str]
    rarity: "Rarity" = "Rarity.UNKNOWN"
    max_quantity: int = 0


@dataclass
class CollectionWildcardTally:
    cards: Dict[str, Card] = field(default_factory=dict)

@dataclass
class DeckWildcardTally:
    deck_name: str
    url: str
    format: DeckFormat
    last_updated_at: datetime.date
    common: int = 0
    uncommon: int = 0
    rare: int = 0
    mythic: int = 0
    special: int = 0


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
        self.driver_chunk_size = 200
        self.max_workers = 1
        self.driver_path = driver_path
        self.standard_wildcard_tally = CollectionWildcardTally(cards={})
        self.historic_brawl_wildcard_tally = CollectionWildcardTally(cards={})

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

    def fetch_and_extract_data(self, urls: List[str]) -> Dict[str, dict]:
        """
        Fetches deck data from the provided list of URLs by using Selenium
        to load each page sequentially (reusing the same driver) and
        retrieving the page source, then extracts JSON from <pre> tags.

        :param urls: A list of URL strings
        :return: A dictionary where each key is the URL and the value is
                 the data dictionary extracted from that page.
        """
        logger.info("Fetching data from multiple URLs sequentially using the same WebDriver.")

        # Initialize WebDriver
        if self.driver_path:
            driver = webdriver.Chrome(self.driver_path)
        else:
            driver = webdriver.Chrome()

        data_map = {}  # Dictionary to hold {url: data_dict}
        try:
            for url in urls:
                logger.info(f"Fetching data from URL: {url}")
                driver.get(url)
                driver.implicitly_wait(10)  # wait for page to load

                page_source = driver.page_source
                data_dict = self._extract_data(page_source)
                logger.debug("Data dictionary extracted")
                data_map[url] = data_dict
        finally:
            driver.quit()

        return data_map

    def _fetch_decklist_page_data(self, page_number: int) -> dict:
        """
        Helper method to fetch JSON data for a single page
        and return it as a Python dictionary.
        """
        logger.info(f"Fetching page data for page_number={page_number}")
        url = self._build_page_url(page_number)
        return self.fetch_and_extract_data([url]) or {}

    def _extract_data(self, page_source: str) -> dict:
        """
        Extracts the JSON dictionary from the page source. The JSON data
        in the Moxfield API response is contained within <pre> tags.
        """
        match = re.search(r'<pre.*?>(.*?)</pre>', page_source, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("Unable to parse JSON data.")
                return {}
        else:
            logger.warning("No <pre> tags found or no JSON data in the page source.")
            return {}

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
            logger.warning(f"Warning: Unrecognized format '{raw_format}'. Defaulting to Other.")
            deck_format = DeckFormat.OTHER

        tally = DeckWildcardTally(
            deck_name=deck_name,
            url=public_url,
            format=deck_format,
            last_updated_at=deck_data.get("lastUpdatedAtUtc", None),
        )

        boards = deck_data.get("boards", {})
        mainboard_cards_dict = boards.get("mainboard", {}).get("cards", {})
        sideboard_cards_dict = boards.get("sideboard", {}).get("cards", {})

        mainboard_cards = list(mainboard_cards_dict.values())
        sideboard_cards = list(sideboard_cards_dict.values())

        all_cards = mainboard_cards + sideboard_cards

        for card_entry in all_cards:
            self.add_card_to_collection(card_entry, deck_format)
            card_info = card_entry.get("card", {})
            rarity_str = card_info.get("rarity", "").lower()
            quantity = card_entry.get("quantity", 1)

            if rarity_str == "common":
                tally.common += quantity
            elif rarity_str == "uncommon":
                tally.uncommon += quantity
            elif rarity_str == "rare":
                tally.rare += quantity
            elif rarity_str == "mythic":
                tally.mythic += quantity
            elif rarity_str == "special":
                tally.special += quantity
            else:
                if rarity_str:  # It's not empty
                    logger.warning(f"Unexpected rarity: {rarity_str}")
                else:
                    logger.warning("Card does not have a rarity specified.")

        return tally

    def add_card_to_collection(self, card_data: dict, deck_format: DeckFormat):
        """
        Adds a card to the collection_wildcard_tally attribute based on the card data dictionary.

        :param card_data: The dictionary containing card details.
        """
        card = card_data["card"]

        unique_id = card["uniqueCardId"]
        scryfall_id = card["scryfall_id"]
        name = card["name"]
        cmc = int(card["cmc"])
        type_line = card["type_line"]
        colors = card.get("colors", [])
        rarity = Rarity.from_string(card.get("rarity", "UNKNOWN"))
        max_quantity = card_data.get("quantity", 0)

        # Create a Card object
        new_card = Card(
            unique_id=unique_id,
            scryfall_id=scryfall_id,
            name=name,
            cmc=cmc,
            type_line=type_line,
            colors=colors,
            rarity=rarity,
            max_quantity=max_quantity,
        )

        if deck_format == DeckFormat.BRAWL:

            if unique_id in self.historic_brawl_wildcard_tally.cards:
                if self.historic_brawl_wildcard_tally.cards[unique_id].max_quantity < max_quantity:
                    self.historic_brawl_wildcard_tally.cards[unique_id].max_quantity = max_quantity
            else:
                self.historic_brawl_wildcard_tally.cards[unique_id] = new_card
        elif deck_format == DeckFormat.STANDARD:
            if unique_id in self.standard_wildcard_tally.cards:
                if self.standard_wildcard_tally.cards[unique_id].max_quantity < max_quantity:
                    self.standard_wildcard_tally.cards[unique_id].max_quantity = max_quantity
            else:
                self.standard_wildcard_tally.cards[unique_id] = new_card
        logger.debug(f"Added card {name} (ID: {unique_id}) to {DeckFormat} collection with max_quantity: {max_quantity}")

    def scan_decklists_from_profile(self, start_page=1, end_page=5):
        """
        Fetch multiple pages in parallel (in chunks) to collect deck metadata
        from the Moxfield profile.

        :param start_page: first page number to fetch
        :param end_page:   last page number to fetch
        :return:           A list of all deck metadata from the requested pages.
        """
        logger.info(f"Scanning decklists from page {start_page} to {end_page}.")

        # 1) Build a list of page URLs
        page_urls = [self._build_page_url(page_num) for page_num in range(start_page, end_page + 1)]
        logger.info(f"Assembled {len(page_urls)} page URLs.")

        # 2) Helper function to chunk the list of URLs into sub-lists of size n
        def chunked(iterable, n):
            for i in range(0, len(iterable), n):
                yield iterable[i: i + n]

        # Decide how many pages we want per chunk/thread
        chunk_size = self.driver_chunk_size
        url_chunks = list(chunked(page_urls, chunk_size))
        logger.info(f"Split into {len(url_chunks)} chunk(s) of up to {chunk_size} URL(s) each.")

        # 3) Use ThreadPoolExecutor to pull data for groups of URLs simultaneously
        decklists = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_chunk = {
                executor.submit(self.fetch_and_extract_data, chunk): chunk
                for chunk in url_chunks
            }

            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    # 4) fetch_and_extract_data returns a dict { url: data_dict } for all URLs in chunk
                    result_dict = future.result()
                    logger.info(f"Successfully fetched {len(result_dict)} page(s) in this chunk.")

                    # 5) For each page in this chunk, parse out the deck metadata
                    for url, data in result_dict.items():
                        if data and data.get('data'):
                            decklists_count = len(data['data'])
                            decklists.extend(data['data'])
                            logger.info(f"Page {url} returned {decklists_count} decklists.")
                        else:
                            logger.info(f"No data returned for page {url}.")

                except Exception as exc:
                    logger.error(f"Exception while processing chunk {chunk}: {exc}")

        logger.info(f"Fetched {len(decklists)} decklists total from pages {start_page} to {end_page}.")
        return decklists

    def retrieve_and_process_deck_data(self, decklists) -> List[DeckWildcardTally]:
        """
        Refactored to batch deck URLs 10 at a time and pass them into
        a (multi-URL) `fetch_and_extract_data` method in parallel threads.
        """
        deck_tallies: List[DeckWildcardTally] = []
        total_decks = len(decklists)
        logger.info(f"Retrieving and processing data for {total_decks} deck(s).")

        # 1) Build the complete list of decklist URLs (api calls)
        all_urls = []
        for entry in decklists:
            url = entry['publicUrl']
            deck_id = url.split('/')[-1]
            decklist_url = f"https://api2.moxfield.com/v3/decks/all/{deck_id}"
            all_urls.append(decklist_url)

        # 2) Helper function for chunking a list into sub-lists of size n
        def chunked(iterable, n):
            for i in range(0, len(iterable), n):
                yield iterable[i: i + n]

        # 3) Create list of URL chunks (each chunk is a list of at most 10 URLs)
        url_chunks = list(chunked(all_urls, self.driver_chunk_size))

        logger.info(f"Created {len(url_chunks)} chunk(s) of URLs (up to 10 per chunk).")

        # 4) Fetch data in parallel, one chunk per thread
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Here we assume `self.fetch_and_extract_data` now accepts a list of URLs
            # and returns a dict { url: extracted_data_dict }
            future_to_chunk = {
                executor.submit(self.fetch_and_extract_data, chunk): chunk
                for chunk in url_chunks
            }

            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]  # the list of URLs in that chunk
                try:
                    # data_map is { url_string: data_dict } for each URL in the chunk
                    data_map = future.result()
                    logger.info(f"Successfully fetched data for {len(data_map)} URLs in chunk.")

                    # 5) Convert each data_dict to a DeckWildcardTally
                    for url, deck_data in data_map.items():
                        if deck_data:
                            tally = self.process_data_to_DeckWildcardTally(deck_data)
                            deck_tallies.append(tally)

                except Exception as e:
                    logger.error(f"Error fetching or processing chunk: {chunk}\n{e}")

        logger.info(f"Processed {len(deck_tallies)} deck(s) out of {total_decks}.")
        return deck_tallies

    @staticmethod
    def export_decklists_to_csv(deck_tallies: List[DeckWildcardTally], output_file: str):
        """
        Exports a list of DeckWildcardTally objects to a CSV file.

        :param deck_tallies: List of DeckWildcardTally objects to be exported.
        :param output_file: Path to the output CSV file.
        """
        logger.info(f"Exporting data to CSV: {output_file}")
        fieldnames = [field for field in DeckWildcardTally.__dataclass_fields__.keys()]

        try:
            with open(output_file, mode='w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for tally in deck_tallies:
                    writer.writerow(asdict(tally))

            logger.info(f"CSV successfully written to {output_file}")

        except Exception as e:
            logger.error(f"An error occurred while writing to CSV: {e}")

    @staticmethod
    def export_cards_to_csv(collection: CollectionWildcardTally, output_file: str):
        """
        Exports the cards from the CollectionWildcardTally to a CSV file.

        :param collection: The CollectionWildcardTally object containing the cards.
        :param output_file: Path to the output CSV file.
        """
        logger.info(f"Exporting card collection to CSV: {output_file}")
        fieldnames = ['max_quantity', 'name',] + [field for field in Card.__dataclass_fields__.keys() if
                                          field not in ['max_quantity', 'name']]

        try:
            with open(output_file, mode='w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for card in collection.cards.values():
                    card_data = asdict(card)
                    writer.writerow(card_data)

            logger.info(f"Card collection successfully written to {output_file}")

        except Exception as e:
            logger.error(f"An error occurred while writing to CSV: {e}")


def main():
    """
    Main entry point for the script.
    """
    fetcher = DeckDataFetcher()
    all_deck_data = fetcher.scan_decklists_from_profile(start_page=1, end_page=23)
    logger.info(f"Collected {len(all_deck_data)} deck(s) from pages 1-5.")
    rarity_data = fetcher.retrieve_and_process_deck_data(all_deck_data)
    fetcher.export_decklists_to_csv(rarity_data, "deck_data.csv")
    fetcher.export_cards_to_csv(fetcher.historic_brawl_wildcard_tally, "brawl_card_data.csv")
    fetcher.export_cards_to_csv(fetcher.standard_wildcard_tally, "standard_card_data.csv")


if __name__ == "__main__":
    main()
