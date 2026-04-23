import json

try:
    with open('event_files/combined_answers/uhg_combined_answers.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"✅ JSON is valid!")
    print(f"Total entries: {len(data)}")
    print(f"Keys in each entry: {list(data[0].keys())}")
    print(f"Sample instruction: {data[0]['instruction'][:80]}...")
    
except json.JSONDecodeError as e:
    print(f"❌ JSON Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
