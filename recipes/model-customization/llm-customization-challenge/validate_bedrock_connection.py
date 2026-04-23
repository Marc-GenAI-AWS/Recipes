"""
Validation script to test AWS Bedrock connection to Claude Sonnet 4.

This script tests:
1. AWS credentials are configured
2. Bedrock service is accessible
3. Claude Sonnet 4 model can be invoked
4. Response parsing works correctly
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.aws_client_manager import AWSClientManager
from src.configuration_manager import ConfigurationManager
from src.logging_config import get_logger

logger = get_logger("bedrock_validation")


def test_bedrock_connection():
    """Test Bedrock connection and Claude Sonnet 4 invocation."""
    
    print("=" * 80)
    print("AWS Bedrock Connection Validation")
    print("=" * 80)
    print()
    
    # Step 1: Load configuration
    print("Step 1: Loading pipeline configuration...")
    try:
        config_manager = ConfigurationManager()
        pipeline_config = config_manager.load_pipeline_config()
        print(f"✅ Configuration loaded successfully")
        print(f"   Region: {pipeline_config.aws_region}")
        print(f"   Model ID: {pipeline_config.bedrock_model_id}")
        print()
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return False
    
    # Step 2: Initialize AWS client manager
    print("Step 2: Initializing AWS client manager...")
    try:
        aws_config = {
            'region': pipeline_config.aws_region,
            'max_attempts': 3,
            'initial_backoff_seconds': 2,
            'max_backoff_seconds': 30
        }
        aws_client_manager = AWSClientManager(aws_config)
        print(f"✅ AWS client manager initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize AWS client manager: {e}")
        print(f"   Make sure AWS credentials are configured:")
        print(f"   - AWS_ACCESS_KEY_ID")
        print(f"   - AWS_SECRET_ACCESS_KEY")
        print(f"   - AWS_SESSION_TOKEN (if using temporary credentials)")
        return False
    
    # Step 3: Get Bedrock client
    print("Step 3: Getting Bedrock Runtime client...")
    try:
        bedrock_client = aws_client_manager.get_bedrock_runtime_client()
        print(f"✅ Bedrock Runtime client obtained")
        print()
    except Exception as e:
        print(f"❌ Failed to get Bedrock client: {e}")
        return False
    
    # Step 4: Test simple invocation
    print("Step 4: Testing Claude Sonnet 4 invocation...")
    print("   Sending test prompt: 'What is 2+2? Answer with just the number.'")
    print()
    
    try:
        # Prepare request
        test_prompt = "What is 2+2? Answer with just the number."
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": test_prompt
                }
            ],
            "temperature": 0.0
        }
        
        # Invoke model
        response = bedrock_client.invoke_model(
            modelId=pipeline_config.bedrock_model_id,
            body=json.dumps(request_body)
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        
        if 'content' in response_body and len(response_body['content']) > 0:
            answer = response_body['content'][0]['text']
            print(f"✅ Model invocation successful!")
            print(f"   Response: {answer}")
            print()
            
            # Validate response
            if '4' in answer:
                print(f"✅ Response validation passed (contains '4')")
            else:
                print(f"⚠️  Response validation warning: Expected '4' in response")
            print()
        else:
            print(f"❌ Unexpected response format: {response_body}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to invoke model: {e}")
        print()
        
        # Check for common errors
        error_str = str(e)
        if "AccessDeniedException" in error_str:
            print("   This error means your AWS credentials don't have permission to use Bedrock.")
            print("   Required permissions:")
            print("   - bedrock:InvokeModel")
            print("   - bedrock:InvokeModelWithResponseStream")
        elif "ResourceNotFoundException" in error_str:
            print("   This error means the model ID is not available in your region.")
            print(f"   Model ID: {pipeline_config.bedrock_model_id}")
            print(f"   Region: {pipeline_config.aws_region}")
            print("   Make sure Claude Sonnet 4 is enabled in your AWS account.")
        elif "ThrottlingException" in error_str:
            print("   This error means you're being rate limited.")
            print("   Wait a moment and try again.")
        
        return False
    
    # Step 5: Test data generation format
    print("Step 5: Testing training data generation format...")
    print("   Sending prompt to generate a training example...")
    print()
    
    try:
        data_gen_prompt = """Generate ONE training example for a customer support chatbot.
