#!/usr/bin/env python3
"""
Script to query finetuned model ARNs with their corresponding questions
and update the 70B answer files with the new "finetuned" responses.
"""

import json
import boto3
import os
from typing import Dict, List, Tuple
import time

# Model ARN mappings
MODEL_ARNS = {
    "lilly": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/lilly-endpoint",
    "uhg": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/bayer-value-prop-assistant-20251013-212359",
    "money": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/bayer-value-prop-assistant-20251013-215929",
    "gaming": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/bayer-value-prop-assistant-20251013-223013"
}

# File mappings based on usecase_map.py logic
FILE_MAPPINGS = {
    "lilly": {
        "questions": "event_files/questions/lilly_questions.txt",
        "answers": "event_files/70b_answers/lilly_patient_edu_responses_working.json"
    },
    "uhg": {
        "questions": "event_files/questions/uhg_questions.txt", 
        "answers": "event_files/70b_answers/uhg_patient_edu_responses_working.json"
    },
    "money": {
        "questions": "event_files/questions/money_laundering_questions.txt",
        "answers": "event_files/70b_answers/money_laundering_responses_working.json"
    },
    "gaming": {
        "questions": "event_files/questions/responsible_gaming_questions.txt",
        "answers": "event_files/70b_answers/responsible_gaming_responses.json"
    }
}

