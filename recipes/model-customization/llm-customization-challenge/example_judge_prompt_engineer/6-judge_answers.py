#!/usr/bin/env python3
"""
Answer Judging Script
Uses Claude Sonnet via AWS Bedrock to judge 70B vs fine-tuned model responses
"""

import json
import os
import boto3
import time
from typing import List, Dict, Tuple
from datetime import datetime

class AnswerJudge:
    def __init__(self, region_name='us-west-2'):
        """Initialize AWS Bedrock client."""
        self.region_name = region_name
        self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=region_name)
        self.model_id = "arn:aws:bedrock:us-west-2:<AWS_ACCOUNT_ID>:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"  # Claude Sonnet 4
        
    def load_judge_prompt(self, use_case: str) -> str:
        """Load the judge prompt template for the given use case."""
        
        # Mapping of use cases to their judge prompt files
        judge_files = {
            "uhg": "uhg_judge_prompt_2.txt",
            "lilly": "lilly_judge_prompt.txt",
            "money": "money_launder_judge_prompt_v2.txt",
            "gaming": "responsible_gaming_judge_prompt.txt",
            "disney": "disney_judge_prompt.txt",
            "blueprint": "blueprint_judge_prompt.txt",
            "security": "security_judge_prompt.txt",
            "parsons": "parsons_judge_prompt.txt"
        }
        
        if use_case not in judge_files:
            raise ValueError(f"Unknown use case: {use_case}. Available: {list(judge_files.keys())}")
        
        judge_file_path = f"event_files/judge_prompts/{judge_files[use_case]}"
        
        if not os.path.exists(judge_file_path):
            raise FileNotFoundError(f"Judge prompt file not found: {judge_file_path}")
        
        with open(judge_file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def load_combined_answers(self, use_case: str) -> List[Dict]:
        """Load the combined answers file."""
        combined_file = f"event_files/combined_answers/{use_case}_combined_answers.json"
        
        if not os.path.exists(combined_file):
            raise FileNotFoundError(f"Combined answers file not found: {combined_file}")
        
        with open(combined_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Filter out entries with missing responses
        valid_data = []
        for item in data:
            if ("No matching" not in item.get('70b', '') and 
                "No fine-tuned" not in item.get('finetuned', '') and
                item.get('70b', '').strip() and 
                item.get('finetuned', '').strip()):
                valid_data.append(item)
        
        print(f"Loaded {len(data)} total entries, {len(valid_data)} have both responses")
        return valid_data
    
    def create_judge_prompt(self, template: str, instruction: str, response_70b: str, response_finetuned: str) -> str:
        """Create the complete judge prompt by filling in the template."""
        
        # Replace placeholders in the template
        prompt = template.replace("{INSTRUCTION}", instruction)
        prompt = prompt.replace("{RESPONSE_A}", response_70b)
        prompt = prompt.replace("{RESPONSE_B}", response_finetuned)
        
        return prompt
    
    def call_claude(self, prompt: str, max_retries: int = 3) -> str:
        """Call Claude Sonnet via AWS Bedrock."""
        
        # Prepare the request body
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.1,  # Low temperature for consistent judging
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        for attempt in range(max_retries):
            try:
                print(f"    Calling Claude (attempt {attempt + 1}/{max_retries})...")
                
                response = self.bedrock_runtime.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )
                
                response_body = json.loads(response['body'].read())
                
                # Extract the response text
                if 'content' in response_body and len(response_body['content']) > 0:
                    return response_body['content'][0]['text']
                else:
                    return "Error: No content in response"
                
            except Exception as e:
                print(f"    Error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return f"Error calling Claude: {e}"
    
    def parse_judge_response(self, response: str) -> Tuple[str, float, str]:
        """Parse Claude's response to extract winner, rating, and rationale."""
        try:
            # Try to find JSON in the response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                result = json.loads(json_str)
                
                winner = result.get('winner', 'Unknown')
                rating = float(result.get('rating', 0.0))
                rationale = result.get('rationale', 'No rationale provided')
                
                return winner, rating, rationale
            else:
                return "Error", 0.0, "Could not parse JSON response"
                
        except Exception as e:
            return "Error", 0.0, f"Parse error: {e}"
    
    def judge_answers(self, use_case: str, output_file: str = None) -> str:
        """Judge all answer pairs and calculate win rate."""
        
        print(f"Judging answers for use case: {use_case}")
        
        # Load judge prompt template
        judge_template = self.load_judge_prompt(use_case)
        print(f"Loaded judge prompt template ({len(judge_template)} characters)")
        
        # Load combined answers
        combined_data = self.load_combined_answers(use_case)
        print(f"Loaded {len(combined_data)} question-answer pairs")
        
        # Prepare output file
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"event_files/judge_results/{use_case}_judge_results_{timestamp}.json"
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        results = []
        finetune_wins = 0
        seventyb_wins = 0
        errors = 0
        
        print(f"\nJudging {len(combined_data)} pairs...")
        
        for i, item in enumerate(combined_data, 1):
            print(f"\nQuestion {i}/{len(combined_data)}: {item['instruction'][:80]}...")
            
            # Create judge prompt
            judge_prompt = self.create_judge_prompt(
                judge_template,
                item['instruction'],
                item['70b'],
                item['finetuned']
            )
            
            # Get Claude's judgment
            claude_response = self.call_claude(judge_prompt)
            
            # Parse the response
            winner, rating, rationale = self.parse_judge_response(claude_response)
            
            # Count wins
            if winner == "A":  # 70B wins
                seventyb_wins += 1
                print(f"  Winner: 70B (Rating: {rating})")
            elif winner == "B":  # Fine-tuned wins
                finetune_wins += 1
                print(f"  Winner: Fine-tuned (Rating: {rating})")
            else:
                errors += 1
                print(f"  Error in judgment: {winner}")
            
            # Store result
            result = {
                "question_number": i,
                "instruction": item['instruction'],
                "winner": winner,
                "rating": rating,
                "rationale": rationale,
                "70b_response": item['70b'],
                "finetuned_response": item['finetuned'],
                "claude_full_response": claude_response
            }
            
            results.append(result)
            
            # Save progress every 10 questions
            if i % 10 == 0:
                print(f"  Saving progress... ({i}/{len(combined_data)} completed)")
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "metadata": {
                            "use_case": use_case,
                            "total_questions": len(combined_data),
                            "completed": i,
                            "finetune_wins": finetune_wins,
                            "seventyb_wins": seventyb_wins,
                            "errors": errors
                        },
                        "results": results
                    }, f, indent=2, ensure_ascii=False)
            
            # Small delay to be respectful to the API
            time.sleep(1)
        
        # Calculate final statistics
        total_valid = finetune_wins + seventyb_wins
        finetune_winrate = (finetune_wins / total_valid * 100) if total_valid > 0 else 0
        
        # Save final results
        final_data = {
            "metadata": {
                "use_case": use_case,
                "total_questions": len(combined_data),
                "valid_judgments": total_valid,
                "finetune_wins": finetune_wins,
                "seventyb_wins": seventyb_wins,
                "errors": errors,
                "finetune_winrate": round(finetune_winrate, 2),
                "judge_model": self.model_id,
                "timestamp": datetime.now().isoformat()
            },
            "results": results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n" + "=" * 60)
        print("JUDGING COMPLETE")
        print("=" * 60)
        print(f"Total questions: {len(combined_data)}")
        print(f"Valid judgments: {total_valid}")
        print(f"Fine-tuned wins: {finetune_wins}")
        print(f"70B wins: {seventyb_wins}")
        print(f"Errors: {errors}")
        print(f"Fine-tuned win rate: {finetune_winrate:.2f}%")
        print(f"Results saved to: {output_file}")
        
        return output_file

def main():
    """Main function to run the answer judging."""
    print("=" * 60)
    print("ANSWER JUDGING TOOL")
    print("=" * 60)
    
    # Configuration - Update this value
    USE_CASE = "gaming"  # Change this to: uhg, lilly, money, gaming, disney, blueprint, security, parsons
    
    # Optional: specify custom output file
    OUTPUT_FILE = None  # Will auto-generate if None
    
    print(f"Use case: {USE_CASE}")
    print(f"Judge model: Claude Sonnet 3.5")
    
    try:
        # Initialize judge
        judge = AnswerJudge()
        
        # Judge answers
        output_file = judge.judge_answers(
            use_case=USE_CASE,
            output_file=OUTPUT_FILE
        )
        
        print(f"\nJudging complete! Check {output_file} for detailed results.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