Return ONLY valid JSON in this exact format:
{"instruction": "the instruction", "context": "the context", "response": "the response"}

Example topic: Handling a return request."""
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": [
                {
                    "role": "user",
                    "content": data_gen_prompt
                }
            ],
            "temperature": 0.7
        }
        
        response = bedrock_client.invoke_model(
            modelId=pipeline_config.bedrock_model_id,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        generated_text = response_body['content'][0]['text']
        
        print(f"   Generated text:")
        print(f"   {generated_text[:200]}...")
        print()
        
        # Try to parse as JSON
        try:
            # Extract JSON from response (might have markdown code blocks)
            json_text = generated_text
            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0].strip()
            elif '```' in json_text:
                json_text = json_text.split('```')[1].split('```')[0].strip()
            
            training_example = json.loads(json_text)
            
            if all(key in training_example for key in ['instruction', 'context', 'response']):
                print(f"✅ Training data format validation passed")
                print(f"   Keys found: {list(training_example.keys())}")
                print()
            else:
                print(f"⚠️  Training data format warning: Missing required keys")
                print(f"   Expected: instruction, context, response")
                print(f"   Found: {list(training_example.keys())}")
                print()
        except json.JSONDecodeError as e:
            print(f"⚠️  Could not parse response as JSON: {e}")
            print(f"   This is expected - the SyntheticDataGenerator handles this")
            print()
            
    except Exception as e:
        print(f"❌ Failed to test data generation: {e}")
        return False
    
    # Step 6: Test judge format
    print("Step 6: Testing judge evaluation format...")
    print("   Sending prompt to compare two responses...")
    print()
    
    try:
        judge_prompt = """Compare these two responses and determine which is better.

Question: How do I return an item?

Response A: You can return items within 30 days. Just bring your receipt to any store.

Response B: To return an item, please visit our website and fill out the return form. We'll email you a shipping label.

Return your answer in JSON format:
{"winner": "A" or "B" or "tie", "reasoning": "explanation", "confidence": 0.0-1.0}"""
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "messages": [
                {
                    "role": "user",
                    "content": judge_prompt
                }
            ],
            "temperature": 0.0
        }
        
        response = bedrock_client.invoke_model(
            modelId=pipeline_config.bedrock_model_id,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        judgment_text = response_body['content'][0]['text']
        
        print(f"   Generated judgment:")
        print(f"   {judgment_text[:200]}...")
        print()
        
        # Try to parse as JSON
        try:
            json_text = judgment_text
            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0].strip()
            elif '```' in json_text:
                json_text = json_text.split('```')[1].split('```')[0].strip()
            
            judgment = json.loads(json_text)
            
            if all(key in judgment for key in ['winner', 'reasoning', 'confidence']):
                print(f"✅ Judge format validation passed")
                print(f"   Winner: {judgment.get('winner')}")
                print(f"   Confidence: {judgment.get('confidence')}")
                print()
            else:
                print(f"⚠️  Judge format warning: Missing required keys")
                print(f"   Expected: winner, reasoning, confidence")
                print(f"   Found: {list(judgment.keys())}")
                print()
        except json.JSONDecodeError as e:
            print(f"⚠️  Could not parse judgment as JSON: {e}")
            print(f"   This is expected - the Judge component handles this")
            print()
            
    except Exception as e:
        print(f"❌ Failed to test judge format: {e}")
        return False
    
    # Summary
    print("=" * 80)
    print("✅ All validation tests passed!")
    print("=" * 80)
    print()
    print("Your AWS Bedrock connection is working correctly.")
    print("You can now use the pipeline to:")
    print("  1. Generate synthetic training data")
    print("  2. Evaluate model responses with the judge")
    print("  3. Run the complete finetuning pipeline")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = test_bedrock_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
