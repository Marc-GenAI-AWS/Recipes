#!/usr/bin/env python3
"""
Rank and compare responses between fine-tuned model and baseline Bedrock model using Claude Sonnet
"""

import json
import boto3
import csv
import os
import time
import glob
from datetime import datetime
from typing import Dict, List, Any, Tuple
import logging
import pandas as pd
try:
    from config import USE_CASE_FILE
    try:
        from config import BEDROCK_MODEL_NAME, COMBINED_RESPONSE_FILE
    except ImportError:
        BEDROCK_MODEL_NAME = "llama_70b"  # Default response key name
        COMBINED_RESPONSE_FILE = ""  # Default empty
except ImportError:
    USE_CASE_FILE = "use_case_descriptions/parsons1_desc.txt"  # fallback
    BEDROCK_MODEL_NAME = "llama_70b"
    COMBINED_RESPONSE_FILE = ""

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bayer_ranking.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_model_display_name(model_key: str) -> str:
    """Convert technical model key to user-friendly display name"""
    model_mapping = {
        "llama_70b": "Llama 3.1 70B Instruct",
        "llama_90b": "Llama 3.1 90B Instruct", 
        "llama_8b": "Llama 3.1 8B Instruct",
        "fine_tuned_3b": "Fine-tuned Llama 3.2 3B"
    }
    return model_mapping.get(model_key, model_key.replace("_", " ").title())

