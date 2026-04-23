import json
import os

# Read the original file
input_file = "event_files/70b_answers/money_laundering_responses_working.json"
output_dir = "combined_answers"
output_file = os.path.join(output_dir, "money_combined_answers.json")

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Load and transform the data
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Transform the structure
combined_data = []
for i, item in enumerate(data, 1):
    transformed_item = {
        "question_number": i,
        "dataset": item.get("dataset", "codeinstructions"),
        "instruction": item.get("instruction", ""),
        "70B_model": item.get("output", ""),
        "generator": item.get("generator", "llama3_70b_instruct")
    }
    combined_data.append(transformed_item)

# Save the transformed data
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(combined_data, f, indent=2, ensure_ascii=False)

print(f"Successfully created {output_file}")
print(f"Transformed {len(combined_data)} responses")
print("Changed 'output' field to '70B_model' field")
