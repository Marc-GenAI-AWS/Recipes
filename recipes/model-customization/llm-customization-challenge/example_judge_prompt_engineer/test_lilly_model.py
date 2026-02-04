#!/usr/bin/env python3
"""
Script to test the Lilly fine-tuned model with sample questions
and save the responses to analyze what's going wrong.
"""

import json
import boto3
import time
from datetime import datetime

class LillyModelTester:
    def __init__(self):
        """Initialize the SageMaker runtime client."""
        self.sagemaker_runtime = boto3.client('sagemaker-runtime', region_name='us-west-2')
        self.endpoint_name = 'jumpstart-dft-meta-textgeneration-l-20251015-005858'
        
        # Sample questions to test the model
        self.test_questions = [
            "What should a patient ask their provider before starting a new injectable medication?",
            "How can patients track side effects and symptoms when starting a new therapy?",
            "What steps should caregivers take to safely organize medications for adults with memory issues?",
            "How can switching to a generic version of a branded drug impact treatment?",
            "What are tips for safe travel with prescription drugs and medical devices?"
        ]
        
        # Model parameters
        self.model_parameters = {
            "max_new_tokens": 500,
            "temperature": 0.1,
            "top_p": 0.9,
            "do_sample": True
        }
    
    def create_prompt(self, question: str) -> str:
        """Create a prompt for the Lilly patient education use case."""
        return f"You are a patient education expert. Please provide clear and helpful information about: {question}"
    
    def query_model(self, question: str) -> dict:
        """Query the SageMaker endpoint with a question."""
        try:
            prompt = self.create_prompt(question)
            print(f"Testing question: {question[:50]}...")
            print(f"Using prompt: {prompt}")
            
            payload = {
                "inputs": prompt,
                "parameters": self.model_parameters
            }
            
            print(f"Calling endpoint: {self.endpoint_name}")
            
            response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType='application/json',
                Body=json.dumps(payload)
            )
            
            print("Got response from endpoint")
            result = json.loads(response['Body'].read().decode())
            print(f"Raw result type: {type(result)}")
            
            # Extract the generated text
            if isinstance(result, list) and len(result) > 0:
                generated_text = result[0].get('generated_text', '').strip()
                print(f"Extracted from list: {len(generated_text)} chars")
            elif 'generated_text' in result:
                generated_text = result['generated_text'].strip()
                print(f"Extracted from dict: {len(generated_text)} chars")
            else:
                generated_text = str(result)
                print(f"Converted to string: {len(generated_text)} chars")
            
            print(f"Generated text preview: {generated_text[:100]}...")
            
            return {
                "question": question,
                "prompt": prompt,
                "response": generated_text,
                "raw_result": result,
                "status": "success"
            }
                
        except Exception as e:
            print(f"Error querying model: {e}")
            import traceback
            traceback.print_exc()
            return {
                "question": question,
                "prompt": prompt if 'prompt' in locals() else "N/A",
                "response": f"Error: {str(e)}",
                "raw_result": None,
                "status": "error"
            }
    
    def test_model(self):
        """Test the model with all sample questions."""
        print("=" * 60)
        print("TESTING LILLY FINE-TUNED MODEL")
        print("=" * 60)
        print(f"Endpoint: {self.endpoint_name}")
        print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        results = []
        
        for i, question in enumerate(self.test_questions, 1):
            print(f"\n--- Test {i}/{len(self.test_questions)} ---")
            result = self.query_model(question)
            results.append(result)
            
            # Print summary
            print(f"Status: {result['status']}")
            print(f"Response length: {len(result['response'])} characters")
            print(f"Response preview: {result['response'][:100]}...")
            
            # Wait between requests
            if i < len(self.test_questions):
                time.sleep(2)
        
        return results
    
    def save_results(self, results: list):
        """Save test results to a JSON file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"lilly_model_test_results_{timestamp}.json"
        
        output_data = {
            "test_info": {
                "endpoint": self.endpoint_name,
                "timestamp": datetime.now().isoformat(),
                "total_tests": len(results),
                "model_parameters": self.model_parameters
            },
            "results": results
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n" + "=" * 60)
            print(f"Results saved to: {filename}")
            print("=" * 60)
            
            # Print summary
            successful_tests = sum(1 for r in results if r['status'] == 'success')
            failed_tests = len(results) - successful_tests
            
            print(f"Summary:")
            print(f"  Total tests: {len(results)}")
            print(f"  Successful: {successful_tests}")
            print(f"  Failed: {failed_tests}")
            
            if successful_tests > 0:
                avg_response_length = sum(len(r['response']) for r in results if r['status'] == 'success') / successful_tests
                print(f"  Average response length: {avg_response_length:.0f} characters")
            
            return filename
            
        except Exception as e:
            print(f"Error saving results: {e}")
            return None

def main():
    """Main function to run the model test."""
    print("Starting Lilly model test...")
    
    try:
        tester = LillyModelTester()
        print("Tester initialized successfully")
        
        # Run the tests
        print("Running model tests...")
        results = tester.test_model()
        print(f"Tests completed, got {len(results)} results")
        
        # Save results
        print("Saving results...")
        filename = tester.save_results(results)
        
        if filename:
            print(f"\nTest completed successfully!")
            print(f"Check the file '{filename}' for detailed results.")
        else:
            print("\nTest completed but failed to save results.")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
