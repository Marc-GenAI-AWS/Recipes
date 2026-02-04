"""
Streamlit User Interface for Automated LLM Finetuning Pipeline

This is the main entry point for the web-based interface that provides:
- Dashboard with overview of all use cases and recent activity
- Use case management (list, create, edit, delete)
- Pipeline execution with real-time progress monitoring
- Results visualization with response comparisons and judgments
- Training data viewer with pagination
- Performance charts showing win rate progression across iterations

The UI uses Streamlit's multi-page navigation system with session state
management to maintain context across page refreshes.
"""

import streamlit as st
from pathlib import Path
import logging
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import Optional, List, Dict, Any
import threading
import time

from src.configuration_manager import ConfigurationManager
from src.progress_tracker import ProgressTracker
from src.config_models import UseCase, Prompts
from src.logging_config import get_logger

# Configure logging
logger = get_logger("streamlit_app")


def init_session_state():
    """
    Initialize Streamlit session state with required components.
    
    This function ensures that the ConfigurationManager and ProgressTracker
    are initialized once per session and available to all pages. It also
    initializes other session state variables for UI state management.
    """
    # Initialize configuration manager
    if 'config_manager' not in st.session_state:
        try:
            st.session_state['config_manager'] = ConfigurationManager()
            logger.info("ConfigurationManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ConfigurationManager: {e}")
            st.error(f"Failed to initialize configuration manager: {e}")
            st.session_state['config_manager'] = None
    
    # Initialize progress tracker
    if 'progress_tracker' not in st.session_state:
        try:
            st.session_state['progress_tracker'] = ProgressTracker()
            logger.info("ProgressTracker initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ProgressTracker: {e}")
            st.error(f"Failed to initialize progress tracker: {e}")
            st.session_state['progress_tracker'] = None
    
    # Initialize UI state variables
    if 'selected_use_case' not in st.session_state:
        st.session_state['selected_use_case'] = None
    
    if 'pipeline_running' not in st.session_state:
        st.session_state['pipeline_running'] = False
    
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = "Dashboard"


