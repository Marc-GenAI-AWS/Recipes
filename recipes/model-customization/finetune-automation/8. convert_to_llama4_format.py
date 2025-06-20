#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to convert home loan recommender JSONL data to Llama 4 Scout fine-tuning format.
"""

import json
import os
import argparse
from datetime import datetime

def convert_to_llama4_format(input_file, output_file=None):
    """
    Convert JSONL file from home loan recommender format to Llama 4 Scout fine-tuning format.
    
    Args:
        input_file (str): Path to input JSONL file
        output_file (str, optional): Path to output file. If None, will create in same directory
                                    with "_llama4" suffix.
    
    Returns:
        str: Path to output file
    """
    if output_file is None:
        # Create output filename with timestamp
        base_dir = os.path.dirname(input_file)
        base_name = os.path.basename(input_file).split('.')[0]
        timestamp = datetime.now().strftime("%m%d_%H%M")
        output_file = os.path.join(base_dir, f"{base_name}_llama4_{timestamp}.jsonl")
    
    converted_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as f_in, open(output_file, 'w', encoding='utf-8') as f_out:
        for line in f_in:
            try:
                # Parse the input JSON
                data = json.loads(line.strip())
                dialog = data.get("dialog", [])
                
                # Restructure for Llama 4 Scout format
                # The format requires a list of messages with role and content
                llama4_format = {
                    "messages": []
                }
                
                # Add each message to the Llama 4 format
                for message in dialog:
                    # Map roles if needed (system, user, assistant should be compatible)
                    llama4_format["messages"].append({
                        "role": message["role"],
                        "content": message["content"]
                    })
                
                # Write to output file
                f_out.write(json.dumps(llama4_format) + '\n')
                converted_count += 1
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")
                continue
            except KeyError as e:
                print(f"Missing key in data: {e}")
                continue
    
    print(f"Conversion complete: {converted_count} records converted")
    print(f"Output saved to: {output_file}")
    return output_file

def main():
    parser = argparse.ArgumentParser(description='Convert home loan recommender JSONL to Llama 4 Scout format')
    parser.add_argument('--input', '-i', required=True, help='Input JSONL file path')
    parser.add_argument('--output', '-o', help='Output file path (optional)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found")
        return
    
    convert_to_llama4_format(args.input, args.output)

if __name__ == "__main__":
    main()
