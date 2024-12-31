import csv
from collections import defaultdict
from data_pull import Rarity

def analyze_card_types(file_paths):
    """
    Analyzes the card rarities for each collection and counts the maximum quantity of cards for each rarity.

    :param file_paths: List of file paths to CSVs to analyze.
    :return: A dictionary where each key is a collection name, and the value is a dictionary
             of rarities and their maximum quantities.
    """
    collection_analysis = {}

    for file_path in file_paths:
        collection_name = file_path.split('/')[-1].replace('_card_data.csv', '').capitalize()
        rarity_counts = defaultdict(int)

        with open(file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                rarity = Rarity.from_string(row['rarity'].split(".")[-1]).value
                count = int(row['max_quantity'])
                rarity_counts[rarity] += count

        collection_analysis[collection_name] = dict(rarity_counts)

    return collection_analysis

# File paths to the CSVs
file_paths = ["brawl_card_data.csv", "standard_card_data.csv"]

# Analyze card rarities
analysis_result = analyze_card_types(file_paths)

# Print results
for collection, rarity_counts in analysis_result.items():
    print(f"\nCollection: {collection}")
    for rarity, count in rarity_counts.items():
        print(f"  {rarity}: {count}")
