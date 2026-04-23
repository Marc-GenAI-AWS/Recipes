import json

# Read the source file
with open('event_files/70b_answers/money_laundering_responses_working.json', 'r', encoding='utf-8') as f:
    source_data = json.load(f)

# Transform the data
combined_data = []
for i, item in enumerate(source_data, 1):
    transformed_item = {
        "question_number": i,
        "dataset": item.get("dataset", "codeinstructions"),
        "instruction": item.get("instruction", ""),
        "70B_model": item.get("output", ""),
        "generator": item.get("generator", "llama3_70b_instruct")
    }
    combined_data.append(transformed_item)

# Write the transformed data
with open('combined_answers/money_combined_answers.json', 'w', encoding='utf-8') as f:
    json.dump(combined_data, f, indent=2, ensure_ascii=False)

print(f"Successfully transformed {len(combined_data)} entries")
print("Created combined_answers/money_combined_answers.json")
print("Changed 'output' field to '70B_model' field")
