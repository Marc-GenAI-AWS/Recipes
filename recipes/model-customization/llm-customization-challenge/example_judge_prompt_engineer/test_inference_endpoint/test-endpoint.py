#!/usr/bin/env python3
"""
SageMaker Inference Endpoint Testing Script
Tests deployed fine-tuned models using the configured ARN role and endpoints
"""

import boto3
import sagemaker
from sagemaker.predictor import Predictor
from sagemaker.serializers import JSONSerializer
from sagemaker.deserializers import JSONDeserializer
import json
import time
from datetime import datetime
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MODEL_ARNS, MODEL_PARAMETERS, AWS_REGION

class EndpointTester:
    def __init__(self, region_name=AWS_REGION):
        """Initialize SageMaker session and clients."""
        self.region_name = region_name
        self.sagemaker_session = sagemaker.Session(boto_session=boto3.Session(region_name=region_name))
        # Using the ARN role from your deployment script
        self.role = "arn:aws:iam::<AWS_ACCOUNT_ID>:role/service-role/<SAGEMAKER_EXECUTION_ROLE>"
        
        print(f"[INIT] Initialized SageMaker Endpoint Tester")
        print(f"Region: {self.region_name}")
        print(f"Role: {self.role}")

    def extract_endpoint_name_from_arn(self, endpoint_arn):
        """Extract endpoint name from full ARN."""
        # ARN format: arn:aws:sagemaker:region:account:endpoint/endpoint-name
        return endpoint_arn.split('/')[-1]

    def test_endpoint_by_arn(self, endpoint_arn, test_prompt=None, use_case="general"):
        """Test an endpoint using its full ARN."""
        endpoint_name = self.extract_endpoint_name_from_arn(endpoint_arn)
        return self.test_endpoint_by_name(endpoint_name, test_prompt, use_case)

    def test_endpoint_by_name(self, endpoint_name, test_prompt=None, use_case="general"):
        """Test an endpoint using its name."""
        
        if test_prompt is None:
            test_prompts = {
                "lilly": "Create a patient education slide about diabetes management for healthcare providers.",
                "uhg": "Explain the benefits of preventive care to a healthcare member.",
                "money": "Identify potential red flags in this financial transaction: Large cash deposit from unknown source.",
                "gaming": "Provide responsible gaming tips for someone showing signs of problem gambling.",
                "state": "Explain the process for renewing a driver's license in California.",
                "cheetah": "Create a marketing strategy for a new mobile app targeting young professionals.",
                "general": "Create a professional presentation slide about digital transformation benefits."
            }
            test_prompt = test_prompts.get(use_case, test_prompts["general"])
        
        print(f"\n[TEST] Testing Endpoint: {endpoint_name}")
        print(f"Use Case: {use_case}")
        print(f"Test Prompt: '{test_prompt[:80]}...'")
        print("-" * 60)
        
        try:
            # Create predictor for the endpoint
            predictor = Predictor(
                endpoint_name=endpoint_name,
                sagemaker_session=self.sagemaker_session,
                serializer=JSONSerializer(),
                deserializer=JSONDeserializer()
            )
            
            # Test different prompt formats
            prompt_formats = [
                # Format 1: Instruction format (matches training data)
                {
                    "name": "Instruction Format",
                    "inputs": f"### Instruction:\n{test_prompt}\n\n### Response:\n",
                    "parameters": {
                        **MODEL_PARAMETERS,
                        "stop": ["###", "\n\n"]
                    }
                },
                # Format 2: Simple format
                {
                    "name": "Simple Format", 
                    "inputs": test_prompt,
                    "parameters": MODEL_PARAMETERS
                },
                # Format 3: Chat format
                {
                    "name": "Chat Format",
                    "inputs": f"Human: {test_prompt}\n\nAssistant:",
                    "parameters": {
                        **MODEL_PARAMETERS,
                        "stop": ["Human:", "\n\n"]
                    }
                }
            ]
            
            results = []
            
            for i, format_config in enumerate(prompt_formats, 1):
                print(f"\n[FORMAT {i}] Testing: {format_config['name']}")
                print("=" * 40)
                
                try:
                    start_time = time.time()
                    response = predictor.predict(format_config)
                    end_time = time.time()
                    
                    # Process response
                    generated_text = self._extract_generated_text(response, format_config["inputs"])
                    
                    result = {
                        "format": format_config["name"],
                        "success": True,
                        "response_time": round(end_time - start_time, 2),
                        "generated_text": generated_text,
                        "raw_response": response
                    }
                    
                    print(f"[SUCCESS] Response time: {result['response_time']}s")
                    print(f"Generated text ({len(generated_text)} chars):")
                    print(f"'{generated_text[:200]}{'...' if len(generated_text) > 200 else ''}'")
                    
                    results.append(result)
                    
                except Exception as e:
                    print(f"[FAILED] {str(e)}")
                    results.append({
                        "format": format_config["name"],
                        "success": False,
                        "error": str(e)
                    })
                
                # Small delay between tests
                time.sleep(1)
            
            # Summary
            print(f"\n[SUMMARY] Test Summary for {endpoint_name}")
            print("=" * 50)
            successful_tests = [r for r in results if r.get("success", False)]
            print(f"Successful tests: {len(successful_tests)}/{len(results)}")
            
            if successful_tests:
                avg_response_time = sum(r["response_time"] for r in successful_tests) / len(successful_tests)
                print(f"Average response time: {avg_response_time:.2f}s")
                
                print(f"\n[BEST] Best performing format: {successful_tests[0]['format']}")
                print(f"Best response: {successful_tests[0]['generated_text'][:300]}...")
            
            return results
            
        except Exception as e:
            print(f"[ERROR] Endpoint test failed: {e}")
            return None

    def _extract_generated_text(self, response, original_input):
        """Extract generated text from various response formats."""
        try:
            # Handle different response formats
            if isinstance(response, dict):
                if 'generated_text' in response:
                    generated_text = response['generated_text']
                elif 'outputs' in response:
                    generated_text = response['outputs']
                else:
                    generated_text = str(response)
            elif isinstance(response, list) and len(response) > 0:
                if isinstance(response[0], dict) and 'generated_text' in response[0]:
                    generated_text = response[0]['generated_text']
                else:
                    generated_text = str(response[0])
            else:
                generated_text = str(response)
            
            # Clean up the response - remove the original input
            if original_input in generated_text:
                generated_text = generated_text.replace(original_input, "").strip()
            
            # Remove common artifacts
            if "### Response:" in generated_text:
                generated_text = generated_text.split("### Response:")[-1].strip()
            
            return generated_text
            
        except Exception as e:
            print(f"Warning: Could not extract generated text: {e}")
            return str(response)

    def check_endpoint_status(self, endpoint_name):
        """Check if an endpoint is active and ready."""
        try:
            sm_client = boto3.client('sagemaker', region_name=self.region_name)
            response = sm_client.describe_endpoint(EndpointName=endpoint_name)
            
            status = response['EndpointStatus']
            print(f"[STATUS] Endpoint {endpoint_name} status: {status}")
            
            if status == 'InService':
                print("[READY] Endpoint is ready for inference")
                return True
            elif status in ['Creating', 'Updating']:
                print("[WAIT] Endpoint is still being created/updated")
                return False
            else:
                print(f"[ERROR] Endpoint is in unexpected status: {status}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Could not check endpoint status: {e}")
            return False

    def test_all_configured_endpoints(self):
        """Test all endpoints from the config file."""
        print(f"\n[START] Testing All Configured Endpoints")
        print("=" * 60)
        
        all_results = {}
        
        for use_case, endpoint_arn in MODEL_ARNS.items():
            endpoint_name = self.extract_endpoint_name_from_arn(endpoint_arn)
            
            print(f"\n[CHECK] Checking {use_case} endpoint...")
            
            # Check if endpoint exists and is ready
            if self.check_endpoint_status(endpoint_name):
                results = self.test_endpoint_by_name(endpoint_name, use_case=use_case)
                all_results[use_case] = results
            else:
                print(f"[SKIP] Skipping {use_case} - endpoint not ready")
                all_results[use_case] = None
        
        # Overall summary
        print(f"\n[RESULTS] Overall Test Results")
        print("=" * 60)
        
        for use_case, results in all_results.items():
            if results:
                successful = len([r for r in results if r.get("success", False)])
                print(f"[OK] {use_case}: {successful}/3 formats successful")
            else:
                print(f"[FAIL] {use_case}: endpoint not available")
        
        return all_results

