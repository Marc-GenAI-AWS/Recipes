import json
import os

# Test if we can read the file
input_file = "uhg_data_gen.jsonl"
print(f"Current directory: {os.getcwd()}")
print(f"Looking for file: {input_file}")
print(f"File exists: {os.path.exists(input_file)}")

if os.path.exists(input_file):
    print("File found! Reading first line...")
    with open(input_file, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        print(f"First line: {first_line[:100]}...")
        
        # Try to parse it
        try:
            data = json.loads(first_line)
            print(f"Keys in data: {list(data.keys())}")
            print(f"Context field: '{data.get('context', 'NOT FOUND')}'")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
else:
    print("File not found!")
    print("Files in current directory:")
    for f in os.listdir('.'):
        print(f"  {f}")
