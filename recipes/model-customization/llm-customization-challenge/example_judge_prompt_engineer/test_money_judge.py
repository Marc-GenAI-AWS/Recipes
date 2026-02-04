#!/usr/bin/env python3
import json
import os

def test_money_data():
    """Test loading money combined answers data."""
    combined_file = "event_files/combined_answers/money_combined_answers.json"
    
    print(f"Testing file: {combined_file}")
    print(f"File exists: {os.path.exists(combined_file)}")
    
    if not os.path.exists(combined_file):
        print("File not found!")
        return
    
    with open(combined_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Total entries: {len(data)}")
    
    # Filter out entries with missing responses
    valid_data = []
    for item in data:
        if ("No matching" not in item.get('70b', '') and 
            "No fine-tuned" not in item.get('finetuned', '') and
            item.get('70b', '').strip() and 
            item.get('finetuned', '').strip()):
            valid_data.append(item)
    
    print(f"Valid entries with both responses: {len(valid_data)}")
    
    # Show first few entries
    for i, item in enumerate(data[:3]):
        print(f"\nEntry {i+1}:")
        print(f"  Instruction: {item['instruction'][:100]}...")
        print(f"  70B: {item['70b'][:50]}...")
        print(f"  Finetuned: {item['finetuned'][:50]}...")

if __name__ == "__main__":
    test_money_data()