def main():
    """Main function to test inference endpoints."""
    print("=" * 60)
    print("SAGEMAKER INFERENCE ENDPOINT TESTER")
    print("=" * 60)
    
    tester = EndpointTester()
    
    print("\nChoose testing option:")
    print("1. Test all configured endpoints")
    print("2. Test specific endpoint by name")
    print("3. Test specific endpoint by ARN")
    print("4. Check endpoint status only")
    
    try:
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            # Test all endpoints
            tester.test_all_configured_endpoints()
            
        elif choice == "2":
            # Test specific endpoint by name
            endpoint_name = input("Enter endpoint name: ").strip()
            use_case = input("Enter use case (or press Enter for 'general'): ").strip() or "general"
            custom_prompt = input("Enter custom prompt (or press Enter for default): ").strip()
            
            tester.test_endpoint_by_name(
                endpoint_name, 
                test_prompt=custom_prompt if custom_prompt else None,
                use_case=use_case
            )
            
        elif choice == "3":
            # Test specific endpoint by ARN
            endpoint_arn = input("Enter endpoint ARN: ").strip()
            use_case = input("Enter use case (or press Enter for 'general'): ").strip() or "general"
            custom_prompt = input("Enter custom prompt (or press Enter for default): ").strip()
            
            tester.test_endpoint_by_arn(
                endpoint_arn,
                test_prompt=custom_prompt if custom_prompt else None,
                use_case=use_case
            )
            
        elif choice == "4":
            # Check status only
            endpoint_input = input("Enter endpoint name or ARN: ").strip()
            if endpoint_input.startswith("arn:"):
                endpoint_name = tester.extract_endpoint_name_from_arn(endpoint_input)
            else:
                endpoint_name = endpoint_input
            
            tester.check_endpoint_status(endpoint_name)
            
        else:
            print("Invalid choice. Please run the script again.")
    
    except KeyboardInterrupt:
        print("\n\n[EXIT] Testing interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