def render_dashboard():
    """
    Display overview dashboard with summary of all use cases and recent activity.
    
    Section 11.2: Enhanced dashboard with:
    - Summary statistics for all use cases
    - Recent activity (last 5 pipeline runs)
    - Quick action buttons that work
    - Performance trends
    """
    st.title("🏠 Dashboard")
    st.markdown("---")
    
    # Check if components are initialized
    if st.session_state.get('config_manager') is None:
        st.error("Configuration manager not initialized. Please check logs.")
        return
    
    # Get use cases
    try:
        use_cases = st.session_state['config_manager'].list_use_cases()
        
        # Calculate summary statistics
        total_iterations = 0
        use_cases_with_history = 0
        recent_activity = []
        
        if st.session_state.get('progress_tracker'):
            for uc_name in use_cases:
                try:
                    history = st.session_state['progress_tracker'].get_performance_history(uc_name)
                    if history:
                        use_cases_with_history += 1
                        total_iterations += len(history)
                        # Add to recent activity
                        for result in history:
                            recent_activity.append({
                                'use_case': uc_name,
                                'iteration': result.iteration,
                                'win_rate': result.win_rate,
                                'time': result.evaluation_time
                            })
                except Exception as e:
                    # No results for this use case yet - skip it
                    logger.debug(f"No results for use case {uc_name}: {e}")
                    continue
        
        # Sort recent activity by time (most recent first)
        recent_activity.sort(key=lambda x: x['time'], reverse=True)
        recent_activity = recent_activity[:5]  # Keep only last 5
        
        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Use Cases", len(use_cases))
        
        with col2:
            st.metric("Use Cases with Results", use_cases_with_history)
        
        with col3:
            st.metric("Total Iterations", total_iterations)
        
        with col4:
            status = "🟢 Ready" if not st.session_state.get('pipeline_running') else "🟡 Running"
            st.metric("Pipeline Status", status)
        
        st.markdown("---")
        
        # Recent Activity Section
        st.subheader("📊 Recent Activity")
        if recent_activity:
            for activity in recent_activity:
                col1, col2, col3, col4 = st.columns([3, 1, 2, 2])
                with col1:
                    st.write(f"**{activity['use_case']}**")
                with col2:
                    st.write(f"Iter {activity['iteration']}")
                with col3:
                    # Color code win rate
                    win_rate = activity['win_rate']
                    color = "🟢" if win_rate >= 0.6 else "🟡" if win_rate >= 0.4 else "🔴"
                    st.write(f"{color} {win_rate:.1%}")
                with col4:
                    st.write(activity['time'].strftime("%Y-%m-%d %H:%M"))
        else:
            st.info("No pipeline runs yet. Start by running a pipeline!")
        
        st.markdown("---")
        
        # Performance Trends Section
        st.subheader("📈 Performance Trends")
        if use_cases_with_history > 0:
            # Create a chart showing win rates across all use cases
            trend_data = []
            for uc_name in use_cases:
                try:
                    history = st.session_state['progress_tracker'].get_performance_history(uc_name)
                    if history:
                        for result in history:
                            trend_data.append({
                                'Use Case': uc_name,
                                'Iteration': result.iteration,
                                'Win Rate': result.win_rate
                            })
                except Exception as e:
                    # No results for this use case yet - skip it
                    logger.debug(f"No results for use case {uc_name}: {e}")
                    continue
            
            if trend_data:
                df = pd.DataFrame(trend_data)
                fig = px.line(df, x='Iteration', y='Win Rate', color='Use Case',
                             title='Win Rate Progression Across Use Cases',
                             markers=True)
                fig.update_layout(yaxis_tickformat='.0%')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No performance data available yet.")
        
        st.markdown("---")
        
        # Use Cases Overview
        st.subheader("📋 Use Cases Overview")
        
        if not use_cases:
            st.info("No use cases found. Create your first use case to get started!")
            if st.button("➕ Create Use Case"):
                st.session_state['current_page'] = "Create Use Case"
                st.rerun()
        else:
            for uc_name in use_cases:
                with st.expander(f"📁 {uc_name}"):
                    try:
                        use_case = st.session_state['config_manager'].load_use_case(uc_name)
                        st.write(f"**Description:** {use_case.description[:200]}...")
                        st.write(f"**Test Questions:** {len(use_case.test_questions)}")
                        st.write(f"**Version:** {use_case.version}")
                        st.write(f"**Created:** {use_case.created_at.strftime('%Y-%m-%d %H:%M')}")
                        
                        # Show performance if available
                        if st.session_state.get('progress_tracker'):
                            try:
                                history = st.session_state['progress_tracker'].get_performance_history(uc_name)
                                if history:
                                    latest = history[-1]
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.metric("Latest Win Rate", f"{latest.win_rate:.1%}")
                                    with col2:
                                        st.metric("Total Iterations", len(history))
                            except Exception as e:
                                # No results for this use case yet
                                logger.debug(f"No results for use case {uc_name}: {e}")
                    except Exception as e:
                        st.error(f"Error loading use case: {e}")
        
        st.markdown("---")
        
        # Quick actions
        st.subheader("⚡ Quick Actions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("➕ Create New Use Case", use_container_width=True):
                st.session_state['current_page'] = "Create Use Case"
                st.rerun()
        
        with col2:
            if st.button("▶️ Run Pipeline", use_container_width=True):
                st.session_state['current_page'] = "Run Pipeline"
                st.rerun()
        
        with col3:
            if st.button("📊 View Results", use_container_width=True):
                st.session_state['current_page'] = "View Results"
                st.rerun()
    
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        st.error(f"Error loading dashboard: {e}")


def render_use_cases():
    """
    Display list of all use cases with management options.
    
    Section 11.3: Full use case management with:
    - Use case list view with filtering
    - Use case detail view
    - Edit and delete functionality
    - Performance history for each use case
    """
    st.title("📋 Use Cases")
    st.markdown("---")
    
    if st.session_state.get('config_manager') is None:
        st.error("Configuration manager not initialized.")
        return
    
    try:
        use_cases = st.session_state['config_manager'].list_use_cases()
        
        # Search/Filter
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input("🔍 Search use cases", placeholder="Enter use case name...")
        with col2:
            show_only_with_results = st.checkbox("Only with results", value=False)
        
        # Filter use cases
        filtered_use_cases = use_cases
        if search_term:
            filtered_use_cases = [uc for uc in filtered_use_cases if search_term.lower() in uc.lower()]
        
        if show_only_with_results and st.session_state.get('progress_tracker'):
            filtered_use_cases = [
                uc for uc in filtered_use_cases
                if st.session_state['progress_tracker'].get_performance_history(uc)
            ]
        
        st.write(f"**Found {len(filtered_use_cases)} use case(s)**")
        st.markdown("---")
        
        if not filtered_use_cases:
            st.info("No use cases found matching your criteria.")
            if st.button("➕ Create New Use Case"):
                st.session_state['current_page'] = "Create Use Case"
                st.rerun()
        else:
            # Display use cases
            for uc_name in filtered_use_cases:
                with st.expander(f"📁 {uc_name}", expanded=False):
                    try:
                        use_case = st.session_state['config_manager'].load_use_case(uc_name)
                        
                        # Use case details
                        st.subheader("Details")
                        st.write(f"**Name:** {use_case.name}")
                        st.write(f"**Description:**")
                        st.write(use_case.description)
                        st.write(f"**Version:** {use_case.version}")
                        st.write(f"**Created:** {use_case.created_at.strftime('%Y-%m-%d %H:%M')}")
                        
                        # Test questions
                        st.subheader("Test Questions")
                        for i, question in enumerate(use_case.test_questions, 1):
                            st.write(f"{i}. {question}")
                        
                        # Judge criteria
                        with st.expander("Judge Criteria"):
                            st.write(use_case.judge_criteria)
                        
                        # Prompts
                        with st.expander("Data Generation Prompt"):
                            st.code(use_case.data_generation_prompt, language="text")
                        
                        with st.expander("Judge Prompt"):
                            st.code(use_case.judge_prompt, language="text")
                        
                        # Performance history
                        if st.session_state.get('progress_tracker'):
                            history = st.session_state['progress_tracker'].get_performance_history(uc_name)
                            if history:
                                st.subheader("Performance History")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total Iterations", len(history))
                                with col2:
                                    st.metric("Latest Win Rate", f"{history[-1].win_rate:.1%}")
                                with col3:
                                    improvement = history[-1].win_rate - history[0].win_rate
                                    st.metric("Improvement", f"{improvement:+.1%}")
                                
                                # Mini chart
                                win_rates = [r.win_rate for r in history]
                                iterations = [r.iteration for r in history]
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=iterations, y=win_rates,
                                    mode='lines+markers',
                                    name='Win Rate'
                                ))
                                fig.update_layout(
                                    title="Win Rate Progression",
                                    xaxis_title="Iteration",
                                    yaxis_title="Win Rate",
                                    yaxis_tickformat='.0%',
                                    height=300
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        
                        # Action buttons
                        st.markdown("---")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if st.button(f"✏️ Edit", key=f"edit_{uc_name}"):
                                st.session_state['edit_use_case'] = uc_name
                                st.session_state['current_page'] = "Create Use Case"
                                st.rerun()
                        
                        with col2:
                            if st.button(f"▶️ Run Pipeline", key=f"run_{uc_name}"):
                                st.session_state['selected_use_case'] = uc_name
                                st.session_state['current_page'] = "Run Pipeline"
                                st.rerun()
                        
                        with col3:
                            if st.button(f"🗑️ Delete", key=f"delete_{uc_name}"):
                                st.session_state[f'confirm_delete_{uc_name}'] = True
                        
                        # Confirm delete
                        if st.session_state.get(f'confirm_delete_{uc_name}'):
                            st.warning(f"⚠️ Are you sure you want to delete '{uc_name}'? This cannot be undone.")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("Yes, delete", key=f"confirm_yes_{uc_name}"):
                                    try:
                                        # Delete use case file
                                        use_case_path = Path(f"config/use_cases/{uc_name}.yaml")
                                        if use_case_path.exists():
                                            use_case_path.unlink()
                                        st.success(f"Deleted use case: {uc_name}")
                                        st.session_state[f'confirm_delete_{uc_name}'] = False
                                        time.sleep(1)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error deleting use case: {e}")
                            with col2:
                                if st.button("Cancel", key=f"confirm_no_{uc_name}"):
                                    st.session_state[f'confirm_delete_{uc_name}'] = False
                                    st.rerun()
                    
                    except Exception as e:
                        st.error(f"Error loading use case {uc_name}: {e}")
                        logger.error(f"Error loading use case {uc_name}: {e}")
    
    except Exception as e:
        logger.error(f"Error rendering use cases page: {e}")
        st.error(f"Error loading use cases: {e}")


def render_create_use_case():
    """
    Display form for creating or editing use cases.
    
    Section 11.4: Complete form with:
    - Use case form with all required fields
    - Form validation
    - Question management (add/edit/remove)
    - Prompt editors with syntax highlighting
    """
    # Check if we're editing an existing use case
    edit_mode = 'edit_use_case' in st.session_state and st.session_state['edit_use_case']
    
    if edit_mode:
        st.title("✏️ Edit Use Case")
        use_case_name = st.session_state['edit_use_case']
        try:
            existing_use_case = st.session_state['config_manager'].load_use_case(use_case_name)
        except Exception as e:
            st.error(f"Error loading use case: {e}")
            st.session_state['edit_use_case'] = None
            return
    else:
        st.title("➕ Create Use Case")
        existing_use_case = None
    
    st.markdown("---")
    
    if st.session_state.get('config_manager') is None:
        st.error("Configuration manager not initialized.")
        return
    
    # AI-Assisted Complete Use Case Generation (OUTSIDE the form)
    st.subheader("🤖 AI-Powered Use Case Generation")
    st.write("Let Claude Sonnet 4 automatically generate everything you need - just provide a brief description!")
    
    with st.expander("✨ Auto-Generate Complete Use Case", expanded=True):
        st.write("Provide a brief description of your use case, and AI will generate:")
        st.write("• 50 diverse test questions")
        st.write("• Judge evaluation criteria")
        st.write("• Judge prompt for comparing responses")
        st.write("• Data generation prompt for training data")
        
        ai_description = st.text_area(
            "Use Case Description *",
            height=150,
            placeholder="Example: Build a customer support assistant that helps users with account issues, billing questions, and product information. The model should be empathetic, clear, and provide actionable solutions.",
            help="Describe what the model should do, who it's for, and what kind of interactions it should handle",
            key="ai_description"
        )
        
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🚀 Generate Complete Use Case", use_container_width=True, key="generate_all_btn", type="primary"):
                if not ai_description or not ai_description.strip():
                    st.error("Please provide a use case description")
                else:
                    # Generate everything using Claude Sonnet 4
                    with st.spinner("🤖 Generating complete use case with Claude Sonnet 4... This may take 30-60 seconds."):
                        try:
                            # Get Bedrock client
                            pipeline_config = st.session_state['config_manager'].load_pipeline_config()
                            aws_config = {
                                'region': pipeline_config.aws_region,
                                'max_attempts': 3,
                                'initial_backoff_seconds': 2,
                                'max_backoff_seconds': 30
                            }
                            
                            from src.aws_client_manager import AWSClientManager
                            aws_client_manager = AWSClientManager(aws_config)
                            bedrock_client = aws_client_manager.get_bedrock_runtime_client()
                            
                            # Read example files for context
                            example_questions_path = Path("example_judge_prompt_engineer/event_files/questions/wealth_questions.txt")
                            example_judge_path = Path("example_judge_prompt_engineer/event_files/judge_prompts/wealth-judge.txt")
                            
                            example_questions = ""
                            example_judge = ""
                            
                            if example_questions_path.exists():
                                with open(example_questions_path, 'r', encoding='utf-8') as f:
                                    example_questions = f.read()[:2000]  # First 2000 chars as example
                            
                            if example_judge_path.exists():
                                with open(example_judge_path, 'r', encoding='utf-8') as f:
                                    example_judge = f.read()
                            
                            # Generate everything in one comprehensive prompt
                            generation_prompt = f"""You are an expert at creating comprehensive LLM evaluation use cases. Based on the use case description below, generate ALL the following components:

USE CASE DESCRIPTION:
{ai_description.strip()}

EXAMPLE FORMAT FOR TEST QUESTIONS (from a wealth management use case):
{example_questions[:1000]}

EXAMPLE FORMAT FOR JUDGE PROMPT (from a wealth management use case):
{example_judge}

YOUR TASK:
Generate a complete use case with the following sections. Use the examples above as inspiration for format and quality, but adapt everything to match the specific use case description provided.

Return your response in the following EXACT format with clear section markers:

===TEST_QUESTIONS_START===
[Generate exactly 50 diverse, realistic test questions that cover different scenarios, edge cases, and capabilities for this use case. Each question should be on its own line. Make them specific, actionable, and representative of real user interactions.]
===TEST_QUESTIONS_END===

===JUDGE_CRITERIA_START===
[Write 3-5 clear evaluation criteria that explain what makes a good response for this use case. Focus on the most important qualities like accuracy, empathy, actionability, etc.]
===JUDGE_CRITERIA_END===

===JUDGE_PROMPT_START===
[Create a comprehensive judge prompt that will be used to compare two model responses. Include:
- Clear role definition for the judge
- Weighted evaluation criteria (with percentages)
- Scoring scale (0-10)
- Decision rules
- JSON output format
Use the example judge prompt format but adapt it completely to this specific use case.]
===JUDGE_PROMPT_END===

===DATA_GEN_PROMPT_START===
[Create a prompt that will be used to generate synthetic training data. It should instruct Claude to generate realistic examples in JSON format with "instruction", "context", and "response" fields that match this use case.]
===DATA_GEN_PROMPT_END===

Generate all sections now, ensuring they are cohesive and specifically tailored to the use case description provided."""
                            
                            request_body = {
                                "anthropic_version": "bedrock-2023-05-31",
                                "max_tokens": 8000,
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": generation_prompt
                                    }
                                ],
                                "temperature": 0.7
                            }
                            
                            # Invoke Claude Sonnet 4
                            response = bedrock_client.invoke_model(
                                modelId=pipeline_config.bedrock_model_id,
                                body=json.dumps(request_body)
                            )
                            
                            # Parse response
                            response_body = json.loads(response['body'].read())
                            generated_text = response_body['content'][0]['text']
                            
                            # Extract sections
                            import re
                            
                            questions_match = re.search(r'===TEST_QUESTIONS_START===(.*?)===TEST_QUESTIONS_END===', generated_text, re.DOTALL)
                            criteria_match = re.search(r'===JUDGE_CRITERIA_START===(.*?)===JUDGE_CRITERIA_END===', generated_text, re.DOTALL)
                            judge_match = re.search(r'===JUDGE_PROMPT_START===(.*?)===JUDGE_PROMPT_END===', generated_text, re.DOTALL)
                            data_gen_match = re.search(r'===DATA_GEN_PROMPT_START===(.*?)===DATA_GEN_PROMPT_END===', generated_text, re.DOTALL)
                            
                            if questions_match and criteria_match and judge_match and data_gen_match:
                                # Store in session state
                                st.session_state['generated_questions'] = questions_match.group(1).strip()
                                st.session_state['generated_criteria'] = criteria_match.group(1).strip()
                                st.session_state['generated_judge_prompt'] = judge_match.group(1).strip()
                                st.session_state['generated_data_gen_prompt'] = data_gen_match.group(1).strip()
                                st.session_state['ai_gen_description'] = ai_description.strip()
                                
                                st.success(f"✅ Generated complete use case! Scroll down to review and edit before saving.")
                                logger.info(f"Successfully generated complete use case using Claude Sonnet 4")
                                st.rerun()
                            else:
                                st.error("Failed to parse generated content. Please try again.")
                                logger.error("Failed to extract sections from generated text")
                            
                        except Exception as e:
                            st.error(f"Failed to generate use case: {e}")
                            logger.error(f"Error generating complete use case with Claude Sonnet 4: {e}")
        
        with col2:
            st.info("💡 **Tip:** Be specific about your use case - mention the domain, target users, and key capabilities you want the model to have.")
    
    st.markdown("---")
    
    # Use case form
    with st.form("use_case_form"):
        st.subheader("Basic Information")
        
        # Name (read-only in edit mode)
        if edit_mode:
            name = st.text_input(
                "Use Case Name *",
                value=existing_use_case.name,
                disabled=True,
                help="Use case name cannot be changed after creation"
            )
        else:
            name = st.text_input(
                "Use Case Name *",
                placeholder="e.g., customer_support",
                help="Use lowercase with underscores. Must be unique."
            )
        
        # Description - pre-fill with AI description if available
        default_description = ""
        if 'ai_gen_description' in st.session_state and st.session_state['ai_gen_description']:
            default_description = st.session_state['ai_gen_description']
        elif existing_use_case:
            default_description = existing_use_case.description
        
        description = st.text_area(
            "Description *",
            value=default_description,
            height=150,
            placeholder="Describe the use case and desired model behavior...",
            help="Detailed description of what the model should do"
        )
        
        st.markdown("---")
        st.subheader("Test Questions")
        st.write("Enter test questions for evaluating model performance (one per line)")
        
        # Test questions - pre-fill with generated questions if available
        default_questions = ""
        if 'generated_questions' in st.session_state and st.session_state['generated_questions']:
            default_questions = st.session_state['generated_questions']
        elif existing_use_case:
            default_questions = "\n".join(existing_use_case.test_questions)
        
        questions_text = st.text_area(
            "Test Questions *",
            value=default_questions,
            height=200,
            placeholder="Question 1\nQuestion 2\nQuestion 3...",
            help="Each line will be treated as a separate question. You can edit the AI-generated questions or write your own."
        )
        
        st.markdown("---")
        st.subheader("Evaluation Criteria")
        
        # Judge criteria - pre-fill with generated criteria if available
        default_criteria = ""
        if 'generated_criteria' in st.session_state and st.session_state['generated_criteria']:
            default_criteria = st.session_state['generated_criteria']
        elif existing_use_case:
            default_criteria = existing_use_case.judge_criteria
        
        judge_criteria = st.text_area(
            "Judge Criteria *",
            value=default_criteria,
            height=150,
            placeholder="Describe how responses should be evaluated...",
            help="Criteria for the judge to evaluate responses"
        )
        
        st.markdown("---")
        st.subheader("Prompts")
        
        # Data generation prompt - pre-fill with generated prompt if available
        default_data_gen = ""
        if 'generated_data_gen_prompt' in st.session_state and st.session_state['generated_data_gen_prompt']:
            default_data_gen = st.session_state['generated_data_gen_prompt']
        elif existing_use_case:
            default_data_gen = existing_use_case.data_generation_prompt
        
        data_gen_prompt = st.text_area(
            "Data Generation Prompt *",
            value=default_data_gen,
            height=250,
            placeholder="Instructions for generating synthetic training data...",
            help="Prompt for Claude Sonnet 4 to generate training examples"
        )
        
        # Judge prompt - pre-fill with generated prompt if available
        default_judge = ""
        if 'generated_judge_prompt' in st.session_state and st.session_state['generated_judge_prompt']:
            default_judge = st.session_state['generated_judge_prompt']
        elif existing_use_case:
            default_judge = existing_use_case.judge_prompt
        
        judge_prompt = st.text_area(
            "Judge Prompt *",
            value=default_judge,
            height=250,
            placeholder="Instructions for judging response quality...",
            help="Prompt for Claude Sonnet 4 to compare responses"
        )
        
        st.markdown("---")
        
        # Submit buttons
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button(
                "💾 Save Use Case" if edit_mode else "➕ Create Use Case",
                use_container_width=True
            )
        with col2:
            cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)
        
        if cancelled:
            # Clear generated content from session state
            st.session_state['generated_questions'] = None
            st.session_state['generated_criteria'] = None
            st.session_state['generated_judge_prompt'] = None
            st.session_state['generated_data_gen_prompt'] = None
            st.session_state['ai_gen_description'] = None
            st.session_state['edit_use_case'] = None
            st.session_state['current_page'] = "Use Cases"
            st.rerun()
        
        if submitted:
            # Validate inputs
            errors = []
            
            if not name or not name.strip():
                errors.append("Use case name is required")
            elif not edit_mode:
                # Check if name already exists
                existing_names = st.session_state['config_manager'].list_use_cases()
                if name in existing_names:
                    errors.append(f"Use case '{name}' already exists")
            
            if not description or not description.strip():
                errors.append("Description is required")
            
            # Parse questions
            questions = [q.strip() for q in questions_text.split('\n') if q.strip()]
            if not questions:
                errors.append("At least one test question is required")
            
            if not judge_criteria or not judge_criteria.strip():
                errors.append("Judge criteria is required")
            
            if not data_gen_prompt or not data_gen_prompt.strip():
                errors.append("Data generation prompt is required")
            
            if not judge_prompt or not judge_prompt.strip():
                errors.append("Judge prompt is required")
            
            # Display errors or save
            if errors:
                st.error("Please fix the following errors:")
                for error in errors:
                    st.error(f"• {error}")
            else:
                try:
                    # Create UseCase object
                    if edit_mode:
                        # Increment version for edits
                        version = existing_use_case.version + 1
                        created_at = existing_use_case.created_at
                    else:
                        version = 1
                        created_at = datetime.now()
                    
                    use_case = UseCase(
                        name=name.strip(),
                        description=description.strip(),
                        test_questions=questions,
                        judge_criteria=judge_criteria.strip(),
                        data_generation_prompt=data_gen_prompt.strip(),
                        judge_prompt=judge_prompt.strip(),
                        version=version,
                        created_at=created_at
                    )
                    
                    # Save use case
                    st.session_state['config_manager'].save_use_case(use_case)
                    
                    # Clear generated content from session state after successful save
                    st.session_state['generated_questions'] = None
                    st.session_state['generated_criteria'] = None
                    st.session_state['generated_judge_prompt'] = None
                    st.session_state['generated_data_gen_prompt'] = None
                    st.session_state['ai_gen_description'] = None
                    
                    st.success(f"✅ Use case '{name}' {'updated' if edit_mode else 'created'} successfully!")
                    st.session_state['edit_use_case'] = None
                    time.sleep(1)
                    st.session_state['current_page'] = "Use Cases"
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Error saving use case: {e}")
                    logger.error(f"Error saving use case: {e}")
    
    # Show preview
    if not edit_mode:
        st.markdown("---")
        st.info("💡 **Tip:** You can use the example use cases in `config/use_cases/` as templates.")


