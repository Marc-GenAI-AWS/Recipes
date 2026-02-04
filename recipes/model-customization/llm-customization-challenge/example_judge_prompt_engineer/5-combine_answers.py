#!/usr/bin/env python3
"""
Answer Combination Script
Combines 70B and fine-tuned model responses into a single JSON file for comparison
"""

import json
import os
from typing import List, Dict

class AnswerCombiner:
    def __init__(self):
        """Initialize the answer combiner."""
        self.base_70b_path = "event_files/70b_answers"
        self.base_finetune_path = "event_files/finetune_answers"
        
    def find_answer_files(self, use_case: str) -> tuple:
        """Find the 70B and fine-tuned answer files for a given use case."""
        
        # Mapping of use cases to their 70B answer files
        seventyb_files = {
            "uhg": "uhg_patient_edu_responses_working.json",
            "lilly": "lilly_patient_edu_responses_working.json", 
            "money": "money_laundering_responses_working.json",
            "gaming": "responsible_gaming_responses.json",
            "disney": "disney_responses_working.json",
            "blueprint": "ibm_blueprint_responses_working.json",
            "security": "certis_security_responses.json",
            "parsons": "parsons_responses_working.json"
        }
        
        if use_case not in seventyb_files:
            raise ValueError(f"Unknown use case: {use_case}. Available: {list(seventyb_files.keys())}")
        
        seventyb_path = os.path.join(self.base_70b_path, seventyb_files[use_case])
        
        # Find fine-tuned file - try multiple naming patterns
        finetune_patterns = [
            f"{use_case}_finetune_answers.json",
            f"{use_case}_finetune_responses.json"
        ]
        
        finetune_path = None
        
        # Look for files with timestamp patterns if exact match not found
        import glob
        finetune_dir = self.base_finetune_path
        
        for pattern in finetune_patterns:
            exact_path = os.path.join(finetune_dir, pattern)
            if os.path.exists(exact_path):
                finetune_path = exact_path
                break
        
        # If exact match not found, look for timestamped files
        if finetune_path is None:
            timestamped_patterns = [
                f"{use_case}_finetune_responses_*.json",
                f"{use_case}_finetune_answers_*.json"
            ]
            
            for pattern in timestamped_patterns:
                search_pattern = os.path.join(finetune_dir, pattern)
                matches = glob.glob(search_pattern)
                if matches:
                    # Use the most recent file if multiple matches
                    finetune_path = max(matches, key=os.path.getmtime)
                    break
        
        # Check if files exist
        if not os.path.exists(seventyb_path):
            raise FileNotFoundError(f"70B answers file not found: {seventyb_path}")
        
        if finetune_path is None or not os.path.exists(finetune_path):
            # List available files to help debug
            available_files = os.listdir(finetune_dir) if os.path.exists(finetune_dir) else []
            raise FileNotFoundError(f"Fine-tuned answers file not found for use case '{use_case}'. "
                                  f"Available files in {finetune_dir}: {available_files}")
        
        return seventyb_path, finetune_path
    
    def load_json_file(self, file_path: str) -> List[Dict]:
        """Load and return JSON data from file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_question_from_instruction(self, instruction: str) -> str:
        """Extract the actual question from the instruction field."""
        # Remove common prefixes like "You are a healthcare employee Scenario:"
        prefixes_to_remove = [
            "You are a healthcare employee Scenario:",
            "You are a pharmaceutical expert. Scenario:",
            "You are a financial compliance analyst. Scenario:",
            "You are a responsible gaming specialist. Scenario:",
            "You are an gaming company employee Scenario:",  # Fixed: added the actual prefix from 70B data
            "You are a Disney customer service representative. Scenario:",
            "You are a business consultant. Scenario:",
            "You are a security advisor. Scenario:",
            "You are a project management consultant. Scenario:",
            "You are a money laundering expert who works for a bank. You are given a set of questions about money laundering and are expected to answer them in a way that is both accurate and concise. Scenario:",
            "Please provide your response in 500 tokens or less.",
            "Scenario:" 
        ]
        
        question = instruction
        for prefix in prefixes_to_remove:
            question = question.replace(prefix, "").strip()
        
        return question
    
    def combine_answers(self, use_case: str, output_file: str = None) -> str:
        """Combine 70B and fine-tuned answers into a single comparison file."""
        
        print(f"Combining answers for use case: {use_case}")
        
        # Find answer files
        seventyb_path, finetune_path = self.find_answer_files(use_case)
        
        print(f"70B answers: {seventyb_path}")
        print(f"Fine-tuned answers: {finetune_path}")
        
        # Load both files
        seventyb_data = self.load_json_file(seventyb_path)
        finetune_data = self.load_json_file(finetune_path)
        
        print(f"Loaded {len(seventyb_data)} 70B responses")
        print(f"Loaded {len(finetune_data)} fine-tuned responses")
        
        # Create mapping of questions to responses for easier matching
        seventyb_map = {}
        for item in seventyb_data:
            question = self.extract_question_from_instruction(item['instruction'])
            seventyb_map[question] = item['output']
        
        finetune_map = {}
        for item in finetune_data:
            question = self.extract_question_from_instruction(item['instruction'])
            finetune_map[question] = item['output']
        
        # Combine responses
        combined_data = []
        
        # Use fine-tuned questions as the base (they should be cleaner)
        for question in finetune_map.keys():
            # Find matching 70B response
            seventyb_output = seventyb_map.get(question, "No matching 70B response found")
            
            combined_item = {
                "usecase": use_case,
                "instruction": question,
                "70b": seventyb_output,
                "finetuned": finetune_map[question]
            }
            
            combined_data.append(combined_item)
        
        # Check for any 70B responses that don't have fine-tuned matches
        missing_in_finetune = []
        for question in seventyb_map.keys():
            if question not in finetune_map:
                missing_in_finetune.append(question)
        
        if missing_in_finetune:
            print(f"Warning: {len(missing_in_finetune)} questions found in 70B but not in fine-tuned responses")
            for question in missing_in_finetune:
                combined_item = {
                    "usecase": use_case,
                    "instruction": question,
                    "70b": seventyb_map[question],
                    "finetuned": "No fine-tuned response found"
                }
                combined_data.append(combined_item)
        
        # Prepare output file
        if output_file is None:
            output_file = f"event_files/combined_answers/{use_case}_combined_answers.json"
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Save combined data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nCombined {len(combined_data)} question-answer pairs")
        print(f"Results saved to: {output_file}")
        
        return output_file
    
    def show_sample(self, combined_file: str, num_samples: int = 2):
        """Show a sample of the combined data."""
        with open(combined_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\nSample of combined data (showing {min(num_samples, len(data))} items):")
        print("=" * 80)
        
        for i, item in enumerate(data[:num_samples]):
            print(f"\nSample {i+1}:")
            print(f"Use Case: {item['usecase']}")
            print(f"Question: {item['instruction'][:100]}...")
            print(f"70B Response: {item['70b'][:150]}...")
            print(f"Fine-tuned Response: {item['finetuned'][:150]}...")
            print("-" * 80)

def main():
    """Main function to run the answer combination."""
    print("=" * 60)
    print("ANSWER COMBINATION TOOL")
    print("=" * 60)
    
    # Configuration - Update this value
    USE_CASE = "gaming"  # Change this to: uhg, lilly, money, gaming, disney, blueprint, security, parsons
    
    # Optional: specify custom output file
    OUTPUT_FILE = None  # Will auto-generate if None
    
    print(f"Use case: {USE_CASE}")
    
    try:
        # Initialize combiner
        combiner = AnswerCombiner()
        
        # Combine answers
        output_file = combiner.combine_answers(
            use_case=USE_CASE,
            output_file=OUTPUT_FILE
        )
        
        # Show sample of results
        combiner.show_sample(output_file, num_samples=2)
        
        print(f"\n" + "=" * 60)
        print("COMBINATION COMPLETE")
        print("=" * 60)
        print(f"Output file: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