class ModelQueryManager:
    def __init__(self):
        """Initialize the SageMaker runtime client."""
        self.sagemaker_runtime = boto3.client('sagemaker-runtime', region_name='us-west-2')
        
    def read_questions(self, questions_file: str) -> List[str]:
        """Read questions from a text file."""
        questions = []
        try:
            with open(questions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):  # Skip empty lines and comments
                        # Remove question numbering if present (e.g., "1.", "2.", etc.)
                        if line[0].isdigit() and '.' in line[:5]:
                            question = line.split('.', 1)[1].strip()
                        else:
                            question = line
                        questions.append(question)
        except FileNotFoundError:
            print(f"Warning: Questions file not found: {questions_file}")
        except Exception as e:
            print(f"Error reading questions file {questions_file}: {e}")
        
        return questions
    
    def query_model(self, endpoint_name: str, question: str, usecase: str) -> str:
        """Query a SageMaker endpoint with a question."""
        try:
            # Create the prompt based on the usecase
            prompt = self._create_prompt(question, usecase)
            
            # Prepare the payload for the model
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 2048,
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "do_sample": True
                }
            }
            
            # Invoke the endpoint
            response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='application/json',
                Body=json.dumps(payload)
            )
            
            # Parse the response
            result = json.loads(response['Body'].read().decode())
            
            # Extract the generated text (format may vary by model)
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('generated_text', '').strip()
            elif 'generated_text' in result:
                return result['generated_text'].strip()
            else:
                return str(result)
                
        except Exception as e:
            print(f"Error querying model {endpoint_name}: {e}")
            return f"Error: {str(e)}"
    
    def _create_prompt(self, question: str, usecase: str) -> str:
        """Create an appropriate prompt based on the usecase."""
        if usecase == "money":
            return f"You are a money laundering expert who works for a bank. You are given a set of questions about money laundering and are expected to answer them in a way that is both accurate and concise. Scenario: {question}"
        elif usecase == "gaming":
            return f"You are a responsible gaming expert. Please provide guidance on the following scenario: {question}"
        elif usecase == "lilly":
            return f"You are a patient education expert. Please provide clear and helpful information about: {question}"
        elif usecase == "uhg":
            return f"You are a healthcare expert providing patient education. Please answer: {question}"
        else:
            return question
    
    def load_existing_answers(self, answers_file: str) -> List[Dict]:
        """Load existing 70B answers from JSON file."""
        try:
            with open(answers_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Answers file not found: {answers_file}")
            return []
        except Exception as e:
            print(f"Error loading answers file {answers_file}: {e}")
            return []
    
    def update_answers_with_finetuned(self, answers: List[Dict], finetuned_responses: List[str]) -> List[Dict]:
        """Add finetuned responses to the existing answer structure."""
        updated_answers = []
        
        for i, answer_entry in enumerate(answers):
            # Create a copy of the original entry
            updated_entry = answer_entry.copy()
            
            # Add the finetuned response if available
            if i < len(finetuned_responses):
                updated_entry['finetuned'] = finetuned_responses[i]
            else:
                updated_entry['finetuned'] = "No response available"
            
            updated_answers.append(updated_entry)
        
        return updated_answers
    
    def save_updated_answers(self, answers: List[Dict], answers_file: str):
        """Save the updated answers back to the JSON file."""
        try:
            # Create backup
            backup_file = answers_file.replace('.json', '_backup.json')
            if os.path.exists(answers_file):
                with open(answers_file, 'r', encoding='utf-8') as f:
                    original = f.read()
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(original)
                print(f"Backup created: {backup_file}")
            
            # Save updated file
            with open(answers_file, 'w', encoding='utf-8') as f:
                json.dump(answers, f, indent=2, ensure_ascii=False)
            print(f"Updated answers saved to: {answers_file}")
            
        except Exception as e:
            print(f"Error saving answers file {answers_file}: {e}")
    
    def process_usecase(self, usecase: str) -> bool:
        """Process a single usecase: query model and update answers."""
        print(f"\n{'='*50}")
        print(f"Processing usecase: {usecase}")
        print(f"{'='*50}")
        
        if usecase not in MODEL_ARNS or usecase not in FILE_MAPPINGS:
            print(f"Error: Usecase {usecase} not found in mappings")
            return False
        
        # Get file paths
        questions_file = FILE_MAPPINGS[usecase]["questions"]
        answers_file = FILE_MAPPINGS[usecase]["answers"]
        endpoint_name = MODEL_ARNS[usecase].split('/')[-1]  # Extract endpoint name from ARN
        
        print(f"Questions file: {questions_file}")
        print(f"Answers file: {answers_file}")
        print(f"Model endpoint: {endpoint_name}")
        
        # Read questions
        questions = self.read_questions(questions_file)
        if not questions:
            print(f"No questions found for {usecase}")
            return False
        
        print(f"Found {len(questions)} questions")
        
        # Load existing answers
        existing_answers = self.load_existing_answers(answers_file)
        if not existing_answers:
            print(f"No existing answers found for {usecase}")
            return False
        
        print(f"Found {len(existing_answers)} existing answers")
        
        # Query model for each question
        finetuned_responses = []
        for i, question in enumerate(questions):
            print(f"Querying question {i+1}/{len(questions)}...")
            response = self.query_model(endpoint_name, question, usecase)
            finetuned_responses.append(response)
            
            # Add a small delay to avoid overwhelming the endpoint
            time.sleep(1)
        
        # Update answers with finetuned responses
        updated_answers = self.update_answers_with_finetuned(existing_answers, finetuned_responses)
        
        # Save updated answers
        self.save_updated_answers(updated_answers, answers_file)
        
        print(f"Successfully processed {usecase}")
        return True
    
    def process_all_usecases(self):
        """Process all usecases."""
        print("Starting model query and answer update process...")
        print(f"Processing {len(MODEL_ARNS)} usecases: {list(MODEL_ARNS.keys())}")
        
        success_count = 0
        for usecase in MODEL_ARNS.keys():
            try:
                if self.process_usecase(usecase):
                    success_count += 1
            except Exception as e:
                print(f"Error processing {usecase}: {e}")
        
        print(f"\n{'='*50}")
        print(f"Process completed!")
        print(f"Successfully processed: {success_count}/{len(MODEL_ARNS)} usecases")
        print(f"{'='*50}")

def main():
    """Main function to run the model query and update process."""
    manager = ModelQueryManager()
    
    # You can process all usecases or individual ones
    # manager.process_all_usecases()
    
    # Or process individual usecases:
    # manager.process_usecase("money")
    # manager.process_usecase("lilly")
    # manager.process_usecase("uhg")
    # manager.process_usecase("gaming")
    
    # For now, let's process all
    manager.process_all_usecases()

if __name__ == "__main__":
    main()