def render_run_pipeline():
    """
    Display interface for starting and monitoring pipeline execution.
    
    Section 11.5: Pipeline execution with:
    - Pipeline execution interface
    - Real-time progress monitoring
    - Live logs and status updates
    - Pause/resume/cancel functionality (basic version)
    """
    st.title("▶️ Run Pipeline")
    st.markdown("---")
    
    if st.session_state.get('config_manager') is None:
        st.error("Configuration manager not initialized.")
        return
    
    try:
        use_cases = st.session_state['config_manager'].list_use_cases()
        
        if not use_cases:
            st.warning("No use cases available. Please create a use case first.")
            if st.button("➕ Create Use Case"):
                st.session_state['current_page'] = "Create Use Case"
                st.rerun()
            return
        
        # Use case selection
        st.subheader("Select Use Case")
        
        # Pre-select if coming from another page
        default_index = 0
        if st.session_state.get('selected_use_case') in use_cases:
            default_index = use_cases.index(st.session_state['selected_use_case'])
        
        selected_use_case = st.selectbox(
            "Use Case",
            use_cases,
            index=default_index,
            help="Select the use case to run the pipeline for"
        )
        
        st.session_state['selected_use_case'] = selected_use_case
        
        # Load use case details
        try:
            use_case = st.session_state['config_manager'].load_use_case(selected_use_case)
            
            with st.expander("📋 Use Case Details", expanded=False):
                st.write(f"**Description:** {use_case.description[:300]}...")
                st.write(f"**Test Questions:** {len(use_case.test_questions)}")
                st.write(f"**Version:** {use_case.version}")
        except Exception as e:
            st.error(f"Error loading use case: {e}")
            return
        
        st.markdown("---")
        
        # Pipeline configuration
        st.subheader("Pipeline Configuration")
        
        col1, col2 = st.columns(2)
        with col1:
            max_iterations = st.number_input(
                "Max Iterations",
                min_value=1,
                max_value=10,
                value=5,
                help="Maximum number of self-improvement iterations"
            )
        
        with col2:
            performance_threshold = st.slider(
                "Performance Threshold",
                min_value=0.0,
                max_value=1.0,
                value=0.6,
                step=0.05,
                format="%.2f",
                help="Minimum win rate to avoid self-improvement (0.0 to 1.0)"
            )
        
        cleanup_resources = st.checkbox(
            "Cleanup resources after completion",
            value=True,
            help="Delete SageMaker endpoints and training artifacts"
        )
        
        st.markdown("---")
        
        # Pipeline execution
        st.subheader("Pipeline Execution")
        
        # Check if pipeline is running
        if st.session_state.get('pipeline_running'):
            st.warning("⚠️ Pipeline is currently running...")
            
            # Progress display
            progress_placeholder = st.empty()
            status_placeholder = st.empty()
            logs_placeholder = st.empty()
            
            # Get real progress from progress tracker
            try:
                use_case_name = st.session_state.get('pipeline_use_case', selected_use_case)
                history = st.session_state['progress_tracker'].get_performance_history(use_case_name)
                max_iter = st.session_state.get('pipeline_max_iterations', 5)
                
                if history:
                    current_iter = len(history)
                    progress_value = min(current_iter / max_iter, 1.0)
                    latest_result = history[-1]
                    
                    with progress_placeholder.container():
                        st.progress(progress_value)
                        st.write(f"Iteration {current_iter} of {max_iter}")
                    
                    with status_placeholder.container():
                        st.info(f"🔄 Current Step: {latest_result.step}")
                        st.metric("Latest Win Rate", f"{latest_result.win_rate:.1%}")
                else:
                    with progress_placeholder.container():
                        st.progress(0.1)
                        st.write("Starting pipeline...")
                    
                    with status_placeholder.container():
                        st.info("🔄 Initializing pipeline...")
                
                # Show logs from log file
                with logs_placeholder.container():
                    try:
                        log_file = Path("logs/pipeline.log")
                        if log_file.exists():
                            with open(log_file, 'r', encoding='utf-8') as f:
                                # Get last 50 lines
                                lines = f.readlines()
                                recent_logs = ''.join(lines[-50:])
                                st.text_area(
                                    "Pipeline Logs (last 50 lines)",
                                    value=recent_logs,
                                    height=300,
                                    disabled=True
                                )
                    except Exception as e:
                        st.text_area(
                            "Pipeline Logs",
                            value=f"Unable to load logs: {e}",
                            height=300,
                            disabled=True
                        )
                
                # Check if pipeline completed
                if st.session_state.get('pipeline_result'):
                    result = st.session_state['pipeline_result']
                    st.success(f"✅ Pipeline completed! Final win rate: {result.final_win_rate:.1%}")
                    st.session_state['pipeline_running'] = False
                    del st.session_state['pipeline_result']
                    time.sleep(2)
                    st.rerun()
                
                # Check for errors
                if st.session_state.get('pipeline_error'):
                    error = st.session_state['pipeline_error']
                    st.error(f"❌ Pipeline failed: {error}")
                    st.session_state['pipeline_running'] = False
                    del st.session_state['pipeline_error']
                
            except Exception as e:
                logger.error(f"Error displaying pipeline progress: {e}")
                with progress_placeholder.container():
                    st.progress(0.5)
                
                with status_placeholder.container():
                    st.info("🔄 Pipeline running...")
            
            # Control buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Refresh Status", use_container_width=True):
                    st.rerun()
            with col2:
                if st.button("⏹️ Stop", use_container_width=True):
                    st.session_state['pipeline_running'] = False
                    st.warning("Pipeline stopped by user")
                    st.rerun()
        else:
            # Start pipeline button
            st.info("📝 **Ready to start pipeline execution with real AWS integration.**")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("▶️ Start Pipeline", use_container_width=True, type="primary"):
                    try:
                        # Import the pipeline
                        from src.finetuning_pipeline import FinetuningPipeline
                        
                        # Initialize pipeline
                        pipeline = FinetuningPipeline(
                            st.session_state['config_manager'],
                            st.session_state['progress_tracker']
                        )
                        
                        # Set pipeline running flag
                        st.session_state['pipeline_running'] = True
                        st.session_state['pipeline_use_case'] = selected_use_case
                        st.session_state['pipeline_max_iterations'] = max_iterations
                        
                        st.success(f"✅ Pipeline started for use case: {selected_use_case}")
                        st.info("🔄 Starting pipeline execution...")
                        
                        # Run pipeline in a thread to avoid blocking UI
                        def run_pipeline_thread():
                            try:
                                logger.info(f"Starting pipeline thread for {selected_use_case}")
                                result = pipeline.run(selected_use_case, max_iterations=max_iterations)
                                st.session_state['pipeline_result'] = result
                                st.session_state['pipeline_running'] = False
                                logger.info(f"Pipeline completed: {result.success}")
                            except Exception as e:
                                logger.error(f"Pipeline error: {e}", exc_info=True)
                                st.session_state['pipeline_error'] = str(e)
                                st.session_state['pipeline_running'] = False
                        
                        # Start thread
                        pipeline_thread = threading.Thread(target=run_pipeline_thread, daemon=True)
                        pipeline_thread.start()
                        st.session_state['pipeline_thread'] = pipeline_thread
                        
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to start pipeline: {e}")
                        logger.error(f"Failed to start pipeline: {e}", exc_info=True)
                        st.session_state['pipeline_running'] = False
            
            with col2:
                if st.button("🔄 Resume", use_container_width=True):
                    st.info("Resume functionality: Load saved pipeline state and continue from last checkpoint")
        
        st.markdown("---")
        
        # Show previous runs
        if st.session_state.get('progress_tracker'):
            history = st.session_state['progress_tracker'].get_performance_history(selected_use_case)
            if history:
                st.subheader("📊 Previous Runs")
                
                # Create table of previous runs
                runs_data = []
                for result in history:
                    runs_data.append({
                        'Iteration': result.iteration,
                        'Win Rate': f"{result.win_rate:.1%}",
                        'Training Time': f"{result.training_time_seconds // 60}m {result.training_time_seconds % 60}s",
                        'Timestamp': result.evaluation_time.strftime('%Y-%m-%d %H:%M'),
                        'Endpoint': result.endpoint_name
                    })
                
                df = pd.DataFrame(runs_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
    
    except Exception as e:
        logger.error(f"Error rendering run pipeline page: {e}")
        st.error(f"Error: {e}")


def render_results():
    """
    Display detailed results including response comparisons and judgments.
    
    Section 11.6: Results visualization with:
    - Side-by-side response comparison view
    - Judgment details with reasoning
    - Win rate and performance metrics
    - Filtering and sorting options
    """
    st.title("📊 View Results")
    st.markdown("---")
    
    if st.session_state.get('config_manager') is None or st.session_state.get('progress_tracker') is None:
        st.error("Required components not initialized.")
        return
    
    try:
        use_cases = st.session_state['config_manager'].list_use_cases()
        
        # Filter to use cases with results
        use_cases_with_results = []
        for uc_name in use_cases:
            history = st.session_state['progress_tracker'].get_performance_history(uc_name)
            if history:
                use_cases_with_results.append(uc_name)
        
        if not use_cases_with_results:
            st.warning("No results available yet. Run a pipeline first.")
            if st.button("▶️ Run Pipeline"):
                st.session_state['current_page'] = "Run Pipeline"
                st.rerun()
            return
        
        # Use case selection
        st.subheader("Select Use Case and Iteration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_use_case = st.selectbox(
                "Use Case",
                use_cases_with_results,
                help="Select use case to view results"
            )
        
        # Get iterations for selected use case
        history = st.session_state['progress_tracker'].get_performance_history(selected_use_case)
        
        with col2:
            iteration_options = [f"Iteration {r.iteration}" for r in history]
            selected_iteration_idx = st.selectbox(
                "Iteration",
                range(len(iteration_options)),
                format_func=lambda i: iteration_options[i],
                index=len(iteration_options) - 1,  # Default to latest
                help="Select iteration to view"
            )
        
        selected_result = history[selected_iteration_idx]
        
        st.markdown("---")
        
        # Performance metrics
        st.subheader("📈 Performance Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Win Rate", f"{selected_result.win_rate:.1%}")
        
        with col2:
            st.metric("Iteration", selected_result.iteration)
        
        with col3:
            training_time_min = selected_result.training_time_seconds // 60
            st.metric("Training Time", f"{training_time_min}m")
        
        with col4:
            st.metric("Endpoint", selected_result.endpoint_name[:20] + "...")
        
        st.markdown("---")
        
        # Response comparisons
        st.subheader("🔍 Response Comparisons")
        
        # Note: In real implementation, we would load actual judgments from saved results
        # For now, we'll show a demo structure
        st.info("📝 **Note:** This shows the structure for response comparisons. "
                "Full implementation requires loading saved evaluation results.")
        
        # Load use case to get questions
        use_case = st.session_state['config_manager'].load_use_case(selected_use_case)
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            filter_winner = st.selectbox(
                "Filter by winner",
                ["All", "Finetuned", "Baseline", "Tie"],
                help="Filter comparisons by winner"
            )
        
        with col2:
            sort_by = st.selectbox(
                "Sort by",
                ["Question Order", "Confidence (High to Low)", "Confidence (Low to High)"],
                help="Sort comparisons"
            )
        
        # Display comparisons for each question
        for i, question in enumerate(use_case.test_questions, 1):
            with st.expander(f"Question {i}", expanded=(i == 1)):
                st.markdown(f"**Question:** {question}")
                st.markdown("---")
                
                # Side-by-side comparison
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 🤖 Finetuned Model")
                    # Demo response
                    st.write("This is where the finetuned model's response would appear. "
                            "The actual response would be loaded from saved evaluation results.")
                    st.success("✓ Winner")
                
                with col2:
                    st.markdown("### 🦙 Baseline 70B Model")
                    # Demo response
                    st.write("This is where the baseline model's response would appear. "
                            "The actual response would be loaded from saved evaluation results.")
                
                # Judge reasoning
                with st.expander("⚖️ Judge Reasoning"):
                    st.markdown("**Winner:** Finetuned Model")
                    st.markdown("**Confidence:** 85%")
                    st.markdown("**Reasoning:**")
                    st.write("The judge's detailed reasoning would appear here, explaining "
                            "why one response was chosen over the other based on the evaluation criteria.")
        
        st.markdown("---")
        
        # Export options
        st.subheader("💾 Export Results")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Export as JSON", use_container_width=True):
                st.info("Export functionality: Download results as JSON file")
        
        with col2:
            if st.button("📥 Export as CSV", use_container_width=True):
                st.info("Export functionality: Download results as CSV file")
    
    except Exception as e:
        logger.error(f"Error rendering results page: {e}")
        st.error(f"Error: {e}")


def render_training_data():
    """
    Display generated training data with pagination.
    
    Section 11.7: Training data viewer with:
    - Training data viewer with pagination
    - Examples with formatting
    - Search and filter functionality
    - Dataset statistics
    """
    st.title("📝 Training Data")
    st.markdown("---")
    
    if st.session_state.get('config_manager') is None:
        st.error("Configuration manager not initialized.")
        return
    
    try:
        use_cases = st.session_state['config_manager'].list_use_cases()
        
        if not use_cases:
            st.warning("No use cases available.")
            return
        
        # Use case selection
        st.subheader("Select Use Case")
        
        selected_use_case = st.selectbox(
            "Use Case",
            use_cases,
            help="Select use case to view training data"
        )
        
        # Check for training data files
        training_data_dir = Path("event_files/training_data")
        training_data_files = []
        
        if training_data_dir.exists():
            # Look for files matching the use case
            training_data_files = list(training_data_dir.glob(f"{selected_use_case}_*.jsonl"))
        
        if not training_data_files:
            st.info(f"No training data found for '{selected_use_case}'. "
                   "Training data will be generated when you run the pipeline.")
            
            if st.button("▶️ Run Pipeline"):
                st.session_state['selected_use_case'] = selected_use_case
                st.session_state['current_page'] = "Run Pipeline"
                st.rerun()
            return
        
        # File selection
        st.subheader("Select Training Data File")
        
        file_options = [f.name for f in training_data_files]
        selected_file = st.selectbox(
            "Training Data File",
            file_options,
            help="Select training data file to view"
        )
        
        selected_file_path = training_data_dir / selected_file
        
        # Load training data
        try:
            examples = []
            with open(selected_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        examples.append(json.loads(line))
            
            st.markdown("---")
            
            # Dataset statistics
            st.subheader("📊 Dataset Statistics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Examples", len(examples))
            
            with col2:
                avg_instruction_len = sum(len(ex.get('instruction', '')) for ex in examples) // len(examples) if examples else 0
                st.metric("Avg Instruction Length", f"{avg_instruction_len} chars")
            
            with col3:
                avg_response_len = sum(len(ex.get('response', '')) for ex in examples) // len(examples) if examples else 0
                st.metric("Avg Response Length", f"{avg_response_len} chars")
            
            with col4:
                file_size_kb = selected_file_path.stat().st_size / 1024
                st.metric("File Size", f"{file_size_kb:.1f} KB")
            
            st.markdown("---")
            
            # Search and filter
            st.subheader("🔍 Search and Filter")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                search_term = st.text_input(
                    "Search in examples",
                    placeholder="Enter search term...",
                    help="Search in instruction, context, and response fields"
                )
            
            with col2:
                show_full_text = st.checkbox("Show full text", value=False)
            
            # Filter examples
            filtered_examples = examples
            if search_term:
                filtered_examples = [
                    ex for ex in examples
                    if search_term.lower() in ex.get('instruction', '').lower()
                    or search_term.lower() in ex.get('context', '').lower()
                    or search_term.lower() in ex.get('response', '').lower()
                ]
            
            st.write(f"**Showing {len(filtered_examples)} of {len(examples)} examples**")
            
            st.markdown("---")
            
            # Pagination
            st.subheader("📄 Training Examples")
            
            page_size = st.select_slider(
                "Examples per page",
                options=[5, 10, 20, 50, 100],
                value=10
            )
            
            total_pages = (len(filtered_examples) + page_size - 1) // page_size if filtered_examples else 1
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                page = st.number_input(
                    "Page",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    help=f"Total pages: {total_pages}"
                )
            
            # Calculate pagination
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, len(filtered_examples))
            
            # Display examples
            for i in range(start_idx, end_idx):
                example = filtered_examples[i]
                
                with st.expander(f"Example {i + 1}", expanded=False):
                    st.markdown("**Instruction:**")
                    instruction = example.get('instruction', '')
                    if show_full_text or len(instruction) <= 200:
                        st.write(instruction)
                    else:
                        st.write(instruction[:200] + "...")
                    
                    st.markdown("**Context:**")
                    context = example.get('context', '')
                    if show_full_text or len(context) <= 200:
                        st.write(context)
                    else:
                        st.write(context[:200] + "...")
                    
                    st.markdown("**Response:**")
                    response = example.get('response', '')
                    if show_full_text or len(response) <= 300:
                        st.write(response)
                    else:
                        st.write(response[:300] + "...")
                    
                    # Show full JSON
                    with st.expander("View JSON"):
                        st.json(example)
            
            st.markdown("---")
            
            # Export options
            st.subheader("💾 Export Data")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 Download JSONL", use_container_width=True):
                    st.info("Download functionality: Save filtered examples as JSONL")
            
            with col2:
                if st.button("📥 Download CSV", use_container_width=True):
                    st.info("Download functionality: Convert to CSV and download")
        
        except Exception as e:
            st.error(f"Error loading training data: {e}")
            logger.error(f"Error loading training data from {selected_file_path}: {e}")
    
    except Exception as e:
        logger.error(f"Error rendering training data page: {e}")
        st.error(f"Error: {e}")


def render_performance():
    """
    Display performance charts and metrics across iterations.
    
    Section 11.8: Performance visualization with:
    - Performance charts with plotly
    - Iteration history table
    - Improvement metrics
    - Export functionality for reports
    """
    st.title("📈 Performance")
    st.markdown("---")
    
    if st.session_state.get('config_manager') is None or st.session_state.get('progress_tracker') is None:
        st.error("Required components not initialized.")
        return
    
    try:
        use_cases = st.session_state['config_manager'].list_use_cases()
        
        # Filter to use cases with results
        use_cases_with_results = []
        for uc_name in use_cases:
            history = st.session_state['progress_tracker'].get_performance_history(uc_name)
            if history:
                use_cases_with_results.append(uc_name)
        
        if not use_cases_with_results:
            st.warning("No performance data available yet. Run a pipeline first.")
            if st.button("▶️ Run Pipeline"):
                st.session_state['current_page'] = "Run Pipeline"
                st.rerun()
            return
        
        # Use case selection
        st.subheader("Select Use Case")
        
        selected_use_case = st.selectbox(
            "Use Case",
            use_cases_with_results,
            help="Select use case to view performance"
        )
        
        # Get performance history
        history = st.session_state['progress_tracker'].get_performance_history(selected_use_case)
        
        if not history:
            st.warning(f"No performance data for '{selected_use_case}'")
            return
        
        st.markdown("---")
        
        # Summary metrics
        st.subheader("📊 Performance Summary")
        
        initial_win_rate = history[0].win_rate
        final_win_rate = history[-1].win_rate
        improvement = final_win_rate - initial_win_rate
        best_iteration = max(history, key=lambda x: x.win_rate)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Iterations", len(history))
        
        with col2:
            st.metric("Initial Win Rate", f"{initial_win_rate:.1%}")
        
        with col3:
            st.metric("Final Win Rate", f"{final_win_rate:.1%}")
        
        with col4:
            st.metric("Improvement", f"{improvement:+.1%}", 
                     delta=f"{improvement:+.1%}",
                     delta_color="normal")
        
        st.markdown("---")
        
        # Win rate progression chart
        st.subheader("📈 Win Rate Progression")
        
        # Prepare data for chart
        iterations = [r.iteration for r in history]
        win_rates = [r.win_rate for r in history]
        
        # Create line chart with plotly
        fig = go.Figure()
        
        # Add win rate line
        fig.add_trace(go.Scatter(
            x=iterations,
            y=win_rates,
            mode='lines+markers',
            name='Win Rate',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=10)
        ))
        
        # Add threshold line (if available)
        try:
            pipeline_config = st.session_state['config_manager'].load_pipeline_config()
            threshold = pipeline_config.performance_threshold
            fig.add_hline(
                y=threshold,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Threshold ({threshold:.0%})",
                annotation_position="right"
            )
        except:
            pass
        
        # Highlight best iteration
        fig.add_trace(go.Scatter(
            x=[best_iteration.iteration],
            y=[best_iteration.win_rate],
            mode='markers',
            name='Best Iteration',
            marker=dict(size=15, color='gold', symbol='star')
        ))
        
        fig.update_layout(
            title="Win Rate Across Iterations",
            xaxis_title="Iteration",
            yaxis_title="Win Rate",
            yaxis_tickformat='.0%',
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Iteration history table
        st.subheader("📋 Iteration History")
        
        # Prepare table data
        table_data = []
        for result in history:
            table_data.append({
                'Iteration': result.iteration,
                'Win Rate': f"{result.win_rate:.1%}",
                'Training Time': f"{result.training_time_seconds // 60}m {result.training_time_seconds % 60}s",
                'Timestamp': result.evaluation_time.strftime('%Y-%m-%d %H:%M'),
                'Model Artifact': result.model_artifact_uri.split('/')[-1] if result.model_artifact_uri else 'N/A',
                'Endpoint': result.endpoint_name
            })
        
        df = pd.DataFrame(table_data)
        
        # Highlight best iteration
        def highlight_best(row):
            if row['Iteration'] == best_iteration.iteration:
                return ['background-color: #ffffcc'] * len(row)
            return [''] * len(row)
        
        styled_df = df.style.apply(highlight_best, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.info(f"⭐ Best iteration: {best_iteration.iteration} with {best_iteration.win_rate:.1%} win rate")
        
        st.markdown("---")
        
        # Improvement metrics
        st.subheader("📊 Improvement Metrics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Iteration-over-Iteration Changes**")
            
            changes_data = []
            for i in range(1, len(history)):
                prev_rate = history[i-1].win_rate
                curr_rate = history[i].win_rate
                change = curr_rate - prev_rate
                changes_data.append({
                    'From': f"Iter {history[i-1].iteration}",
                    'To': f"Iter {history[i].iteration}",
                    'Change': f"{change:+.1%}"
                })
            
            if changes_data:
                changes_df = pd.DataFrame(changes_data)
                st.dataframe(changes_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("**Training Time Analysis**")
            
            total_training_time = sum(r.training_time_seconds for r in history)
            avg_training_time = total_training_time // len(history)
            
            st.write(f"**Total Training Time:** {total_training_time // 60}m {total_training_time % 60}s")
            st.write(f"**Average per Iteration:** {avg_training_time // 60}m {avg_training_time % 60}s")
            st.write(f"**Fastest Iteration:** {min(r.training_time_seconds for r in history) // 60}m")
            st.write(f"**Slowest Iteration:** {max(r.training_time_seconds for r in history) // 60}m")
        
        st.markdown("---")
        
        # Prompts evolution (if available)
        st.subheader("📝 Prompts Evolution")
        
        with st.expander("View Prompts Used in Each Iteration"):
            for result in history:
                st.markdown(f"### Iteration {result.iteration}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Data Generation Prompt:**")
                    st.text_area(
                        f"Data Gen {result.iteration}",
                        value=result.prompts_used.data_generation_prompt[:500] + "...",
                        height=150,
                        disabled=True,
                        label_visibility="collapsed"
                    )
                
                with col2:
                    st.markdown("**Judge Prompt:**")
                    st.text_area(
                        f"Judge {result.iteration}",
                        value=result.prompts_used.judge_prompt[:500] + "...",
                        height=150,
                        disabled=True,
                        label_visibility="collapsed"
                    )
                
                st.markdown("---")
        
        st.markdown("---")
        
        # Export functionality
        st.subheader("💾 Export Performance Report")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📥 Export as JSON", use_container_width=True):
                # Prepare report data
                report_data = {
                    'use_case': selected_use_case,
                    'total_iterations': len(history),
                    'initial_win_rate': initial_win_rate,
                    'final_win_rate': final_win_rate,
                    'improvement': improvement,
                    'best_iteration': best_iteration.iteration,
                    'best_win_rate': best_iteration.win_rate,
                    'iterations': table_data
                }
                
                st.download_button(
                    label="Download JSON",
                    data=json.dumps(report_data, indent=2),
                    file_name=f"{selected_use_case}_performance_report.json",
                    mime="application/json"
                )
        
        with col2:
            if st.button("📥 Export as CSV", use_container_width=True):
                csv_data = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"{selected_use_case}_iteration_history.csv",
                    mime="text/csv"
                )
        
        with col3:
            if st.button("📊 Generate Report", use_container_width=True):
                st.info("Generate comprehensive PDF report functionality coming soon!")
    
    except Exception as e:
        logger.error(f"Error rendering performance page: {e}")
        st.error(f"Error: {e}")


def main():
    """
    Main Streamlit application with multi-page navigation.
    
    Sets up the page configuration, initializes session state,
    and provides navigation between different pages of the application.
    """
    # Configure page
    st.set_page_config(
        page_title="LLM Finetuning Pipeline",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session_state()
    
    # Sidebar navigation
    st.sidebar.title("🤖 LLM Finetuning Pipeline")
    st.sidebar.markdown("---")
    
    # Navigation menu
    pages = {
        "Dashboard": {
            "icon": "🏠",
            "function": render_dashboard
        },
        "Use Cases": {
            "icon": "📋",
            "function": render_use_cases
        },
        "Create Use Case": {
            "icon": "➕",
            "function": render_create_use_case
        },
        "Run Pipeline": {
            "icon": "▶️",
            "function": render_run_pipeline
        },
        "View Results": {
            "icon": "📊",
            "function": render_results
        },
        "Training Data": {
            "icon": "📝",
            "function": render_training_data
        },
        "Performance": {
            "icon": "📈",
            "function": render_performance
        }
    }
    
    # Page selection
    selected_page = st.sidebar.radio(
        "Navigation",
        list(pages.keys()),
        index=list(pages.keys()).index(st.session_state.get('current_page', 'Dashboard')),
        format_func=lambda x: f"{pages[x]['icon']} {x}"
    )
    
    # Update current page in session state
    st.session_state['current_page'] = selected_page
    
    st.sidebar.markdown("---")
    
    # Display pipeline status in sidebar
    if st.session_state.get('pipeline_running'):
        st.sidebar.warning("⚠️ Pipeline Running")
    else:
        st.sidebar.success("✅ Pipeline Ready")
    
    # Display component status
    with st.sidebar.expander("🔧 System Status"):
        if st.session_state.get('config_manager'):
            st.success("✅ Configuration Manager")
        else:
            st.error("❌ Configuration Manager")
        
        if st.session_state.get('progress_tracker'):
            st.success("✅ Progress Tracker")
        else:
            st.error("❌ Progress Tracker")
    
    st.sidebar.markdown("---")
    st.sidebar.info(
        "**Automated LLM Finetuning Pipeline**\n\n"
        "A system for automated model finetuning with "
        "self-improvement capabilities."
    )
    
    # Render selected page
    try:
        pages[selected_page]["function"]()
    except Exception as e:
        logger.error(f"Error rendering page {selected_page}: {e}")
        st.error(f"Error rendering page: {e}")
        st.exception(e)


if __name__ == "__main__":
    main()
