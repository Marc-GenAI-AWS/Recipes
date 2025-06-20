import ruamel.yaml 
import boto3
import os
import tarfile
import io

yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

with open("config.yaml", "r") as file:
    config = yaml.load(file)

AWS_REGION = config['aws_region']
SAGEMAKER_ARN_ROLE = config['sagemaker_role']
raw_model_path = config['model_files_s3_bucket']
use_case = config['use_case']

# Remove s3:// prefix if present and split into bucket and prefix
if raw_model_path.startswith('s3://'):
    raw_model_path = raw_model_path[5:]
    
# Split the S3 path into bucket and prefix
parts = raw_model_path.split('/', 1)
bucket_name = parts[0]
prefix = parts[1] if len(parts) > 1 else ''

# Define clean relative path for the compressed file
compressed_file_relative_path = f"finetuned-models/{use_case}/model_tar/model.tar.gz"

# Read the local inference.py file for possible replacement
local_inference_path = "inference.py"
local_inference_content = None
if os.path.exists(local_inference_path):
    with open(local_inference_path, "rb") as f:
        local_inference_content = f.read()
    print(f"Loaded local inference.py ({len(local_inference_content)} bytes) for possible replacement")

# Download files directly to memory and compress
with tarfile.open("/tmp/model.tar.gz", "w:gz") as tar:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    
    # Use proper keyword arguments for list_objects_v2
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    
    if "Contents" in response:
        objects = response["Contents"]
        
        # Track if we've seen inference.py and if it needs replacement
        inference_found = False
        needs_replacement = False
        
        # Keep track of files we've added to prevent duplicates
        added_files = set()
        
        # Define list of essential model file patterns and directories to exclude
        essential_patterns = ['pytorch_model.bin', 'model.safetensors', 'config.json', 'tokenizer', 
                          'special_tokens_map.json', 'inference.py', 'model.py', 'serving.properties',
                          'merges.txt', 'vocab.json']
        
        exclude_dirs = ['profiler-output', 'output/profiler', 'tensorboard']
        
        for obj in objects:
            key = obj["Key"]
            relative_path = key[len(prefix):].lstrip('/')
            
            # Skip files in excluded directories
            skip_file = False
            for excluded_dir in exclude_dirs:
                if excluded_dir in relative_path:
                    skip_file = True
                    print(f"Skipping non-essential file: {relative_path}")
                    break
                    
            # Skip files that don't match essential patterns
            if not skip_file:
                base_filename = os.path.basename(relative_path)
                is_essential = False
                
                # Check if file matches any essential pattern
                for pattern in essential_patterns:
                    if pattern in base_filename:
                        is_essential = True
                        break
                        
                if not is_essential:
                    skip_file = True
                    print(f"Skipping non-model file: {relative_path}")
                    
                # Skip file if we've already added a file with the same name
                if base_filename in added_files:
                    skip_file = True
                    print(f"Skipping duplicate file: {relative_path}")
            
            if skip_file:
                continue
                
            # Process inference.py specially - we'll defer adding it until the end
            if base_filename == "inference.py":
                inference_found = True
                # Get the file content but don't add it yet - we'll use local version if available
                file_response = s3.get_object(Bucket=bucket_name, Key=key)
                s3_inference_content = file_response["Body"].read()
                
                # Check if it's empty or very small
                if len(s3_inference_content) < 10:  # Less than 10 bytes is practically empty
                    print(f"Found empty or near-empty inference.py ({len(s3_inference_content)} bytes)")
                    needs_replacement = True
                    
                # Skip for now, we'll add the appropriate inference.py at the end
                skip_file = True
                print("Deferring inference.py addition - will add the appropriate version at the end")
            else:
                # For non-inference.py files, just get the content as before
                file_response = s3.get_object(Bucket=bucket_name, Key=key)
                file_content = file_response["Body"].read()
            
            if not skip_file:
                # Create a tar info object at the root level (just the base filename)
                tarinfo = tarfile.TarInfo(name=base_filename)
                tarinfo.size = len(file_content)
                
                # Add file to tar archive
                file_data = io.BytesIO(file_content)
                tar.addfile(tarinfo, fileobj=file_data)
                
                # Record that we added this file
                added_files.add(base_filename)
                print(f"Added {base_filename} (from {relative_path}) to archive root")
        
        # Now add the appropriate inference.py (local version preferred)
        if "inference.py" not in added_files:
            inference_content = None
            source = ""
            
            if local_inference_content:
                inference_content = local_inference_content
                source = "local file (preferred)"
            elif inference_found and not needs_replacement:
                inference_content = s3_inference_content
                source = "S3"
            
            if inference_content:
                tarinfo = tarfile.TarInfo(name="inference.py")
                tarinfo.size = len(inference_content)
                file_data = io.BytesIO(inference_content)
                tar.addfile(tarinfo, fileobj=file_data)
                added_files.add("inference.py")
                print(f"Added inference.py to archive root (from {source})")
            
        print(f"\nAll {len(added_files)} files will extract to the root level of the tarball (no subdirectories)")
        print(f"Files added: {', '.join(sorted(added_files))}")



# Check the contents of the tarball
print("\n======= Verifying tarball contents =======")
with tarfile.open("/tmp/model.tar.gz", "r:gz") as verify_tar:
    members = verify_tar.getmembers()
    print(f"Tarball contains {len(members)} files, all at root level:")
    for member in members:
        if '/' in member.name:
            print(f"WARNING: File not at root level: {member.name}")
        else:
            print(f"  - {member.name} ({member.size} bytes)")

# Upload compressed file using the clean relative path as the key
print(f"\nUploading compressed model to s3://{bucket_name}/{compressed_file_relative_path}")
s3.upload_file("/tmp/model.tar.gz", bucket_name, compressed_file_relative_path)
print("Upload complete")

# Store the full S3 path (without s3:// prefix) in the config
model_tar_s3_path = f"{bucket_name}/{compressed_file_relative_path}"

# Update the field we need to change
config['model_tar_s3_file_path'] = model_tar_s3_path
print(f"Updated config with model_tar_s3_file_path: {model_tar_s3_path}")

# Write back with field order preserved
with open("config.yaml", "w") as f:
    yaml.dump(config, f)