#!/usr/bin/env python3
import json
import os

def load_combined_answers(use_case: str):
    """Load the combined answers file."""
    combined_file = f"event_files/combined_answers/{use_case}_combined_answers.json"
    
    print(f"Looking for file: {combined_file}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"File exists: {os.path.exists(combined_file)}")
    
    if not os.path.exists(combined_file):
        raise FileNotFoundError(f"Combined answers file not found: {combined_file}")
    
    with open(combined_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Successfully loaded {len(data)} items")
    return data

if __name__ == "__main__":
    try:
        data = load_combined_answers("money")
        print("SUCCESS: File loaded correctly")
        if data:
            print(f"First item: {data[0]}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
