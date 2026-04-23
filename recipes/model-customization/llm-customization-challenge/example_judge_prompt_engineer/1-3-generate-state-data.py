import boto3
import json
from pathlib import Path

class DataGenerator:
    def __init__(self, region_name='us-west-2', domain_key=None):
        """Initialize Claude Sonnet 4 for response ranking"""
        if domain_key is None:
            raise ValueError("domain_key must be specified (e.g., 'lilly', 'gaming', 'money', 'uhg')")
        
        self.region = region_name
        self.domain_key = domain_key
        self.model_id = "arn:aws:bedrock:us-west-2:<AWS_ACCOUNT_ID>:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region_name)
        
        # Load judging criteria
        judge_prompts_subdir = Path('event_files/judge_prompts')
        judge_prompts_files = list(judge_prompts_subdir.rglob(f'*{domain_key}*'))
        
        self.judging_criteria = ""
        print(f"Looking for judge prompts with domain_key: {domain_key}")
        print(f"Found judge prompt files: {[f.name for f in judge_prompts_files]}")
        for file in judge_prompts_files:
            print(f"Checking file: {file.name}")
            if domain_key in file.name:
                print(f"Found matching judge prompt file: {file}")
                with open(file, 'r', encoding='utf-8') as f:
                    self.judging_criteria = f.read()
                    break
        
        if not self.judging_criteria:
            print("WARNING: No judging criteria loaded!")

        # Load use case
        usecases_subdir = Path('event_files/usecases')
        usecases_files = list(usecases_subdir.rglob(f'*{domain_key}*'))
        
        self.use_case = ""
        print(f"Looking for use case files with domain_key: {domain_key}")
        print(f"Found use case files: {[f.name for f in usecases_files]}")
        for file in usecases_files:
            print(f"Checking file: {file.name}")
            if domain_key in file.name:
                print(f"Found matching use case file: {file}")
                with open(file, 'r', encoding='utf-8') as f:
                    self.use_case = f.read()
                    break
        
        if not self.use_case:
            print("WARNING: No use case loaded!")

        # The prompt will be constructed from loaded judging criteria and use case

    def generate_training_data(self):
        """Generate 5 JSONL training examples using Claude Sonnet 4"""
        # Use the loaded judging criteria as the prompt
        formatted_prompt = f"""Generate 5 training examples for fine-tuning a credit risk assistant model. Each example should be in JSONL format with the structure:
{{"instruction": "question about credit risk", "context": "relevant context if needed", "response": "expert response"}}

Use case context:
{self.use_case}

Generate realistic credit risk scenarios and expert responses that would help train a model to assist institutional risk, operations, and investment teams. Focus on portfolio credit exposure, liquidity risk, and counterparty stability assessments.

Each training example should demonstrate the type of expert analysis described in the use case. Make the scenarios diverse and realistic.

Output exactly 5 lines of valid JSONL (one JSON object per line):"""
        
        # Prepare the request body for Claude
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "messages": [
                {
                    "role": "user",
                    "content": formatted_prompt
                }
            ]
        }
        
        try:
            # Call Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            generated_content = response_body['content'][0]['text']
            
            return generated_content
            
        except Exception as e:
            print(f"Error generating data: {e}")
            return None
    
    def save_training_data(self, domain_key):
        """Generate and save training data to a JSONL file"""
        # Generate the training data
        generated_content = self.generate_training_data()
        
        if generated_content is None:
            print("Failed to generate training data")
            return False
        
        # Create filename based on domain key
        filename = f"data_gen/{domain_key}_data_gen.jsonl"
        
        # Ensure the data_gen directory exists
        Path("data_gen").mkdir(exist_ok=True)
        
        try:
            # Clean up the generated content - remove extra blank lines
            lines = generated_content.strip().split('\n')
            clean_lines = [line.strip() for line in lines if line.strip()]
            
            # Validate and clean each JSON line
            valid_json_lines = []
            for line in clean_lines:
                try:
                    # Clean unicode characters that break JSONL
                    cleaned_line = line.replace('→', '->').replace('—', '-').replace('"', '"').replace('"', '"')
                    
                    # Try to parse as JSON to validate
                    parsed_json = json.loads(cleaned_line)
                    
                    # Re-serialize to ensure proper formatting
                    clean_json = json.dumps(parsed_json, ensure_ascii=True, separators=(',', ':'))
                    valid_json_lines.append(clean_json)
                    
                except json.JSONDecodeError as e:
                    # Skip invalid JSON lines
                    print(f"Skipping invalid JSON line (position {e.pos}): {line[:100]}...")
                    continue
            
            # Append to existing file or create new one
            with open(filename, 'a', encoding='utf-8') as f:
                for line in valid_json_lines:
                    f.write(line + '\n')
            
            print(f"Training data saved to {filename}")
            return True
            
        except Exception as e:
            print(f"Error saving data to file: {e}")
            return False


# Choose which domain to generate data for
DOMAIN = "state"  # Change this to: "lilly", "gaming", "money", or "uhg"

generator = DataGenerator(domain_key=DOMAIN)

# Debug: Print what was loaded
print(f"Use case loaded: {generator.use_case[:100]}...")
print(f"Judging criteria loaded: {generator.judging_criteria[:100]}...")

# Generate and save training data to file - full generation
print("Starting data generation...")
for i in range(40):  # Generate 40 batches (200 examples total)
    print(f"Generating batch {i+1}/40...")
    generator.save_training_data(DOMAIN)