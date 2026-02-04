#!/usr/bin/env python3
import os
import json

print("Testing judge script...")
print(f"Current working directory: {os.getcwd()}")

# Test if the file exists
use_case = "money"
combined_file = f"event_files/combined_answers/{use_case}_combined_answers.json"
print(f"Looking for file: {combined_file}")
print(f"File exists: {os.path.exists(combined_file)}")

if os.path.exists(combined_file):
    try:
        with open(combined_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully loaded {len(data)} items from JSON file")
        print(f"First item keys: {list(data[0].keys()) if data else 'No items'}")
    except Exception as e:
        print(f"Error loading JSON: {e}")
else:
    print("File not found!")
    print("Contents of event_files/combined_answers/:")
    if os.path.exists("event_files/combined_answers/"):
        for file in os.listdir("event_files/combined_answers/"):
            print(f"  {file}")
    else:
        print("  Directory doesn't exist!")
