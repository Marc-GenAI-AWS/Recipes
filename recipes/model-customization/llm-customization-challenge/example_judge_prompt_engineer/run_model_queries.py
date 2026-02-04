#!/usr/bin/env python3
"""
Simplified script to query finetuned model ARNs and update answer files.
Uses config.py for all configuration settings.
"""

import json
import boto3
import os
import time
from typing import Dict, List
from config import MODEL_ARNS, FILE_MAPPINGS, AWS_REGION, MODEL_PARAMETERS, DELAY_BETWEEN_QUERIES, CREATE_BACKUPS

class ModelQueryManager:
    def __init__(self):
        """Initialize the SageMaker runtime client."""
        self.sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=AWS_REGION)
        
    def read_questions(self, questions_file: str) -> List[str]:
        """Read questions from a text file."""
        questions = []
        try:
            with open(questions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Remove question numbering if present
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
    
    def create_prompt(self, question: str, usecase: str) -> str:
        """Create an appropriate prompt based on the usecase."""
        prompts = {
            "money": f"You are a money laundering expert who works for a bank. You are given a set of questions about money laundering and are expected to answer them in a way that is both accurate and concise. Scenario: {question}",
            "gaming": f"You are a responsible gaming expert. Please provide guidance on the following scenario: {question}",
            "lilly": f"You are a patient education expert. Please provide clear and helpful information about: {question}",
            "uhg": f"You are a healthcare expert providing patient education. Please answer: {question}"
        }
        return prompts.get(usecase, question)
    
    def query_model(self, endpoint_name: str, question: str, usecase: str) -> str:
        """Query a SageMaker endpoint with a question."""
        try:
            prompt = self.create_prompt(question, usecase)
            
            payload = {
                "inputs": prompt,
                "parameters": MODEL_PARAMETERS
            }
            
            response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='application/json',
                Body=json.dumps(payload)
            )
            
            result = json.loads(response['Body'].read().decode())
            
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('generated_text', '').strip()
            elif 'generated_text' in result:
                return result['generated_text'].strip()
            else:
                return str(result)
                
        except Exception as e:
            print(f"Error querying model {endpoint_name}: {e}")
            return f"Error: {str(e)}"
    
    def load_existing_answers(self, answers_file: str) -> List[Dict]:
        """Load existing 70B answers from JSON file."""
        try:
            with open(answers_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading answers file {answers_file}: {e}")
            return []
    
    def update_answers_with_finetuned(self, answers: List[Dict], finetuned_responses: List[str]) -> List[Dict]:
        """Add finetuned responses to the existing answer structure."""
        updated_answers = []
        
        for i, answer_entry in enumerate(answers):
            updated_entry = answer_entry.copy()
            if i < len(finetuned_responses):
                updated_entry['finetuned'] = finetuned_responses[i]
            else:
                updated_entry['finetuned'] = "No response available"
            updated_answers.append(updated_entry)
        
        return updated_answers
    
    def save_updated_answers(self, answers: List[Dict], answers_file: str):
        """Save the updated answers back to the JSON file."""
        try:
            if CREATE_BACKUPS and os.path.exists(answers_file):
                backup_file = answers_file.replace('.json', '_backup.json')
                with open(answers_file, 'r', encoding='utf-8') as f:
                    original = f.read()
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(original)
                print(f"Backup created: {backup_file}")
            
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
        
        questions_file = FILE_MAPPINGS[usecase]["questions"]
        answers_file = FILE_MAPPINGS[usecase]["answers"]
        endpoint_name = MODEL_ARNS[usecase].split('/')[-1]
        
        print(f"Questions file: {questions_file}")
        print(f"Answers file: {answers_file}")
        print(f"Model endpoint: {endpoint_name}")
        
        # Read questions
        questions = self.read_questions(questions_file)
        if not questions:
            print(f"No questions found for {usecase}")
            return False
        
        # Load existing answers
        existing_answers = self.load_existing_answers(answers_file)
        if not existing_answers:
            print(f"No existing answers found for {usecase}")
            return False
        
        print(f"Found {len(questions)} questions and {len(existing_answers)} existing answers")
        
        # Query model for each question
        finetuned_responses = []
        for i, question in enumerate(questions):
            print(f"Querying question {i+1}/{len(questions)}...")
            response = self.query_model(endpoint_name, question, usecase)
            finetuned_responses.append(response)
            time.sleep(DELAY_BETWEEN_QUERIES)
        
        # Update and save answers
        updated_answers = self.update_answers_with_finetuned(existing_answers, finetuned_responses)
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

# Simple configuration - just change the usecase here and run the file
manager = ModelQueryManager()

# Change this to the usecase you want to process:
USECASE_TO_RUN = "lilly"  # Options: money, gaming, lilly, uhg

# Process the specified usecase
if USECASE_TO_RUN in MODEL_ARNS:
    manager.process_usecase(USECASE_TO_RUN)
else:
    print(f"Unknown usecase: {USECASE_TO_RUN}")
    print(f"Available usecases: {list(MODEL_ARNS.keys())}")
    print("Please update USECASE_TO_RUN variable with a valid usecase.")
