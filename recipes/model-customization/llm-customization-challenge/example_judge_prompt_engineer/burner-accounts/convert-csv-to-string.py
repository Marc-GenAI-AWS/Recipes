import pandas as pd


def generate_aws_update_command(file_path: str, table_name: str, leaderboard_id: str, output_path: str) -> None:
    # Read all columns as strings
    df = pd.read_csv(file_path, dtype=str)
    first_column_name = df.columns[0]

    # Clean and extract IDs
    ids = df[first_column_name].str.strip().tolist()

    # Format the ID list for the AWS CLI
    formatted_ids = ', '.join(f'"{i}"' for i in ids)

    # Construct the AWS command
    command = f"""aws dynamodb update-item \\
--table-name {table_name} \\
--key '{{"leaderboardId": {{"S": "{leaderboard_id}"}}}}' \\
--update-expression "ADD burnerAccountList :accountIds" \\
--expression-attribute-values '{{":accountIds": {{"SS": [{formatted_ids}]}}}}'"""

    # Save to text file for easy copy-paste
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(command)

    print(f"AWS command saved to {output_path}")

print(generate_aws_update_command('burner-accounts\data\disney-burners.csv', 'leaderboard', 'disney-aws-ai-league', 'burner-accounts\strings\disney-burners-converted.txt'))
