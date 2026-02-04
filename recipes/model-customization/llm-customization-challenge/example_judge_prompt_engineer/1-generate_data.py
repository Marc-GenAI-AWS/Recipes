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

        self.prompt = """You are a world-class LLM data engineer crafting training data for a high-performing Llama 3.2 3B healthcare assistant. The goal is to generate outputs that are ideal for use in real-world patient education, digital outreach, or clinical care guidance—maintaining exceptional clarity, empathy, and usability for any patient or caregiver audience.

        Your task:
        Given the use case provided, write exactly five unique JSONL lines for instruction-tuning.

        Requirements:

        Each JSONL line must be valid JSON with instruction, context, and response.

        Instructions should be realistic and challenging, reflecting real clinical or patient-education situations involving ambiguity, diverse patient needs, or complex reasoning. Include any necessary patient background, demographic details, or scenario constraints directly within the instruction itself.

        Context should always be an empty string ("").

        Each response must:

        Be specifically tailored to the scenario and any patient/caregiver details provided in the instruction.

        Offer clear, supportive, and practical guidance—including next steps, cautionary advice, or checkpoints as appropriate.

        Demonstrate warmth and trustworthiness, using approachable language for general populations (avoiding jargon or unnecessary technical detail).

        Be highly readable and logically organized (using lists, bullet points, or sections for clarity as needed), always ready for direct communication with lay audiences or patients.

        Remain concise (ideally under 250 tokens) yet comprehensive and directly suited to real patient-facing material.

        Avoid meta commentary, repetition, or generic summaries. Ensure every example varies in focus, tone, and structure to expose the model to a wide range of patient communication scenarios.

        Use only standard ASCII characters.

        Use case:
        {USE CASE HERE}

        Return exactly five lines. Output only standard JSONL (one object per line); no explanation or markdown.

        Format:
        {{
        "instruction": "...",
        "context": "",
        "response": "..."
        }}"""

    def generate_training_data(self):
        """Generate 5 JSONL training examples using Claude Sonnet 4"""
        # Format the prompt with actual use case
        formatted_prompt = self.prompt.replace("{USE CASE HERE}", self.use_case)
        
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
DOMAIN = "uhg"  # Change this to: "lilly", "gaming", "money", or "uhg"

generator = DataGenerator(domain_key=DOMAIN)

# Debug: Print what was loaded
print(f"Use case loaded: {generator.use_case[:100]}...")
print(f"Judging criteria loaded: {generator.judging_criteria[:100]}...")

# Generate and save training data to file - full generation
print("Starting data generation...")
for i in range(40):  # Generate 40 batches (200 examples total)
    print(f"Generating batch {i+1}/40...")
    generator.save_training_data(DOMAIN)