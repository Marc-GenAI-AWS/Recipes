#!/usr/bin/env python3
"""
Fine-tuned Model Response Generator
Reads questions from event_files/questions/[usecase]_questions.txt
Gets responses from a SageMaker endpoint
Saves responses in the same format as 70b_answers files
"""

import boto3
import json
import time
import os
from datetime import datetime
from typing import List, Dict

class FineTuneResponseGenerator:
    def __init__(self, region_name='us-west-2'):
        """Initialize SageMaker runtime client."""
        self.region_name = region_name
        self.sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=region_name)
        
    def load_questions(self, use_case: str) -> List[str]:
        """Load questions from the questions file."""
        # Map use case to question file
        question_files = {
            "uhg": "uhg_questions.txt",
            "lilly": "lilly_questions.txt", 
            "money": "money_laundering_questions.txt",
            "gaming": "responsible_gaming_questions.txt",
            "disney": "disney_questions.txt",
            "blueprint": "client_blueprint_questions.txt",
            "security": "security_questions.txt",  # Using bayer as placeholder for security
            "parsons": "parsons_questions.txt"
        }
        
        if use_case not in question_files:
            raise ValueError(f"Unknown use case: {use_case}. Available: {list(question_files.keys())}")
        
        questions_file = f"event_files/questions/{question_files[use_case]}"
        
        if not os.path.exists(questions_file):
            raise FileNotFoundError(f"Questions file not found: {questions_file}")
        
        questions = []
        with open(questions_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    # Remove numbering if present (e.g., "1. Question" -> "Question")
                    if line[0].isdigit() and '.' in line[:5]:
                        question = line.split('.', 1)[1].strip()
                    else:
                        question = line
                    questions.append(question)
        
        print(f"Loaded {len(questions)} questions from {questions_file}")
        return questions
    
    def create_prompt(self, question: str, use_case: str) -> str:
        """Create the prompt for the fine-tuned model."""
        # Fine-tuned models don't need role prefixes since they were trained on domain-specific data
        return question
    
    def get_model_response(self, endpoint_name: str, prompt: str, max_retries: int = 3) -> str:
        """Get response from the SageMaker endpoint."""
        
        # Prepare the payload for the model
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 500,
                "temperature": 0.7,
                "top_p": 0.9,
                "do_sample": True,
                "stop": ["<|eot_id|>", "</s>"]
            }
        }
        
        for attempt in range(max_retries):
            try:
                print(f"  Calling endpoint (attempt {attempt + 1}/{max_retries})...")
                
                response = self.sagemaker_runtime.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType='application/json',
                    Body=json.dumps(payload)
                )
                
                result = json.loads(response['Body'].read().decode())
                
                # Extract the generated text
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get('generated_text', '')
                elif isinstance(result, dict):
                    generated_text = result.get('generated_text', result.get('outputs', ''))
                else:
                    generated_text = str(result)
                
                # Clean up the response - remove the original prompt if it's included
                if prompt in generated_text:
                    generated_text = generated_text.replace(prompt, '').strip()
                
                # Clean up newlines and other escape characters
                generated_text = generated_text.replace('\\n', ' ').replace('\n', ' ')
                generated_text = generated_text.replace('\\t', ' ').replace('\t', ' ')
                generated_text = generated_text.replace('\\r', '').replace('\r', '')
                
                # Clean up multiple spaces
                import re
                generated_text = re.sub(r'\s+', ' ', generated_text).strip()
                
                return generated_text
                
            except Exception as e:
                print(f"    Error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return f"Error generating response: {e}"
    
    def generate_responses(self, endpoint_name: str, use_case: str, output_file: str = None) -> str:
        """Generate responses for all questions and save to JSON file."""
        
        print(f"Generating responses for use case: {use_case}")
        print(f"Using endpoint: {endpoint_name}")
        
        # Load questions
        questions = self.load_questions(use_case)
        
        # Prepare output file
        if output_file is None:
            output_file = f"event_files/finetune_answers/{use_case}_finetune_answers.json"
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        responses = []
        
        print(f"\nProcessing {len(questions)} questions...")
        
        for i, question in enumerate(questions, 1):
            print(f"\nQuestion {i}/{len(questions)}: {question[:80]}...")
            
            # Create prompt
            prompt = self.create_prompt(question, use_case)
            
            # Get response from model
            response_text = self.get_model_response(endpoint_name, prompt)
            
            # Create response object in the same format as 70b responses
            response_obj = {
                "dataset": "codeinstructions",
                "instruction": prompt,
                "output": response_text,
                "generator": f"llama3_2_3b_finetune_{use_case}"
            }
            
            responses.append(response_obj)
            
            # Save progress every 10 questions
            if i % 10 == 0:
                print(f"  Saving progress... ({i}/{len(questions)} completed)")
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(responses, f, indent=2, ensure_ascii=False)
        
        # Save final results
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(responses, f, indent=2, ensure_ascii=False)
        
        print(f"\nCompleted! Generated {len(responses)} responses")
        print(f"Results saved to: {output_file}")
        
        return output_file

def main():
    """Main function to run the response generation."""
    print("=" * 60)
    print("FINE-TUNED MODEL RESPONSE GENERATOR")
    print("=" * 60)
    
    # Configuration - Update these values
    ENDPOINT_NAME = "gaming-instruct-endpoint"  # Replace with your endpoint name
    USE_CASE = "gaming"  # Change this to match your use case
    
    # Optional: specify custom output file
    OUTPUT_FILE = None  # Will auto-generate if None
    
    print(f"Endpoint: {ENDPOINT_NAME}")
    print(f"Use case: {USE_CASE}")
    
    try:
        # Initialize generator
        generator = FineTuneResponseGenerator()
        
        # Generate responses
        output_file = generator.generate_responses(
            endpoint_name=ENDPOINT_NAME,
            use_case=USE_CASE,
            output_file=OUTPUT_FILE
        )
        
        print(f"\n" + "=" * 60)
        print("GENERATION COMPLETE")
        print("=" * 60)
        print(f"Output file: {output_file}")
        
        # Show sample of first response
        with open(output_file, 'r', encoding='utf-8') as f:
            responses = json.load(f)
            if responses:
                print(f"\nSample response:")
                print(f"Question: {responses[0]['instruction']}")
                print(f"Answer: {responses[0]['output'][:200]}...")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
