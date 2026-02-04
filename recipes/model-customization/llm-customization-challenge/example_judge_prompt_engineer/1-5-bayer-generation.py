import boto3
import json
import time
from pathlib import Path
from botocore.exceptions import ReadTimeoutError, ClientError

class DataGenerator:
    def __init__(self, region_name='us-west-2', domain_key=None):
        """Initialize Claude Sonnet 4 for response ranking"""
        if domain_key is None:
            raise ValueError("domain_key must be specified (e.g., 'bayer', 'wealth', 'gaming', 'money', 'uhg')")
        
        self.region = region_name
        self.domain_key = domain_key
        self.model_id = "arn:aws:bedrock:us-west-2:<AWS_ACCOUNT_ID>:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
        # Configure client with longer timeout and retry settings
        config = boto3.session.Config(
            read_timeout=300,  # 5 minutes
            connect_timeout=60,  # 1 minute
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region_name, config=config)
        
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

        # Note: We intentionally do NOT load the test questions to prevent data contamination
        # The model should learn general patterns, not memorize specific test cases

        self.prompt = """You are a world-class LLM data engineer creating elite instruction-tuning data for a Llama 3.2 3B model. The goal is to enable this smaller model to outperform the Llama 3.2 70B model on pharmaceutical communications and value proposition tasks, where accuracy, empathy, brand alignment, and regulatory compliance matter more than verbosity or generic messaging.

Your task:
Generate exactly five unique JSONL lines of expert-quality data for fine-tuning based on the provided Bayer Nubeqa use case.

Requirements
Each JSONL line must be valid JSON with these keys:

instruction: A realistic pharmaceutical communications scenario that mirrors the types of messaging challenges a Bayer team would encounter—these may involve value propositions, audience-specific communications, brand messaging, clinical explanations, patient education, or stakeholder engagement around Nubeqa prostate cancer treatment.

context: Always an empty string "" (for schema consistency).

response: The ideal pharmaceutical communications response—accurate, empathetic, brand-aligned, and deeply actionable. Responses should deliver clear messaging that connects clinical science to human purpose, acknowledges audience needs, maintains regulatory compliance, and reflects Bayer's mission of helping men live longer and love the life they live.

Create prompts and responses that fit authentic pharmaceutical communications contexts, demanding accurate medical knowledge, empathetic communication, brand consistency, and regulatory awareness. Responses should synthesize clinical expertise with human understanding, referencing specific audience needs, emotional considerations, and compliant messaging practices.

Instruction Guidelines

Vary audience types (healthcare professionals, patients, caregivers, policymakers, internal teams), communication formats, and messaging objectives.

Incorporate challenges such as value proposition development, clinical education, patient support, brand positioning, competitive differentiation, regulatory compliance, and emotional engagement.

Ensure each prompt presents a realistic communications scenario that demands accurate, empathetic, and brand-aligned messaging, not generic pharmaceutical information.

Model realistic situations that pharmaceutical communications teams encounter when translating clinical science into meaningful, compliant messages.

Response Guidelines

Deliver deeply accurate and empathetic responses that reflect clinical facts and acknowledge audience emotions and needs.

Provide clear messaging with scientific accuracy, emotional resonance, and practical application.

Use language that builds trust and confidence while maintaining regulatory compliance and brand consistency.

Connect Nubeqa's clinical benefits to human impact—quality of life, family time, hope, and living fully.

Focus on Bayer's brand mission of helping men live longer and love the life they live.

Only use standard ASCII characters (no Unicode, smart quotes, or formatting symbols).

Output Format
Return exactly five valid JSONL lines, each on a separate line, with the following structure:
{"instruction": "...", "context": "", "response": "..."}"""

    def generate_training_data(self):
        """Generate 5 JSONL training examples using Claude Sonnet 4"""
        # Format the prompt with actual use case, judging criteria, and sample questions
        formatted_prompt = f"""{self.prompt}

Use Case Context:
{self.use_case}

Scenario Types to Create (generate diverse, original scenarios):
- Internal team communications and motivational messages
- Healthcare professional education and value propositions
- Patient and caregiver support and education
- Policymaker and stakeholder communications
- Brand positioning and competitive differentiation
- Clinical explanation and treatment guidance
- Emotional support and empathy-driven messaging

Quality Standards (ensure responses meet these criteria):
{self.judging_criteria}

Generate responses that would score 8.0+ on the evaluation criteria above, focusing on accuracy and regulatory soundness, audience relevance, brand alignment, creativity, and empathy. Ensure responses feel like they come from a trusted pharmaceutical communications professional who understands both clinical science and human impact. Create entirely original scenarios - do not reference or copy any existing test questions."""
        
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
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                print(f"API call attempt {attempt + 1}/{max_retries}")
                
                # Call Bedrock
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body)
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                generated_content = response_body['content'][0]['text']
                
                return generated_content
                
            except (ReadTimeoutError, ClientError) as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:  # Don't sleep on last attempt
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print(f"All {max_retries} attempts failed")
                    return None
            except Exception as e:
                print(f"Unexpected error generating data: {e}")
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
DOMAIN = "bayer"  # Set to Bayer Nubeqa domain

generator = DataGenerator(domain_key=DOMAIN)

# Debug: Print what was loaded
print(f"Use case loaded: {generator.use_case[:100]}...")
print(f"Judging criteria loaded: {generator.judging_criteria[:100]}...")
print("Test questions intentionally NOT loaded to prevent data contamination")

# Generate and save training data to file - full generation
print("Starting Bayer Nubeqa data generation...")
for i in range(40):  # Generate 40 batches (200 examples total)
    print(f"Generating batch {i+1}/40...")
    success = generator.save_training_data(DOMAIN)
    
    if success:
        print(f"Batch {i+1} completed successfully")
    else:
        print(f"Batch {i+1} failed - continuing with next batch")
    
    # Small delay between batches to avoid overwhelming the API
    if i < 39:  # Don't sleep after the last batch
        time.sleep(1)
