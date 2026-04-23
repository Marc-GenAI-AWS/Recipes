#!/usr/bin/env python3
"""
Combine money laundering responses into a new format for evaluation
"""

import json
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def combine_money_responses():
    """Combine money laundering responses into new format"""
    
    # Input file path
    input_file = "event_files/70b_answers/money_laundering_responses_working.json"
    
    # Create output directory if it doesn't exist
    output_dir = "combined_answers"
    os.makedirs(output_dir, exist_ok=True)
    
    # Output file path
    output_file = os.path.join(output_dir, "money_combined_answers.json")
    
    try:
        # Load the input file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"✅ Loaded {len(data)} responses from {input_file}")
        
        # Transform the data structure
        combined_data = []
        for i, item in enumerate(data, 1):
            transformed_item = {
                "question_number": i,
                "dataset": item.get("dataset", "codeinstructions"),
                "instruction": item.get("instruction", ""),
                "70B_model": item.get("output", ""),
                "generator": item.get("generator", "llama3_70b_instruct")
            }
            combined_data.append(transformed_item)
        
        # Save the combined data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Successfully created {output_file}")
        logger.info(f"📊 Transformed {len(combined_data)} responses")
        logger.info(f"🔄 Changed 'output' field to '70B_model' field")
        
        return output_file
        
    except FileNotFoundError:
        logger.error(f"❌ Input file not found: {input_file}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parsing JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return None

def main():
    """Main function"""
    logger.info("🏦 Money Laundering Response Combiner")
    logger.info("=" * 50)
    
    output_file = combine_money_responses()
    
    if output_file:
        logger.info(f"\n🎉 Process completed successfully!")
        logger.info(f"📁 Output file: {output_file}")
    else:
        logger.error("❌ Process failed!")

if __name__ == "__main__":
    main()
