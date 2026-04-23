"""
Data loading utilities.
"""
import os
import json


def load_training_data(data_dir):
    """
    Load training data from the specified directory.
    
    SageMaker will download data from S3 to this directory
    before training starts.
    
    Args:
        data_dir: Path to training data directory
        
    Returns:
        List of training samples
    """
    print(f"Looking for data in: {data_dir}")
    
    # Check if directory exists
    if not os.path.exists(data_dir):
        print(f"Warning: {data_dir} does not exist. Using dummy data.")
        return generate_dummy_data(100)
    
    # List files in directory
    files = os.listdir(data_dir)
    print(f"Found files: {files}")
    
    if not files:
        print("No files found. Using dummy data.")
        return generate_dummy_data(100)
    
    # Load data based on file type
    data = []
    for filename in files:
        filepath = os.path.join(data_dir, filename)
        
        if filename.endswith('.json'):
            data.extend(load_json_file(filepath))
        elif filename.endswith('.csv'):
            data.extend(load_csv_file(filepath))
        elif filename.endswith('.txt'):
            data.extend(load_text_file(filepath))
        # Add more formats as needed (FASTA, SDF, etc.)
    
    if not data:
        print("No data loaded from files. Using dummy data.")
        return generate_dummy_data(100)
    
    return data


def load_json_file(filepath):
    """Load data from JSON file."""
    print(f"Loading JSON: {filepath}")
    with open(filepath, 'r') as f:
        return json.load(f)


def load_csv_file(filepath):
    """Load data from CSV file."""
    print(f"Loading CSV: {filepath}")
    data = []
    with open(filepath, 'r') as f:
        header = f.readline().strip().split(',')
        for line in f:
            values = line.strip().split(',')
            data.append(dict(zip(header, values)))
    return data


def load_text_file(filepath):
    """Load data from text file (one sample per line)."""
    print(f"Loading TXT: {filepath}")
    with open(filepath, 'r') as f:
        return [line.strip() for line in f if line.strip()]


def generate_dummy_data(n_samples):
    """
    Generate dummy data for testing.
    
    Replace with your actual data format.
    """
    print(f"Generating {n_samples} dummy samples")
    return [{"id": i, "value": f"sample_{i}"} for i in range(n_samples)]
