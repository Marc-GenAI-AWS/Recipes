#!/usr/bin/env python3
import sys
sys.path.append('.')

# Import the fixed DataGenerator
exec(open('1-0-generate_any_data.py').read())

def test_prompt_formatting():
    try:
        generator = DataGenerator(domain_key="gaming")
        
        print("=== USE CASE LOADED ===")
        print(generator.use_case)
        print("\n=== FORMATTED PROMPT PREVIEW ===")
        formatted_prompt = generator.prompt.replace("{USE_CASE_HERE}", generator.use_case)
        print(formatted_prompt[:500] + "...")
        
        print("\n=== TESTING SINGLE GENERATION ===")
        result = generator.generate_training_data()
        if result:
            print("Generated content:")
            print(result[:500] + "...")
        else:
            print("Generation failed!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_prompt_formatting()
