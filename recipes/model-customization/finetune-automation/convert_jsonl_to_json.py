import json
import os
from pathlib import Path

def convert_jsonl_to_json(input_file, output_file):
    """
    Convert a JSONL file to a traditional JSON file.
    
    Args:
        input_file (str): Path to the input JSONL file
        output_file (str): Path to the output JSON file
    """
    print(f"Converting {input_file} to {output_file}")
    
    # Read JSONL file and parse each line as JSON
    data = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                json_obj = json.loads(line.strip())
                data.append(json_obj)
            except json.JSONDecodeError as e:
                print(f"Error parsing line: {e}")
    
    # Write the combined data as a JSON array to the output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Conversion complete. {len(data)} records written to {output_file}")

if __name__ == "__main__":
    # Get the project root directory
    root_dir = Path(__file__).parent
    
    # Define input and output file paths
    input_file = os.path.join(root_dir, "usecase_data", "patient_care_plan", "patient_care_plan_dialog_0619_1415.jsonl")
    output_file = os.path.join(root_dir, "patient_care_plan_dialog_0619_1415.json")
    
    convert_jsonl_to_json(input_file, output_file)
