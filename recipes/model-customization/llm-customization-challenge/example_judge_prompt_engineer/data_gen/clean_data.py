import json
import re

def clean_jsonl_data(input_file, output_file):
    """
    Clean JSONL data by:
    1. Setting context field to empty string
    2. Removing escape sequences like \n, \t, \u00b0, etc.
    """
    
    cleaned_data = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                # Parse JSON line
                data = json.loads(line.strip())
                
                # Set context to empty string
                if 'context' in data:
                    data['context'] = ""
                
                # Clean escape sequences from all string fields
                for key, value in data.items():
                    if isinstance(value, str):
                        # Remove common escape sequences
                        cleaned_value = value.replace('\\n', ' ')  # newlines to spaces
                        cleaned_value = cleaned_value.replace('\\t', ' ')  # tabs to spaces
                        cleaned_value = cleaned_value.replace('\\r', '')   # carriage returns
                        
                        # Remove unicode escape sequences like \u00b0
                        cleaned_value = re.sub(r'\\u[0-9a-fA-F]{4}', '', cleaned_value)
                        
                        # Remove other backslash sequences
                        cleaned_value = re.sub(r'\\[^"]', '', cleaned_value)
                        
                        # Clean up multiple spaces
                        cleaned_value = re.sub(r'\s+', ' ', cleaned_value).strip()
                        
                        data[key] = cleaned_value
                
                cleaned_data.append(data)
                
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue
    
    # Write cleaned data to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        for data in cleaned_data:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')
    
    print(f"Cleaned {len(cleaned_data)} records")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    import os
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    input_file = os.path.join(script_dir, "bayer_data_gen.jsonl")
    output_file = os.path.join(script_dir, "bayer_data_gen_cleaned2.jsonl")
    
    print(f"Looking for input file: {input_file}")
    print(f"Will save output to: {output_file}")
    
    clean_jsonl_data(input_file, output_file)
    
    # Show a sample of the cleaned data
    print("\nSample of cleaned data:")
    with open(output_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < 2:  # Show first 2 records
                data = json.loads(line)
                print(f"\nRecord {i+1}:")
                print(f"Instruction: {data['instruction'][:100]}...")
                print(f"Context: '{data['context']}'")
                print(f"Response: {data['response'][:100]}...")
