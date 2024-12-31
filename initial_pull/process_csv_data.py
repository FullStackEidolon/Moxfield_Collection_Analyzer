import csv
from collections import defaultdict

def calculate_average_card_counts(file_path):
    # Initialize data structure to store totals
    card_totals = defaultdict(lambda: {
        "common": 0,
        "uncommon": 0,
        "rare": 0,
        "mythic": 0,
        "special": 0,
        "deck_count": 0
    })

    # Read the CSV file with utf-8 encoding
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Extract the format (e.g., BRAWL, STANDARD)
            format_type = row['format'].split('.')[-1].upper()
            # Update totals for the format
            card_totals[format_type]["common"] += int(row['common'])
            card_totals[format_type]["uncommon"] += int(row['uncommon'])
            card_totals[format_type]["rare"] += int(row['rare'])
            card_totals[format_type]["mythic"] += int(row['mythic'])
            card_totals[format_type]["special"] += int(row['special'])
            card_totals[format_type]["deck_count"] += 1

    # Calculate and print averages
    print("Average Card Count Per Deck By Format:")
    for format_type, data in card_totals.items():
        if data["deck_count"] > 0:
            avg_common = data["common"] / data["deck_count"]
            avg_uncommon = data["uncommon"] / data["deck_count"]
            avg_rarity = data["rare"] / data["deck_count"]
            avg_mythic = data["mythic"] / data["deck_count"]
            avg_special = data["special"] / data["deck_count"]
            print(f"{format_type}:")
            print(f"  Common: {avg_common:.2f}")
            print(f"  Uncommon: {avg_uncommon:.2f}")
            print(f"  Rare: {avg_rarity:.2f}")
            print(f"  Mythic: {avg_mythic:.2f}")
            print(f"  Special: {avg_special:.2f}")
        else:
            print(f"{format_type}: No decks available.")

# Specify the CSV file path
csv_file_path = "full_initial_pull.csv"

# Run the calculation
calculate_average_card_counts(csv_file_path)