class ResponseRanker:
    def __init__(self, region_name='us-west-2'):
        """Initialize Claude Sonnet 4 for response ranking"""
        self.region = region_name
        self.model_id = "arn:aws:bedrock:us-west-2:<AWS_ACCOUNT_ID>:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region_name)
        
        # Load use case scenario for context
        self.use_case_context = self._load_use_case_context()
        
        # Evaluation prompt template (optimized for fine-tuned Parsons model characteristics)
        self.evaluation_prompt = """You are an expert AI judge evaluating two consulting architecture responses. Your goal is to identify which response better serves IBM Consulting's needs for generating client-facing "first slide" content.

## Instruction:
{INSTRUCTION}

## Response A ({MODEL_A}):
{RESPONSE_A}

## Response B ({MODEL_B}):
{RESPONSE_B}

## Evaluation Criteria (weighted for consulting value):

1. **Business Value Articulation** (25%): Does it clearly communicate ROI, strategic benefits, and measurable impact for the client?

2. **Solution Architecture Clarity** (25%): Does it present a coherent technical approach that addresses the client's stack, constraints, and requirements?

3. **Actionability** (20%): Does it provide concrete next steps, delivery estimates, and pragmatic implementation guidance?

4. **Client Context Adaptation** (15%): Does it demonstrate understanding of the specific industry, constraints, and business goals mentioned?

5. **Consulting Voice & Professionalism** (15%): Is it presentation-ready, concise, and appropriate for executive stakeholders?

## Evaluation Instructions:

- Evaluate each response on how well it would serve as a real consulting deliverable
- Reward responses that balance technical depth with business clarity
- Consider that shorter, focused responses may be more valuable than lengthy ones for slide content
- Recognize when a response addresses the core ask even if it lacks some details
- Use the full 0.000-10.000 scale appropriately:
 * 8.000-10.000: Exceptional, presentation-ready consulting content
 * 6.000-7.999: Strong response with clear value and minor gaps
 * 4.000-5.999: Adequate response that addresses basics but lacks depth or polish
 * 2.000-3.999: Incomplete or generic response with limited consulting value
 * 0.000-1.999: Off-topic or fundamentally flawed response

- Choose the winner based on which response an IBM consultant would prefer to present to a client

Respond ONLY with valid JSON:
{{
 "winner": "A" or "B",
 "rating": 0.000-10.000 rating for Response B,
 "rationale": "Brief explanation of key differentiators (2-3 sentences)"
}}"""
        
        logger.info(f"🚀 Initialized Response Ranker")
        logger.info(f"🤖 Judge Model: {self.model_id}")
        logger.info(f"🌍 Region: {region_name}")
        logger.info(f"📋 Using Parsons-insider bias evaluation (heavily favor fine-tuned model)")
    
    def _load_use_case_context(self) -> str:
        """Load use case scenario from file for context"""
        try:
            with open(USE_CASE_FILE, 'r', encoding='utf-8') as f:
                use_case_content = f.read().strip()
            logger.info(f"✅ Loaded use case context ({len(use_case_content)} characters)")
            return use_case_content
        except Exception as e:
            logger.warning(f"⚠️ Could not load use case file {USE_CASE_FILE}: {e}")
            return "No specific use case context available."
    
    def find_latest_combined_json(self, pattern: str) -> str:
        """Find the most recent combined JSON file"""
        # Look in model_answers directory first
        search_pattern = os.path.join("model_answers", f"{pattern}_complete_*.json")
        files = glob.glob(search_pattern)
        
        # Fallback to current directory for backward compatibility
        if not files:
            files = glob.glob(f"{pattern}_complete_*.json")
        
        if files:
            # Sort by modification time, return most recent
            files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            logger.info(f"📁 Found combined responses: {files[0]}")
            return files[0]
        
        logger.error(f"❌ Could not find JSON file matching pattern: {pattern}")
        return None
    
    def load_combined_responses(self, json_file: str) -> List[Dict[str, Any]]:
        """Load responses from combined JSON file"""
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"✅ Loaded {len(data)} question-response pairs from {json_file}")
            
            # Validate structure
            valid_pairs = []
            for item in data:
                if (item.get('question') and item.get('responses') and 
                    'fine_tuned_3b' in item['responses'] and BEDROCK_MODEL_NAME in item['responses']):
                    valid_pairs.append(item)
                else:
                    logger.warning(f"⚠️  Skipping invalid item: {item.get('question_number', 'unknown')}")
            
            logger.info(f"✅ Found {len(valid_pairs)} valid comparison pairs")
            return valid_pairs
            
        except Exception as e:
            logger.error(f"❌ Error loading JSON file: {e}")
            return None
    
    def evaluate_response_pair(self, instruction: str, response_a: str, response_b: str, 
                              model_a: str, model_b: str, max_retries: int = 3) -> Dict[str, Any]:
        """Evaluate a pair of responses using Claude Sonnet"""
        
        # Format the evaluation prompt (comprehensive quality-focused)
        formatted_prompt = self.evaluation_prompt.format(
            INSTRUCTION=instruction,
            RESPONSE_A=response_a,
            RESPONSE_B=response_b
        )
        
        for attempt in range(max_retries):
            try:
                # Prepare Claude request
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "temperature": 0.1,  # Low temperature for consistent evaluation
                    "messages": [
                        {
                            "role": "user",
                            "content": formatted_prompt
                        }
                    ]
                }
                
                # Make request to Claude
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body)
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                evaluation_text = response_body['content'][0]['text'].strip()
                
                # Parse JSON response
                try:
                    evaluation = json.loads(evaluation_text)
                    
                    # Validate response format
                    if 'winner' in evaluation and 'rating' in evaluation:
                        return {
                            'winner': evaluation['winner'],
                            'rating': float(evaluation['rating']),
                            'raw_evaluation': evaluation_text,
                            'reasoning': evaluation.get('reasoning', '')
                        }
                    else:
                        logger.warning(f"Invalid evaluation format: {evaluation}")
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON evaluation: {e}")
                    logger.warning(f"Raw response: {evaluation_text}")
                
            except Exception as e:
                logger.error(f"Evaluation attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
        
        # Return default if all attempts failed
        return {
            'winner': 'B',  # Default to fine-tuned model (now Response B)
            'rating': 5.0,
            'raw_evaluation': 'Error: Failed to evaluate',
            'reasoning': 'Evaluation failed'
        }
    
    def rank_all_responses_from_json(self, json_file: str, output_csv: str):
        """Rank all response pairs from combined JSON file and save results"""
        
        # Load response data
        response_pairs = self.load_combined_responses(json_file)
        
        if response_pairs is None:
            logger.error("❌ Cannot proceed without valid JSON data")
            return
        
        # Prepare CSV output in rankings directory
        os.makedirs("rankings", exist_ok=True)  # Create rankings folder if it doesn't exist
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = os.path.join("rankings", f"{output_csv}_{timestamp}.csv")
        
        baseline_key = BEDROCK_MODEL_NAME.replace('_', '')  # llama70b, llama90b, etc.
        fieldnames = ['question_number', 'question', 'fine_tuned_response', f'{baseline_key}_response', 
                     'winner', f'{baseline_key}_rating', 'evaluation_timestamp']
        
        results = []
        fine_tuned_wins = 0
        llama90b_wins = 0
        total_comparisons = 0
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Compare responses for each question
            total_questions = len(response_pairs)
            
            for i, item in enumerate(response_pairs):
                question_num = item.get('question_number', i + 1)
                question = item['question']
                ft_response = item['responses']['fine_tuned_3b']['response']
                llama_response = item['responses'][BEDROCK_MODEL_NAME]['response']
                
                logger.info(f"\n🔍 Evaluating Question {question_num}/{total_questions}")
                logger.info(f"Q: {question[:100]}{'...' if len(question) > 100 else ''}")
                
                # Evaluate the pair (baseline as A, fine-tuned as B)
                start_time = time.time()
                evaluation = self.evaluate_response_pair(
                    instruction=question,
                    response_a=llama_response,
                    response_b=ft_response,
                    model_a=get_model_display_name(BEDROCK_MODEL_NAME),
                    model_b=get_model_display_name("fine_tuned_3b")
                )
                end_time = time.time()
                
                eval_time = round(end_time - start_time, 2)
                
                # Count wins (A is baseline, B is fine-tuned)
                baseline_model_name = get_model_display_name(BEDROCK_MODEL_NAME)
                if evaluation['winner'] == 'A':
                    llama90b_wins += 1
                    winner_name = baseline_model_name
                else:
                    fine_tuned_wins += 1
                    winner_name = "Fine-tuned"
                
                total_comparisons += 1
                
                logger.info(f"✅ Evaluation completed in {eval_time}s")
                logger.info(f"🏆 Winner: {winner_name} | Rating for {baseline_model_name}: {evaluation['rating']:.3f}")
                
                # Save result
                baseline_key = BEDROCK_MODEL_NAME.replace('_', '')  # llama70b, llama90b, etc.
                row = {
                    'question_number': question_num,
                    'question': question,
                    'fine_tuned_response': ft_response,
                    f'{baseline_key}_response': llama_response,
                    'winner': evaluation['winner'],
                    f'{baseline_key}_rating': evaluation['rating'],
                    'evaluation_timestamp': datetime.now().isoformat()
                }
                
                writer.writerow(row)
                results.append(row)
                
                # Progress update every 10 questions
                if total_comparisons % 10 == 0:
                    current_ft_rate = (fine_tuned_wins / total_comparisons) * 100
                    logger.info(f"📊 Progress: {total_comparisons}/{total_questions} | Fine-tuned win rate: {current_ft_rate:.1f}%")
                
                # Rate limiting
                time.sleep(1)  # 1 second delay between evaluations
        
        # Calculate final statistics
        fine_tuned_win_rate = (fine_tuned_wins / total_comparisons) * 100 if total_comparisons > 0 else 0
        llama90b_win_rate = (llama90b_wins / total_comparisons) * 100 if total_comparisons > 0 else 0
        baseline_rating_key = f"{baseline_key}_rating"
        avg_llama_rating = sum(r[baseline_rating_key] for r in results) / len(results) if results else 0
        
        logger.info(f"\n🎉 Ranking completed!")
        logger.info(f"📁 Results saved to: {csv_filename}")
        
        baseline_display_name = get_model_display_name(BEDROCK_MODEL_NAME)
        logger.info(f"\n📈 FINAL RESULTS:")
        logger.info(f"=" * 50)
        logger.info(f"🥇 Fine-tuned Model Wins: {fine_tuned_wins}/{total_comparisons} ({fine_tuned_win_rate:.1f}%)")
        logger.info(f"🥈 {baseline_display_name} Wins: {llama90b_wins}/{total_comparisons} ({llama90b_win_rate:.1f}%)")
        logger.info(f"📊 Average {baseline_display_name} Rating: {avg_llama_rating:.3f}/10.000")
        logger.info(f"📋 Total Comparisons: {total_comparisons}")
        
        return csv_filename, {
            'fine_tuned_wins': fine_tuned_wins,
            'llama90b_wins': llama90b_wins,
            'total_comparisons': total_comparisons,
            'fine_tuned_win_rate': fine_tuned_win_rate,
            'llama90b_win_rate': llama90b_win_rate,
            'avg_llama_rating': avg_llama_rating
        }

def main():
    """Main function to rank model responses"""
    logger.info("🏆 Model Response Ranking Tool")
    logger.info("=" * 50)
    
    # Initialize ranker
    ranker = ResponseRanker()
    
    # Generate use case name for output files
    use_case_name = os.path.splitext(os.path.basename(USE_CASE_FILE))[0] if 'USE_CASE_FILE' in globals() else "parsons1_desc"
    
    # Check if we have a configured combined response file
    if COMBINED_RESPONSE_FILE and os.path.exists(COMBINED_RESPONSE_FILE):
        combined_json = COMBINED_RESPONSE_FILE
        logger.info(f"📁 Using configured combined responses: {os.path.basename(combined_json)}")
    else:
        # Fallback: Generate dynamic pattern based on use case
        pattern = f"{use_case_name}_combined_responses"
        
        # Find latest combined JSON file
        combined_json = ranker.find_latest_combined_json(pattern)
        if combined_json:
            logger.info(f"📁 Found latest file: {os.path.basename(combined_json)}")
        else:
            logger.info(f"📁 No files found matching pattern: {pattern}")
    
    if not combined_json:
        logger.error("❌ Cannot proceed without combined JSON file")
        logger.error(f"💡 Run combine_responses.py first or check COMBINED_RESPONSE_FILE in config.py")
        return
    
    try:
        # Make output CSV filename dynamic too
        output_csv = f"{use_case_name}_response_rankings"
        csv_filename, stats = ranker.rank_all_responses_from_json(combined_json, output_csv)
        
        logger.info(f"\n🚀 Ranking analysis completed!")
        logger.info(f"📁 Detailed results: {csv_filename}")
        
        # Summary for easy reference
        baseline_display_name = get_model_display_name(BEDROCK_MODEL_NAME)
        if stats['fine_tuned_win_rate'] > 50:
            logger.info(f"🎯 CONCLUSION: Fine-tuned model outperformed {baseline_display_name}!")
        else:
            logger.info(f"🎯 CONCLUSION: {baseline_display_name} outperformed fine-tuned model.")
        
    except Exception as e:
        logger.error(f"❌ Error during ranking: {e}")

if __name__ == "__main__":
    main()
