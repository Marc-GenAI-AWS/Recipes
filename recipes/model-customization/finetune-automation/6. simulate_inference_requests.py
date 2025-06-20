import boto3
import json
import time
import os
import sys
import yaml

# Load configuration
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

# Extract configuration values
# Override endpoint name with the one that works (from static example)
ENDPOINT_NAME = config['endpoint_name']  # Using endpoint name from working example
REGION = config['aws_region']
s3_uri = config['uri_for_uploaded_s3_input_data']

# Use default AWS credentials from environment or config

def split_s3_path(s3_path):
    # Remove the "s3://" prefix
    path = s3_path.replace("s3://", "", 1)
    # Split at the first slash to separate bucket and key
    bucket, _, key = path.partition("/")
    return bucket, key

bucket, key = split_s3_path(s3_uri)

print("Bucket:", bucket)  # my-bucket-name
print("Key:", key)        # path/to/my/object.jsonl


def query_endpoint(payload):
    client = boto3.client(
        "sagemaker-runtime", 
        region_name=REGION
    )
    response = client.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps(payload)
    )
    result = response["Body"].read().decode("utf-8")
    return json.loads(result)

def main():
    # Check if endpoint name is provided
    if not ENDPOINT_NAME:
        print("ERROR: No endpoint name provided in config.yaml")
        return 1
        
    # Print header with information about the simulation
    print("\n" + "="*50)
    print(f"INFERENCE SIMULATION")
    print("="*50)
    print(f"Endpoint: {ENDPOINT_NAME}")
    print(f"Region: {REGION}")
    print(f"Input data: {s3_uri}")
    print("="*50 + "\n")
    
    try:
        # Get all data lines first
        s3 = boto3.client(
            "s3", 
            region_name=REGION
        )
        response = s3.get_object(Bucket=bucket, Key=key)
        
        # Read all lines and decode them properly
        all_lines = []
        for line in response["Body"].iter_lines():
            if line:  # Skip empty lines
                all_lines.append(line)
        
        total_lines = len(all_lines)
        print(f"Found {total_lines} requests to process\n")
        
        # Limit the number of requests for testing if needed
        max_requests = 5  # Set to None to process all requests
        processing_lines = all_lines[:max_requests] if max_requests else all_lines
        
        # Process each line
        for line_num, line in enumerate(processing_lines, 1):
            try:
                # Decode bytes to string before parsing JSON
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                
                # Parse the JSON data    
                try:
                    sample = json.loads(line)
                    payload = {"dialog": sample["dialog"]}
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"ERROR: Invalid JSON or missing dialog field in line {line_num}: {e}")
                    continue
                
                print(f"===== REQUEST {line_num} =====")
                print(json.dumps(payload, indent=2))
                print("\n")
                
                print(f"===== SUBMITTING REQUEST {line_num} =====")
                result = query_endpoint(payload)
                
                print(f"===== RESPONSE {line_num} =====")
                print(json.dumps(result, indent=2))
                print("\n")
                
                # Force stdout to flush to make sure output is captured
                sys.stdout.flush()
                
                # Sleep to avoid rate limiting (except for last request)
                if line_num < total_lines:
                    print(f"Waiting 10 seconds before next request...\n")
                    time.sleep(10)
                    
            except Exception as e:
                print(f"===== ERROR ON REQUEST {line_num} =====")
                print(f"Error: {str(e)}")
                print("\n")
                sys.stdout.flush()
    except Exception as e:
        print(f"===== FATAL ERROR =====")
        print(f"Failed to process S3 data: {str(e)}")
        print("\n")
        return 1
        
    print("===== INFERENCE SIMULATION COMPLETE =====\n")
    return 0
    
if __name__ == "__main__":
    main()
