#!/usr/bin/env python3
import sys
sys.path.append('.')

exec(open('5-combine_answers.py').read())
# Now AnswerCombiner class is available

def test_combine():
    try:
        combiner = AnswerCombiner()
        
        # Test the extraction method
        test_70b = "You are a money laundering expert who works for a bank. You are given a set of questions about money laundering and are expected to answer them in a way that is both accurate and concise. Scenario: A business banking client frequently deposits just under $10,000 at various branches and has begun wiring large sums overseas to a shell company. What steps should a bank employee take to analyze and process this potentially suspicious activity?"
        
        test_finetune = "A business banking client frequently deposits just under $10,000 at various branches and has begun wiring large sums overseas to a shell company. What steps should a bank employee take to analyze and process this potentially suspicious activity?"
        
        extracted_70b = combiner.extract_question_from_instruction(test_70b)
        extracted_finetune = combiner.extract_question_from_instruction(test_finetune)
        
        print("70B extracted:", extracted_70b[:100] + "...")
        print("Finetune extracted:", extracted_finetune[:100] + "...")
        print("Match:", extracted_70b == extracted_finetune)
        
        # Try to combine
        output_file = combiner.combine_answers("money")
        print(f"Success! Output: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_combine()
