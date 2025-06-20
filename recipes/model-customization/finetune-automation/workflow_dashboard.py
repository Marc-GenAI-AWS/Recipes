import streamlit as st
import requests

# Set page configuration - must be first Streamlit command
st.set_page_config(
    page_title="LLM Fine-tuning Workflow Dashboard",
    page_icon="🤖",
    layout="wide"
)

# Retro Wave Theme styling
def apply_retro_wave_theme():
    st.markdown('''
    <style>
    /* New Retro Wave Styling */
    
    /* Gradient backgrounds and glow effects */
    .stApp {
        background: linear-gradient(180deg, #3B1F90 0%, #3B1F90 85%, #F216B7 100%);
    }
    
    /* Neon headers with moderate glow effect */
    h1, h2, h3 {
        color: #61ECFF !important;
        text-shadow: 0 0 5px rgba(97, 236, 255, 0.5), 0 0 8px rgba(97, 236, 255, 0.3);
        font-weight: bold !important;
    }
    
    /* Buttons styling - toned down */
    .stButton>button {
        background: #F216B7 !important; /* Brighter pink */
        color: white !important;
        border: 1px solid #61ECFF !important;
        border-radius: 4px !important;
        box-shadow: 0 0 5px rgba(242, 22, 183, 0.4) !important;
        transition: all 0.3s !important;
    }
    
    .stButton>button:hover {
        background: #F216B7 !important; /* Same pink as regular state */
        box-shadow: 0 0 8px rgba(97, 236, 255, 0.5) !important;
        transform: translateY(-1px) !important;
    }
    
    /* Sidebar gradient */
    [data-testid=stSidebar] {
        background: linear-gradient(180deg, #5227B3 0%, #3B1F90 100%) !important;
        border-right: 2px solid #61ECFF;
    }
    
    /* Input fields */
    .stTextInput>div>div>input, .stSelectbox>div>div>input {
        background-color: rgba(59, 31, 144, 0.3) !important;
        border: 1px solid #61ECFF !important;
        color: white !important;
    }
    
    /* Code blocks with neon border */
    .stCodeBlock {
        border: 1px solid #61ECFF !important;
        box-shadow: 0 0 10px rgba(97, 236, 255, 0.5) !important;
    }
    
    /* Progress bar */
    .stProgress > div > div > div > div {
        background-color: #EF49F2 !important;
        background-image: linear-gradient(to right, #EF49F2, #61ECFF) !important;
    }
    
    /* Divider line */
    hr {
        border-top: 2px solid #61ECFF !important;
        box-shadow: 0 0 8px #61ECFF !important;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(59, 31, 144, 0.6) !important;
        border-radius: 4px 4px 0 0 !important;
        border: 1px solid #61ECFF !important;
        border-bottom: none !important;
        color: white !important;
        padding: 10px 20px !important;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #F216B7 !important;
        box-shadow: 0 0 10px #F216B7 !important;
        font-weight: bold !important;
    }
    
    /* Logo and title */
    .title-container {
        display: flex;
        align-items: center;
        background: linear-gradient(90deg, #F216B7, #5715BD);
        padding: 10px;
        margin-bottom: 20px;
        border-radius: 5px;
        border: 1px solid #61ECFF;
        box-shadow: 0 0 8px #61ECFF;
    }
    
    /* Custom Start Here header styling with green glow */
    .start-here-header {
        color: #00FF66 !important;
        text-shadow: 0 0 10px rgba(0, 255, 102, 0.8), 0 0 15px rgba(0, 255, 102, 0.6) !important;
        font-weight: bold !important;
        margin-bottom: 15px !important;
        font-size: 1.3em !important;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { text-shadow: 0 0 10px rgba(0, 255, 102, 0.8), 0 0 15px rgba(0, 255, 102, 0.6); }
        50% { text-shadow: 0 0 15px rgba(0, 255, 102, 0.9), 0 0 20px rgba(0, 255, 102, 0.7); }
        100% { text-shadow: 0 0 10px rgba(0, 255, 102, 0.8), 0 0 15px rgba(0, 255, 102, 0.6); }
    }
    
    .logo-text {
        font-size: 2.2rem !important;
        font-weight: bold !important;
        color: #7CFFFF !important; /* Slightly brighter blue */
        margin: 0 !important;
        text-shadow: 0px 0px 5px rgba(97, 236, 255, 0.4), 0 0 10px rgba(97, 236, 255, 0.2);
        letter-spacing: 1px; /* Spread out letters slightly for better readability */
    }
    
    /* Inference response styling */
    .inference-container {
        border: 1px solid #61ECFF;
        border-radius: 6px;
        box-shadow: 0 0 10px rgba(97, 236, 255, 0.4);
        padding: 15px;
        margin: 10px 0;
        background-color: rgba(59, 31, 144, 0.3);
        max-height: 500px;
        overflow-y: auto;
    }
    
    .response-item {
        padding: 12px;
        margin-bottom: 25px;
        background-color: rgba(59, 31, 144, 0.5);
        border-radius: 8px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
    }
    
    .response-item h4 {
        color: #61ECFF !important;
        margin: 5px 0 10px 0;
        font-size: 1.1rem;
        text-shadow: 0 0 5px rgba(97, 236, 255, 0.3);
        padding-bottom: 5px;
        border-bottom: 1px solid rgba(97, 236, 255, 0.3);
    }
    
    .response-item pre {
        background-color: rgba(0, 0, 0, 0.2);
        padding: 10px;
        border-radius: 4px;
        overflow-x: auto;
        border: 1px solid rgba(97, 236, 255, 0.2);
    }
    
    /* Conversation styling */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    
    .chat-message {
        padding: 10px 15px;
        border-radius: 18px;
        max-width: 85%;
        word-wrap: break-word;
        margin: 4px 0;
    }
    
    .user-message {
        background-color: rgba(242, 22, 183, 0.3);
        color: white;
        align-self: flex-end;
        margin-left: auto;
        border: 1px solid rgba(242, 22, 183, 0.5);
        text-align: right;
    }
    
    .assistant-message {
        background-color: rgba(97, 236, 255, 0.2);
        color: #00FF66;
        align-self: flex-start;
        margin-right: auto;
        border: 1px solid rgba(97, 236, 255, 0.3);
    }
    </style>
    ''', unsafe_allow_html=True)

