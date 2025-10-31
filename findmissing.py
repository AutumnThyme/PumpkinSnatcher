import json

# Path to your JSON file
filename = "data.json"

# Load the JSON data from the file
with open(filename, "r") as f:
    data = json.load(f)

# Get claimed numbers
claimed = set(data.get("claimed", []))

# Compute missing numbers (0–100 inclusive)
missing = sorted(set(range(101)) - claimed)

# Print results cleanly
print("Missing numbers (0–100):")
print(", ".join(map(str, missing)))
print(f"\nTotal missing: {len(missing)}")
