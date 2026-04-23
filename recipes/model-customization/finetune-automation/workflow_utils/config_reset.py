"""
Configuration Reset Utilities

This module provides functions to reset or modify the configuration YAML file
used in the LLM fine-tuning workflow.
"""

import os
import sys
import ruamel.yaml

def reset_workflow_config(config_path='config.yaml'):
    """
    Reset workflow-generated configuration fields in the config.yaml file.
    
    This function removes or resets fields that are generated during the workflow process,
    allowing for a clean slate before starting a new workflow run.
    
    Args:
        config_path (str): Path to the configuration YAML file. Defaults to 'config.yaml'.
        
    Returns:
        bool: True if reset was successful, False otherwise.
    """
    try:
        # Set up ruamel.yaml to preserve formatting and comments
        yaml = ruamel.yaml.YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)
        
        # Load existing config
        with open(config_path, 'r') as file:
            config = yaml.load(file)
        
        # Fields to reset (set to empty value)
        fields_to_reset = [
            'use_case',
            'uri_for_uploaded_s3_input_data',
            'model_tar_s3_file_path',
            'output_model_files_s3_bucket',
            'model_name',
            'model_files_s3_bucket',
            'input_data_s3_file_path',
            'endpoint_name',
            'data_config_file'
        ]
        
        # Reset each field
        for field in fields_to_reset:
            if field in config:
                config[field] = ""
        
        # Write back to the file
        with open(config_path, 'w') as file:
            yaml.dump(config, file)
        
        print(f"Successfully reset workflow configuration in {config_path}")
        return True
        
    except Exception as e:
        print(f"Error resetting configuration: {e}")
        return False

if __name__ == "__main__":
    # If script is run directly, reset the config file
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    reset_workflow_config(config_path)