# Apply custom styling
apply_retro_wave_theme()
import os
import sys
from workflow_utils import reset_workflow_config
import glob
import yaml
import ruamel.yaml
import subprocess
import time
import boto3
import json
from pathlib import Path
from datetime import datetime

# Title is now handled by st.title below

# Constants
CONFIG_DIR = "data_gen_configs"
CONFIG_FILE = "config.yaml"
LOG_DIR = "workflow_logs"

# Make sure the log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

def load_config():
    """Load the current config.yaml file using ruamel.yaml to preserve formatting and order."""
    yaml_handler = ruamel.yaml.YAML()
    yaml_handler.preserve_quotes = True
    yaml_handler.indent(mapping=2, sequence=4, offset=2)
    
    try:
        with open(CONFIG_FILE, "r") as f:
            return yaml_handler.load(f)
    except Exception as e:
        st.error(f"Error loading config.yaml: {e}")
        return {}

def save_config(config):
    """Save config.yaml using ruamel.yaml to preserve formatting and order."""
    yaml_handler = ruamel.yaml.YAML()
    yaml_handler.preserve_quotes = True
    yaml_handler.indent(mapping=2, sequence=4, offset=2)
    
    try:
        with open(CONFIG_FILE, "w") as f:
            yaml_handler.dump(config, f)
        return True
    except Exception as e:
        st.error(f"Error saving config.yaml: {e}")
        return False

def get_available_usecases():
    """Get all available use case config files."""
    config_files = glob.glob(f"{CONFIG_DIR}/*.yaml")
    usecases = []
    
    for config_file in config_files:
        try:
            with open(config_file, "r") as f:
                domain_config = yaml.safe_load(f)
                domain_name = domain_config.get("domain_name", os.path.basename(config_file))
                description = domain_config.get("description", "No description available")
                usecases.append({
                    "path": config_file,
                    "name": domain_name,
                    "description": description
                })
        except Exception as e:
            st.warning(f"Could not read {config_file}: {e}")
    
    return usecases

def update_config_for_usecase(usecase_path, custom_name=None):
    """Update config.yaml for the selected use case and optional custom name."""
    config = load_config()
    
    # Extract domain name from the config file
    try:
        with open(usecase_path, "r") as f:
            domain_config = yaml.safe_load(f)
            domain_name = domain_config.get("domain_name", "unknown")
    except:
        domain_name = os.path.basename(usecase_path).split(".")[0]
    
    # Use custom name if provided, otherwise use the name from config
    if custom_name:
        use_case_name = custom_name.replace("_", "-")  # Always use hyphens for SageMaker compatibility
    else:
        use_case_name = domain_name.replace("_", "-")
    
    # Update key config values
    config["data_config_file"] = usecase_path
    config["use_case"] = use_case_name
    
    # Try to find data files both by domain name and custom name
    found_data = False
    search_paths = []
    if domain_name:
        search_paths.append(f"usecase_data/{domain_name}")
        search_paths.append(f"usecase_data/{domain_name.replace('-', '_')}")
    
    if custom_name:
        search_paths.append(f"usecase_data/{custom_name}")
        search_paths.append(f"usecase_data/{custom_name.replace('-', '_')}")
    
    # Look for data files in all possible locations
    for path in search_paths:
        if os.path.exists(path):
            data_files = glob.glob(f"{path}/*.jsonl")
            if data_files:
                latest_file = max(data_files, key=os.path.getctime)
                config["local_input_data_path"] = latest_file
                found_data = True
                break
    
    return save_config(config)

def run_script(script_name, capture_output=True):
    """Run a Python script and return its output."""
    log_file = f"{LOG_DIR}/{script_name.replace(' ', '_').replace('.', '')}_{datetime.now().strftime('%m%d_%H%M')}.log"
    
    st.info(f"Running {script_name}...")
    process = subprocess.Popen(
        [sys.executable, script_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Create a placeholder for live output
    output_placeholder = st.empty()
    
    # For storing the complete output
    complete_output = []
    
    # Real-time output display with log writing
    with open(log_file, "w") as log:
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
                
            if line:
                complete_output.append(line)
                log.write(line)
                log.flush()
                
                # Display the last 20 lines for better UI experience
                display_lines = complete_output[-20:] if len(complete_output) > 20 else complete_output
                output_placeholder.code("".join(display_lines))
    
    # Final output status
    if process.returncode == 0:
        st.success(f"{script_name} completed successfully!")
    else:
        st.error(f"{script_name} failed with return code {process.returncode}")
    
    return "".join(complete_output), process.returncode, log_file

# Function to check endpoint status
def check_endpoint_status(endpoint_name):
    """Check if a SageMaker endpoint is in service"""
    if not endpoint_name:
        return "No Endpoint Configured", "⚠️"
    
    try:
        # Get the AWS region from config
        with open("config.yaml", "r") as file:
            config_data = yaml.safe_load(file)
        aws_region = config_data.get('aws_region', 'us-west-2')
        
        # Create a SageMaker client
        sm_client = boto3.client('sagemaker', region_name=aws_region)
        
        # Describe the endpoint
        response = sm_client.describe_endpoint(EndpointName=endpoint_name)
        
        # Get the endpoint status
        status = response['EndpointStatus']
        
        # Return status and icon
        if status == 'InService':
            return "In Service", "✅"
        elif status == 'Creating':
            return "Creating", "⏳"
        elif status == 'Updating':
            return "Updating", "⏳"
        elif status == 'Failed':
            return "Failed", "❌"
        else:
            return status, "❓"
    
    except Exception as e:
        if "Could not find endpoint" in str(e):
            return "Not Found", "❌"
        return f"Error: {str(e)[:50]}...", "❌"

# Main App

st.title("🤖 LLM Fine-tuning Workflow Dashboard")
st.write("This dashboard lets you select use cases and run the fine-tuning workflow steps.")

# Get current config and available use cases
current_config = load_config()
usecases = get_available_usecases()

# Sidebar - Use Case Selection
st.sidebar.markdown('<div class="start-here-header">Start Here: Initialize Use Case</div>', unsafe_allow_html=True)

# Use a container for the selectbox and refresh button
use_case_container = st.sidebar.container()
use_case_col1, use_case_col2 = use_case_container.columns([5, 1])

# Session state to track if refresh was clicked
if 'refresh_usecases' not in st.session_state:
    st.session_state.refresh_usecases = False

# Function to reload use cases
def refresh_use_cases():
    st.session_state.refresh_usecases = True
    st.session_state.usecases = get_available_usecases()
    
# Add refresh button
if use_case_col2.button("🔄", key="refresh_usecases_btn", help="Refresh available use cases"):
    refresh_use_cases()
    
# If we're coming from the Usecase Creation tab and have a new config to select
if 'select_new_config' in st.session_state and st.session_state.select_new_config:
    refresh_use_cases()
    # Reset the flag so we don't refresh every time
    st.session_state.select_new_config = False

# Get fresh list of usecases if needed
if st.session_state.refresh_usecases:
    usecases = st.session_state.usecases
    st.session_state.refresh_usecases = False

selected_usecase = use_case_col1.selectbox(
    "Select a use case",
    options=[uc["path"] for uc in usecases],
    format_func=lambda x: next((uc["name"] for uc in usecases if uc["path"] == x), x)
)

# Show use case description
selected_uc_info = next((uc for uc in usecases if uc["path"] == selected_usecase), None)
if selected_uc_info:
    st.sidebar.write(f"**Description**: {selected_uc_info['description']}")

# Custom use case name input
st.sidebar.subheader("Custom Use Case Name (Optional)")
custom_name = st.sidebar.text_input(
    "Enter a custom name for this use case",
    help="Leave blank to use the name from the config file. Name will have underscores replaced with hyphens for SageMaker compatibility."
)

# Update config button
if st.sidebar.button("📝 Update Config for Selected Use Case", key="update_config_btn"):
    if update_config_for_usecase(selected_usecase, custom_name if custom_name else None):
        if custom_name:
            st.sidebar.success(f"Config updated with custom name: {custom_name}!")
        else:
            st.sidebar.success(f"Config updated for {selected_uc_info['name']}!")
        # Reload config to show updated values
        current_config = load_config()
    else:
        st.sidebar.error("Failed to update config!")

# Show current configuration settings
st.sidebar.header("Current Config")
st.sidebar.write(f"**Use Case**: {current_config.get('use_case', 'Not set')}")
st.sidebar.write(f"**Config File**: {current_config.get('data_config_file', 'Not set')}")
st.sidebar.write(f"**Data Count**: {current_config.get('count_synthetic_data', 'Not set')}")

# Add reset configuration button
st.sidebar.divider()
st.sidebar.subheader("Reset Configuration")
with st.sidebar.expander("Reset Workflow Configuration"):
    st.write("This will reset all workflow-generated fields in the configuration file.")
    st.write("⚠️ **Warning:** This action cannot be undone.")
    if st.button("🔄 Reset Config", key="reset_config_btn"):
        if reset_workflow_config():
            st.success("Configuration reset successfully!")
            # Reload config to show updated values
            current_config = load_config()
        else:
            st.error("Failed to reset configuration!")

# Initialize tab structure - ensure each tab has a unique name and ID
data_tab, model_tab, deploy_tab, registry_tab, usecase_tab = st.tabs(["Data Generation", "Model Finetune", "Deploy & Simulate", "Model Registry", "Usecase Creation"])

# Tab 1: Data Generation
with data_tab:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("Step 1: Generate Synthetic Data")
        st.write("Generate synthetic training data based on the selected use case.")
    with col2:
        st.markdown(f"**Current Use Case:** {current_config.get('use_case', 'Not set')}")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        data_count = st.number_input("Data Count", min_value=10, max_value=2000, value=int(current_config.get('count_synthetic_data', 500)))
    
    if st.button("🔄 Generate Synthetic Data", key="generate_data_btn"):
        # Update count in config if needed
        if data_count != int(current_config.get('count_synthetic_data', 500)):
            current_config['count_synthetic_data'] = data_count
            save_config(current_config)
        
        output, returncode, log_file = run_script("1. generate_synthetic_data.py")
        if returncode == 0:
            st.success("Data generation complete! Check the logs tab for details.")
        else:
            st.error("Data generation failed. Check the logs for errors.")

    st.divider()
    st.header("Step 2: Upload Data to S3")
    st.write("Upload the generated data to your S3 bucket for training.")
    
    if st.button("☁️ Upload to S3", key="upload_s3_btn"):
        output, returncode, log_file = run_script("2. upload_to_s3.py")
        if returncode == 0:
            st.success("S3 upload complete!")
            # Reload config to show updated values
            current_config = load_config()
        else:
            st.error("S3 upload failed. Check the logs for errors.")
            
    st.divider()
    st.header("🔄 Use Existing Data")
    st.write("Choose data from an existing use case instead of generating new data.")
    
    # Helper function to get existing use case data folders
    def get_existing_usecase_data():
        usecase_data_dir = os.path.join(os.path.dirname(__file__), "usecase_data")
        if not os.path.exists(usecase_data_dir):
            return []
            
        # Get all directories in the usecase_data folder
        usecase_folders = [f for f in os.listdir(usecase_data_dir) 
                          if os.path.isdir(os.path.join(usecase_data_dir, f))]
        
        # Get data details for each usecase
        usecase_data = []
        for folder in usecase_folders:
            folder_path = os.path.join(usecase_data_dir, folder)
            data_files = [f for f in os.listdir(folder_path) 
                         if os.path.isfile(os.path.join(folder_path, f)) and (f.endswith('.json') or f.endswith('.jsonl'))]
            
            # Get the file count and date of most recent file
            if data_files:
                most_recent = max([os.path.getmtime(os.path.join(folder_path, f)) for f in data_files])
                most_recent_date = datetime.fromtimestamp(most_recent).strftime('%Y-%m-%d')
                file_count = len(data_files)
            else:
                most_recent_date = 'Unknown'
                file_count = 0
                
            usecase_data.append({
                "name": folder.replace('_', ' ').title(),
                "folder": folder,
                "file_count": file_count,
                "last_modified": most_recent_date
            })
        
        return usecase_data
    
    # Get existing data
    usecase_data = get_existing_usecase_data()
    
    if not usecase_data:
        st.info("No existing use case data found in the 'usecase_data' directory.")
    else:
        # Create a selectbox with existing data options
        import pandas as pd
        
        # Create options for the dropdown
        options = ["-- Select existing data --"] + [f"{data['name']} ({data['file_count']} files, updated {data['last_modified']})" for data in usecase_data]
        
        # Create a mapping from display name back to folder name
        folder_mapping = {f"{data['name']} ({data['file_count']} files, updated {data['last_modified']})": data['folder'] for data in usecase_data}
        
        # Display a dropdown selector
        col1, col2 = st.columns([3, 1])
        with col1:
            selected_option = st.selectbox(
                "Select existing data to use:",
                options,
                key="existing_data_dropdown"
            )
        
        # If an option is selected (not the default)
        if selected_option != "-- Select existing data --":
            selected_folder = folder_mapping[selected_option]
            
            # Find the data info for the selected folder
            selected_data = next((data for data in usecase_data if data['folder'] == selected_folder), None)
            
            if selected_data:
                with col2:
                    # Button to use the selected data
                    if st.button("Use This Data", key="use_existing_data_btn"):
                        # Update the config to match the selected data
                        config = load_config()
                        config['use_case'] = selected_folder
                        
                        # Find matching config file if it exists
                        config_dir = os.path.join(os.path.dirname(__file__), "data_gen_configs")
                        matching_configs = [f for f in os.listdir(config_dir) 
                                         if f.startswith(selected_folder) and f.endswith('.yaml')]
                        
                        if matching_configs:
                            # Use the most recent config file if multiple exist
                            matching_configs.sort(reverse=True)
                            config['data_config_file'] = os.path.join(config_dir, matching_configs[0])
                            
                        # Set the data location to the existing data
                        usecase_data_dir = os.path.join(os.path.dirname(__file__), "usecase_data", selected_folder)
                        config['data_location'] = usecase_data_dir
                        config['using_existing_data'] = True
                        
                        # Save the updated config
                        save_config(config)
                        st.success(f"Config updated to use existing '{selected_data['name']}' data!")
                        
                        # Reload config to show updated values
                        current_config = load_config()
                
                # Data preview section
                st.subheader("Data Preview")
                
                # Get the data files from the selected folder
                usecase_data_dir = os.path.join(os.path.dirname(__file__), "usecase_data", selected_folder)
                data_files = [f for f in os.listdir(usecase_data_dir) 
                             if os.path.isfile(os.path.join(usecase_data_dir, f)) and (f.endswith('.json') or f.endswith('.jsonl'))]
                
                if not data_files:
                    st.info(f"No data files found in the {selected_data['name']} folder.")
                else:
                    # Sort by modification time (newest first)
                    data_files.sort(key=lambda f: os.path.getmtime(os.path.join(usecase_data_dir, f)), reverse=True)
                    
                    # Show a sample of the data (up to 5 files)
                    sample_files = data_files[:5]
                    
                    for i, file in enumerate(sample_files):
                        file_path = os.path.join(usecase_data_dir, file)
                        
                        # Display in an expander
                        with st.expander(f"File: {file}", expanded=(i == 0)):
                            try:
                                if file.endswith('.jsonl'):
                                    # Handle JSONL files (one JSON object per line)
                                    with open(file_path, 'r') as f:
                                        lines = f.readlines()
                                    
                                    # Show only the first record as a sample
                                    if lines:  # Make sure there's at least one line
                                        st.write(f"Sample record (1 of {len(lines)} records in file)")
                                        try:
                                            first_record = json.loads(lines[0].strip())
                                            st.json(first_record)
                                        except json.JSONDecodeError:
                                            st.error("Error parsing the sample record")
                                            # Show raw content if JSON parsing fails
                                            try:
                                                st.code(lines[0][:1000], language="json")
                                            except Exception:
                                                pass
                                    else:
                                        st.info("This JSONL file appears to be empty.")
                                else:
                                    # Handle regular JSON files
                                    with open(file_path, 'r') as f:
                                        file_content = json.load(f)
                                        st.json(file_content)
                            except Exception as e:
                                st.error(f"Error loading file: {str(e)}")
                                # Show raw content if JSON parsing fails
                                try:
                                    with open(file_path, 'r') as f:
                                        st.code(f.read()[:1000], language="json")
                                        if os.path.getsize(file_path) > 1000:
                                            st.write("... (content truncated)")
                                except Exception:
                                    pass
                    
                    if len(data_files) > 5:
                        st.info(f"Showing 5 of {len(data_files)} files. {len(data_files) - 5} more files are available.")


# Tab 2: AWS & Training (Legacy - to be removed)
with model_tab:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("Step 3: Fine-tune LLM")
        st.write("Train your LLM on the synthetic data using SageMaker.")
    with col2:
        st.markdown(f"**Current Use Case:** {current_config.get('use_case', 'Not set')}")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        epochs = st.number_input("Training Epochs", min_value=1, max_value=10, value=int(current_config.get('epochs', 3)))
    with col2:
        learning_rate = st.text_input("Learning Rate", value=str(current_config.get('learning_rate', '2e-5')))
    
    if st.button("🤖 Start Fine-tuning", key="start_finetuning_btn"):
        # Update parameters in config if changed
        if epochs != int(current_config.get('epochs', 3)) or learning_rate != str(current_config.get('learning_rate', '2e-5')):
            current_config['epochs'] = epochs
            current_config['learning_rate'] = learning_rate
            save_config(current_config)
        
        output, returncode, log_file = run_script("3. finetune_llm.py")
        if returncode == 0:
            st.success("Fine-tuning job submitted successfully!")
            # Reload config to show updated values
            current_config = load_config()
        else:
            st.error("Fine-tuning submission failed. Check the logs for errors.")
    
    st.divider()
    st.header("Step 4: Compress Model")
    st.write("Compress and prepare the model files for deployment.")
    
    if st.button("📦 Compress Model Files", key="compress_model_btn"):
        output, returncode, log_file = run_script("4. compress_model_files.py")
        if returncode == 0:
            st.success("Model compression complete!")
            # Reload config to show updated values
            current_config = load_config()
        else:
            st.error("Model compression failed. Check the logs for errors.")

# Tab 3: Deployment
with deploy_tab:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("Step 5: Deploy Model")
        st.write("Deploy the fine-tuned model to a SageMaker endpoint.")
    with col2:
        st.markdown(f"**Current Use Case:** {current_config.get('use_case', 'Not set')}")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        endpoint_name = st.text_input("Endpoint Name (Optional)", 
                                      value=current_config.get('endpoint_name', f"{current_config.get('use_case', 'model')}-endpoint-{int(time.time())%10000}"))
    
    if st.button("🚀 Deploy Model", key="deploy_model_btn"):
        output, returncode, log_file = run_script("5. model_build_deploy_inference.py")
        if returncode == 0:
            st.success("Model deployed successfully!")
            # Reload config to show updated values
            current_config = load_config()
        else:
            st.error("Model deployment failed. Check the logs for errors.")
    
    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("Step 6: Simulate Inference")
        st.write("Simulate requests to the deployed model endpoint.")
    
    # Get the endpoint name from config and check its status
    endpoint_name = current_config.get('endpoint_name', '')
    status_text, status_icon = check_endpoint_status(endpoint_name)
    
    with col2:
        st.markdown(f"**Current Use Case:** {current_config.get('use_case', 'Not set')}")
        st.markdown(f"**Endpoint:** {endpoint_name}")
        st.markdown(f"**Status:** {status_icon} {status_text}")
    
    # Create placeholder for inference responses
    inference_response_container = st.empty()
    
    if st.button("🔍 Run Inference Simulation", key="run_inference_btn"):
        # Create an expander to show real-time responses
        with st.expander("Inference Responses", expanded=True):
            # Create a container for responses with custom styling
            st.markdown("<div class='inference-container' style='max-height: 400px; overflow-y: auto;'>", unsafe_allow_html=True)
            response_placeholder = st.empty()
            
            # Run the inference script
            output, returncode, log_file = run_script("6. simulate_inference_requests.py")
            
            if returncode == 0:
                st.success("Inference tests completed successfully!")
                
                # Show raw output for debugging
                with st.expander("Debug: Raw Output", expanded=True):
                    st.code(output)
                    
                    # Show number of lines in output
                    line_count = len(output.split('\n'))
                    st.write(f"Output contains {line_count} lines")
                
                # Parse the output to extract the responses
                responses = []
                response_text = ""
                lines = output.split('\n')
                
                # New parser for the formatted output
                current_section = None
                current_request_num = None
                current_json = ""
                current_request_json = None
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    
                    # Skip empty lines
                    if not line:
                        continue
                        
                    # Detect section headers
                    if line.startswith("===== REQUEST"):
                        current_section = "request"
                        current_request_num = line.replace("===== REQUEST ", "").replace(" =====", "").strip()
                        current_json = ""
                        continue
                        
                    elif line.startswith("===== RESPONSE"):
                        current_section = "response"
                        current_json = ""
                        continue
                        
                    elif line.startswith("===== "):
                        # Another header, not request or response
                        current_section = None
                        continue
                    
                    # Collect JSON content based on current section
                    if current_section == "request" and (line.startswith('{') or line.startswith('[') or 
                                                       line.startswith('"') or line.startswith('}') or 
                                                       line.startswith(']')):
                        current_json += line
                        
                        # Try to parse complete JSON
                        if (current_json.count('{') == current_json.count('}') and 
                            (i == len(lines)-1 or lines[i+1].strip() == "" or lines[i+1].startswith("====="))):
                            try:
                                current_request_json = json.loads(current_json)
                            except json.JSONDecodeError:
                                pass
                            
                    elif current_section == "response" and (line.startswith('{') or line.startswith('[') or 
                                                          line.startswith('"') or line.startswith('}') or 
                                                          line.startswith(']')):
                        current_json += line
                        
                        # Try to parse complete JSON and create response entry
                        if (current_json.count('{') == current_json.count('}') and 
                            (i == len(lines)-1 or lines[i+1].strip() == "" or lines[i+1].startswith("====="))):
                            try:
                                response_json = json.loads(current_json)
                                
                                # Create formatted response item with conversational UI
                                response_text += f"<div class='response-item'>"
                                response_text += f"<h4>Inference Simulation #{current_request_num}</h4>"
                                
                                # Format as conversation if dialog field exists
                                chat_text = "<div class='chat-container'>"
                                try:
                                    # Extract dialog from request payload
                                    if 'dialog' in current_request_json:
                                        dialog = current_request_json['dialog']
                                        for turn in dialog:
                                            role = turn.get('role', '')
                                            content = turn.get('content', '')
                                            
                                            # Format messages based on role
                                            if role.lower() == 'user':
                                                chat_text += f"<div class='chat-message user-message'>{content}</div>"
                                            elif role.lower() == 'assistant':
                                                chat_text += f"<div class='chat-message assistant-message'>{content}</div>"
                                    
                                    # Add the model's new response as a highlighted message
                                    if 'generation' in response_json:
                                        model_response = response_json['generation']
                                        chat_text += f"<div class='chat-message assistant-message' style='border: 2px solid #00FF66; box-shadow: 0 0 10px rgba(0, 255, 102, 0.5);'>{model_response}</div>"
                                    
                                except Exception as e:
                                    chat_text += f"<div style='color:#F216B7;'>Error parsing conversation: {str(e)}</div>"
                                
                                chat_text += "</div>"
                                response_text += chat_text
                                
                                # Add expandable raw JSON for debugging
                                response_text += f"<details><summary style='color:#61ECFF; cursor:pointer; margin-top:10px;'>View Raw JSON</summary>"
                                response_text += f"<h4>Request Payload:</h4>"
                                response_text += f"<pre>{json.dumps(current_request_json, indent=2)}</pre>"
                                response_text += f"<h4>Response:</h4>"
                                response_text += f"<pre style='color: #00FF66;'>{json.dumps(response_json, indent=2)}</pre>"
                                response_text += f"</details>"
                                response_text += f"</div>"
                                
                                # Add to responses list
                                responses.append({
                                    'payload': current_request_json,
                                    'result': response_json,
                                    'request_num': current_request_num
                                })
                                
                                # Reset for next pair
                                current_section = None
                                current_json = ""
                            except json.JSONDecodeError:
                                pass
                
                # The updated parser handles all the responses in the loop
                # No additional processing needed here
                
                # Display all responses in a styled container
                if responses:
                    response_placeholder.markdown(f"<div class='responses-wrapper'>{response_text}</div>", unsafe_allow_html=True)
                else:
                    response_placeholder.warning("No responses were captured. Check the logs for details.")
            else:
                st.error("Inference tests failed. Check the logs for errors.")

# Tab 2: Model Fine-tuning
with model_tab:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("Step 3: Fine-tune Model")
        st.write("Configure and start model fine-tuning using SageMaker.")
        
        # Show current configuration
        st.subheader("Current Configuration")
        st.json({
            "use_case": current_config.get('use_case', 'Not set'),
            "model_name": current_config.get('model_name', 'Not set'),
            "fine_tuning_model": current_config.get('fine_tuning_model', 'None'),
            "training_data": current_config.get('training_data', 'None'),
            "instance_type": current_config.get('instance_type', 't3.medium')
        })
        
        # Input fields for configuration
        st.subheader("Fine-tuning Configuration")
        
        # Model selection
        model_options = [
            "meta-llama/Llama-2-7b", 
            "meta-llama/Llama-2-13b",
            "meta-llama/Llama-2-70b", 
            "mistralai/Mistral-7B-Instruct-v0.1",
            "mistralai/Mistral-7B-Instruct-v0.2"
        ]
        
        fine_tuning_model = st.selectbox(
            "Base Model", 
            options=model_options,
            index=0 if current_config.get('fine_tuning_model') not in model_options else model_options.index(current_config.get('fine_tuning_model')),
            key="model_finetune_selector"
        )
        
        # Instance selection
        instance_options = [
            "ml.g5.2xlarge", 
            "ml.g5.4xlarge",
            "ml.g5.8xlarge",
            "ml.g5.16xlarge", 
            "ml.p4d.24xlarge"
        ]
        
        instance_type = st.selectbox(
            "Training Instance Type", 
            options=instance_options,
            index=0 if current_config.get('instance_type') not in instance_options else instance_options.index(current_config.get('instance_type')),
            key="instance_type_selector"
        )
        
        # Advanced training parameters
        with st.expander("Advanced Training Parameters"):
            epochs = st.number_input("Epochs", min_value=1, max_value=10, value=3)
            learning_rate = st.number_input("Learning Rate", min_value=0.00001, max_value=0.01, value=0.0001, format="%.5f")
            batch_size = st.number_input("Batch Size", min_value=1, max_value=64, value=8)
        
        # Submit button
        if st.button("Save Fine-tuning Configuration"):
            config = load_config()
            config['fine_tuning_model'] = fine_tuning_model
            config['instance_type'] = instance_type
            config['epochs'] = int(epochs)
            config['learning_rate'] = float(learning_rate)
            config['batch_size'] = int(batch_size)
            save_config(config)
            st.success("Fine-tuning configuration saved!")
            current_config = config  # Update current config
        
        # Start training job
        st.subheader("Start Training Job")
        if st.button("Launch Fine-tuning Job", type="primary"):
            if not current_config.get('use_case'):
                st.error("Please select a use case first!")
            elif not current_config.get('training_data'):
                st.error("Training data not available. Generate synthetic data first!")
            else:
                try:
                    # Create shortened timestamp for job name (MMDD_HHMM format)
                    timestamp = datetime.datetime.now().strftime("%m%d_%H%M")
                    
                    # Create a valid job name (alphanumeric and hyphens only)
                    use_case = current_config.get('use_case', '').replace('_', '-')
                    job_name = f"{use_case}-{timestamp}".lower()
                    
                    # Mock job submission for demo
                    st.success(f"✅ Training job '{job_name}' submitted successfully!")
                    st.info("Check the AWS SageMaker console for job status and details.")
                    
                    # Update config with job name
                    config = load_config()
                    config['training_job'] = job_name
                    save_config(config)
                    
                    # Log the job submission
                    logging.info(f"Submitted training job: {job_name}")
                except Exception as e:
                    st.error(f"Failed to submit training job: {str(e)}")
        
        # Show job status if available
        if current_config.get('training_job'):
            st.subheader("Recent Training Jobs")
            st.info(f"Most recent job: {current_config.get('training_job')}")
            
            # Mock job status
            status_options = ["InProgress", "Completed", "Failed"]
            mock_status = status_options[1]  # Assume completed for demo
            
            # Show status with appropriate color
            if mock_status == "Completed":
                st.success(f"Status: {mock_status}")
            elif mock_status == "InProgress":
                st.info(f"Status: {mock_status}")
            else:
                st.error(f"Status: {mock_status}")
    
    # Right column for help/instructions
    with col2:
        st.markdown("### 📋 Instructions")
        st.info("""
        **Model Fine-tuning Steps:**
        
        1. Select a base model
        2. Choose compute instance
        3. Configure training parameters
        4. Launch fine-tuning job
        
        Fine-tuning takes 1-4 hours depending on
        data size and instance type.
        """)
        
        # Show estimated costs
        st.markdown("### 💰 Estimated Costs")
        
        # Map instance types to hourly rates
        instance_costs = {
            "ml.g5.2xlarge": "$1.52/hour",
            "ml.g5.4xlarge": "$3.04/hour",
            "ml.g5.8xlarge": "$6.08/hour",
            "ml.g5.16xlarge": "$12.16/hour",
            "ml.p4d.24xlarge": "$32.77/hour"
        }
        
        # Display cost for selected instance
        if current_config.get('instance_type') in instance_costs:
            st.metric("Instance Cost", instance_costs.get(current_config.get('instance_type')))
        
        # Show warning for larger instances
        if current_config.get('instance_type') in ["ml.g5.16xlarge", "ml.p4d.24xlarge"]:
            st.warning("⚠️ High-cost instance selected")

# Tab 4: Model Registry
with registry_tab:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("SageMaker Model Registry")
        st.write("Browse and select models registered in SageMaker.")
        
        # Function to get list of models from SageMaker
        def fetch_sagemaker_models():
            try:
                # Extract region from config if available
                aws_region = current_config.get('aws_region', 'us-west-2')
                
                # Create a SageMaker client
                sm_client = boto3.client('sagemaker', region_name=aws_region)
                
                # Fetch models from SageMaker
                models = []
                paginator = sm_client.get_paginator('list_models')
                
                # Pagination to handle large numbers of models
                for page in paginator.paginate():
                    for model in page['Models']:
                        models.append(model)
                
                return models
            except Exception as e:
                st.error(f"Error fetching models: {e}")
                return []
        
        # Fetch models with a loading spinner
        with st.spinner("Fetching available models from SageMaker..."):
            models = fetch_sagemaker_models()
        
        if not models:
            st.info("No models found in SageMaker Model Registry or unable to access the registry. Try creating a model first.")
        else:
            # Display models in a selection box
            model_names = [model['ModelName'] for model in models]
            selected_model = st.selectbox("Select a model to deploy", model_names, key="registry_tab_model_selector")
            
            # Display model details
            if selected_model:
                selected_model_info = next((m for m in models if m['ModelName'] == selected_model), None)
                if selected_model_info:
                    st.subheader("Model Details")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Creation Time:** {selected_model_info.get('CreationTime').strftime('%Y-%m-%d %H:%M')}")
                        st.write(f"**ARN:** {selected_model_info.get('ModelArn')}")
                    
                    # Button to select this model for deployment
                    if st.button("📋 Select for Deployment", key="select_model_deployment_btn"):
                        # Update config with the selected model
                        config = load_config()
                        config['model_name'] = selected_model
                        save_config(config)
                        st.success(f"Selected model '{selected_model}' for deployment!")
                        
                    # Try to retrieve more model details
                    with st.expander("More details"):
                        try:
                            aws_region = current_config.get('aws_region', 'us-west-2')
                            sm_client = boto3.client('sagemaker', region_name=aws_region)
                            model_desc = sm_client.describe_model(ModelName=selected_model)
                            st.json(model_desc, default=str)
                        except Exception as e:
                            st.write(f"Could not fetch detailed model information: {e}")

# Tab 5: Usecase Creation
with usecase_tab:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("🧩 Generate New Usecase Configuration")
        st.write("Create custom YAML configuration files for synthetic data generation using Perplexity API.")
        
        # Import the EnhancedUseCaseGenerator
        try:
            import perplexity_generates_data_config
            EnhancedUseCaseGenerator = perplexity_generates_data_config.EnhancedUseCaseGenerator
            st.success("✅ Successfully loaded EnhancedUseCaseGenerator.")
        except Exception as e:
            st.error(f"❌ Error loading EnhancedUseCaseGenerator: {str(e)}")
            EnhancedUseCaseGenerator = None
        
        # Domain configuration
        st.subheader("Domain Configuration")
        domain_name = st.text_input("Domain Name", value="enterprise_sales", 
                                 help="Name of the domain to generate configuration for (e.g., healthcare_patient_care, retail_recommendation)")
        
        # Advanced options in an expander
        with st.expander("Advanced Options"):
            instructions_file = st.text_input(
                "Instructions File", 
                value="instructions_for_usecase_data_creation.md",
                help="Path to markdown file with detailed instructions")
            
            output_dir = st.text_input(
                "Output Directory", 
                value="data_generation/usecase_config_files",
                help="Directory where the generated YAML file will be saved")
            
            api_key = st.text_input(
                "Perplexity API Key (Optional)", 
                value="",
                help="Custom API key to use instead of the default one",
                type="password")
            
            search_domains = st.multiselect(
                "Search Focus Domains",
                options=["salesforce.com", "hubspot.com", "pipedrive.com", "crm.org", 
                         "healthcare.gov", "hl7.org", "epic.com", "cerner.com",
                         "retail.org", "nrf.com", "shopify.com", "amazon.com"],
                default=["salesforce.com", "hubspot.com", "pipedrive.com", "crm.org"],
                help="Domains to focus search results on for research")
        
        # Show existing examples for reference
        with st.expander("Available Examples for Reference"):
            usecase_files = get_available_usecases()
            if usecase_files:
                # Create a list of options with domain name and description
                options = [f"{u['name']} - {u['description'][:50]}..." for u in usecase_files]
                # Display selectbox with descriptive options
                selected_index = st.selectbox("Select existing config to view", 
                                              options=range(len(options)),
                                              format_func=lambda i: options[i],
                                              key="usecase_example_selector")
                
                if selected_index is not None:
                    selected_path = usecase_files[selected_index]['path']
                    try:
                        with open(selected_path, 'r') as f:
                            example_content = f.read()
                        st.code(example_content, language="yaml")
                    except Exception as e:
                        st.error(f"Could not read example: {str(e)}")
            else:
                st.info("No example config files found.")
                
        # Generate button
        if st.button("🔮 Generate New Configuration", type="primary"):
            if EnhancedUseCaseGenerator is not None:
                try:
                    # Display spinner during generation
                    with st.spinner(f"🔍 Generating {domain_name} configuration using Perplexity API..."):
                                        # We'll execute the script with command line arguments
                        import subprocess
                        import sys
                        
                        # Create progress indicators
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        output_container = st.container()
                        
                        # Update initial status
                        status_text.text("Starting generation process...")
                        progress_bar.progress(10)
                        
                        # Prepare the command to run the script
                        cmd = [sys.executable, "perplexity_generates_data_config.py", 
                               "--domain", domain_name, 
                               "--output-dir", output_dir, 
                               "--instructions", instructions_file]
                        
                        # Set environment variables including API key if provided and force UTF-8 encoding
                        env = os.environ.copy()
                        env["PYTHONIOENCODING"] = "utf-8"
                        if api_key:
                            env["PERPLEXITY_API_KEY"] = api_key
                            
                        # Update status
                        status_text.text("Executing Perplexity API command...")
                        progress_bar.progress(30)
                        
                        # Create a container for output
                        with output_container:
                            st.subheader("Generation Process Log")
                            output_placeholder = st.empty()
                            output_text = ""
                        
                        # Execute the process
                        try:
                            # Start the process
                            process = subprocess.Popen(
                                cmd,
                                env=env,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=False,
                                bufsize=1
                            )
                            
                            # Update status
                            status_text.text("Generating configuration with Perplexity API...")
                            progress_bar.progress(40)
                            
                            # Read output lines as they're produced
                            output_text = ""
                            while True:
                                line = process.stdout.readline()
                                if not line and process.poll() is not None:
                                    break
                                    
                                if line:
                                    try:
                                        decoded_line = line.decode('utf-8', errors='replace')
                                        output_text += decoded_line
                                        output_placeholder.code(output_text)
                                        
                                        # Check if we've reached certain milestones to update progress
                                        if "Calling Perplexity API" in decoded_line:
                                            progress_bar.progress(50)
                                        elif "Validating" in decoded_line:
                                            progress_bar.progress(70)
                                        elif "Saved to:" in decoded_line:
                                            progress_bar.progress(90)
                                    except Exception as decode_err:
                                        st.warning(f"Error decoding output: {str(decode_err)}")
                            
                            # Get any stderr output
                            stderr_output = process.stderr.read()
                            if stderr_output:
                                try:
                                    decoded_stderr = stderr_output.decode('utf-8', errors='replace')
                                    output_text += "\nERROR:\n" + decoded_stderr
                                    output_placeholder.code(output_text, language="bash")
                                    raise Exception(decoded_stderr)
                                except Exception as stderr_err:
                                    st.error(f"Error reading stderr: {str(stderr_err)}")
                                    raise Exception("Error reading process output")
                            
                            # Wait for process to complete
                            return_code = process.wait()
                            if return_code != 0:
                                raise Exception(f"Process failed with return code {return_code}")
                            
                            # Update status
                            status_text.text("Config generated successfully!")
                            progress_bar.progress(100)
                            
                            # Extract file path from output
                            file_path = None
                            for line in output_text.split('\n'):
                                if "Saved to:" in line:
                                    file_path = line.split("Saved to:")[-1].strip()
                                    break
                            
                            if not file_path or not os.path.exists(file_path):
                                # Find the most recently created YAML file in the output directory
                                yaml_files = []
                                for file in Path(output_dir).glob(f"*{domain_name.lower().replace(' ', '_')}*.yaml"):
                                    yaml_files.append((file, file.stat().st_mtime))
                                
                                if not yaml_files:
                                    yaml_files = []
                                    for file in Path(output_dir).glob("*.yaml"):
                                        yaml_files.append((file, file.stat().st_mtime))
                                
                                if not yaml_files:
                                    raise Exception(f"No YAML files found in {output_dir}")
                                
                                # Sort by modification time (newest first)
                                yaml_files.sort(key=lambda x: x[1], reverse=True)
                                file_path = str(yaml_files[0][0])
                            
                            # Load the YAML content
                            with open(file_path, 'r', encoding='utf-8') as f:
                                yaml_content = f.read()
                            
                            # Create the result object
                            result = {
                                "file_path": file_path,
                                "yaml_content": yaml_content,
                                "domain": domain_name,
                                # Extract citations if present in output
                                "citations": []
                            }
                            
                        except Exception as e:
                            progress_bar.empty()
                            status_text.error(f"Error: {str(e)}")
                            st.error(f"Error executing process: {str(e)}")
                            raise e
                        
                        if result and result.get('file_path'):
                            st.success(f"✅ Successfully generated {domain_name} configuration!")
                            st.write(f"📁 File saved to: {result['file_path']}")
                            
                            # Display YAML content
                            st.subheader("Generated YAML Configuration")
                            st.code(result['yaml_content'], language="yaml")
                            
                            # Display citations if available
                            if result.get('citations'):
                                with st.expander("Research Citations"):
                                    st.write("The following sources were used to generate this configuration:")
                                    
                                    for citation in result['citations']:
                                        st.write(f"🔍 **{citation.get('title', 'Source')}**")
                                        st.write(f"URL: {citation.get('url', 'N/A')}")
                                        st.write("---")
                                        
                            # Button to use this config for data generation
                            if st.button("Use This Configuration", type="primary"):
                                if update_config_for_usecase(result['file_path']):
                                    # Set flag to refresh use case list in sidebar
                                    if 'select_new_config' not in st.session_state:
                                        st.session_state.select_new_config = True
                                    else:
                                        st.session_state.select_new_config = True
                                    st.success(f"Config updated to use {domain_name}!")
                                    st.info("💡 The use case list in the sidebar has been refreshed. Your new config is now available for selection.")
                            
                except Exception as e:
                    st.error(f"❌ Error generating configuration: {str(e)}")
                    st.error("Check the console for more details.")
            else:
                st.error("UseCaseGenerator module could not be loaded. Please check the console for errors.")
                
    # Right column for help/instructions
    with col2:
        st.markdown("### 📝 Instructions")
        st.info("""
        **How to use:**
        
        1. Enter a domain name (e.g., healthcare_records, financial_services)
        2. Adjust advanced options if needed
        3. Click 'Generate New Configuration'
        4. Review and use the generated YAML
        
        **Pro Tips:**
        - Be specific with domain names
        - Check existing examples for reference
        - Custom API keys can be used for higher rate limits
        """)
        
        # Display stats if available
        st.markdown("### 📊 Statistics")
        usecase_files = get_available_usecases()
        st.metric("Available Configs", len(usecase_files))
        
        # Get unique domains
        unique_domains = set()
        for file in usecase_files:
            # Extract domain name from filename (before first underscore)
            if '_' in file:
                domain = file.split('_')[0]
                unique_domains.add(domain)
        
        st.metric("Unique Domains", len(unique_domains))
    
    # Fetch models with a loading spinner
    with st.spinner("Fetching available models from SageMaker..."):
        models = fetch_sagemaker_models()
    
    if not models:
        st.info("No models found in SageMaker Model Registry or unable to access the registry. Try creating a model first.")
    else:
        # Display models in a selection box
        model_names = [model['ModelName'] for model in models]
        selected_model = st.selectbox(
            "Select a model to deploy",
            options=model_names
        )
        
        # Display model details if a model is selected
        if selected_model:
            selected_model_info = next((m for m in models if m['ModelName'] == selected_model), None)
            if selected_model_info:
                st.subheader("Model Details")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Creation Time:** {selected_model_info.get('CreationTime').strftime('%Y-%m-%d %H:%M')}")
                    st.write(f"**ARN:** {selected_model_info.get('ModelArn')}")
                
                # Button to select this model for deployment
                if st.button("📋 Select for Deployment", key="select_registry_model_btn"):
                    # Update config with the selected model
                    config = load_config()
                    config['model_name'] = selected_model
                    save_config(config)
                    st.success(f"Selected model '{selected_model}' for deployment!")
                    
                # Try to retrieve more model details
                with st.expander("More details"):
                    try:
                        sm_client = boto3.client('sagemaker', region_name=aws_region)
                        model_desc = sm_client.describe_model(ModelName=selected_model)
                        st.json(json.dumps(model_desc, default=str, indent=2))
                    except Exception as e:
                        st.write(f"Could not fetch detailed model information: {e}")

# Add logs section to sidebar
with st.sidebar.expander("📋 Workflow Logs", expanded=False):
    st.write("View logs from previous workflow runs.")

    # Get log files
    log_files = [f for f in os.listdir() if f.endswith(".log") and os.path.isfile(f)]
    
    if log_files:
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        selected_log = st.selectbox("Select a log file", log_files)
        
        # Show log content
        if selected_log:
            try:
                with open(selected_log, 'r') as f:
                    log_content = f.read()
                
                st.code(log_content[:2000], language="plain")
                if len(log_content) > 2000:
                    st.info("Log truncated. View full log in filesystem.")
            except Exception as e:
                st.error(f"Error reading log file: {e}")
    else:
        st.info("No log files found.")

# Footer
st.sidebar.divider()
st.sidebar.caption("LLM Workflow Automation Dashboard")

