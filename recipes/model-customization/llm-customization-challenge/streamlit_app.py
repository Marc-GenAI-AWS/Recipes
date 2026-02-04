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

from src.configuration_manager import ConfigurationManager
from src.progress_tracker import ProgressTracker
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
    
    The dashboard shows:
    - Total number of use cases
    - Recent pipeline runs
    - Quick action buttons
    - Summary statistics
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
        
        # Display summary metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Use Cases", len(use_cases))
        
        with col2:
            # Count use cases with performance history
            use_cases_with_history = 0
            if st.session_state.get('progress_tracker'):
                for uc_name in use_cases:
                    history = st.session_state['progress_tracker'].get_performance_history(uc_name)
                    if history:
                        use_cases_with_history += 1
            st.metric("Use Cases with Results", use_cases_with_history)
        
        with col3:
            st.metric("Pipeline Status", "Ready" if not st.session_state.get('pipeline_running') else "Running")
        
        st.markdown("---")
        
        # Display use case list
        st.subheader("📋 Use Cases")
        
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
                        st.write(f"**Created:** {use_case.created_at}")
                        
                        # Show performance if available
                        if st.session_state.get('progress_tracker'):
                            history = st.session_state['progress_tracker'].get_performance_history(uc_name)
                            if history:
                                latest = history[-1]
                                st.write(f"**Latest Win Rate:** {latest.win_rate:.1%}")
                                st.write(f"**Total Iterations:** {len(history)}")
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
    
    Shows:
    - Searchable/filterable list of use cases
    - Key metadata for each use case
    - Edit and delete options
    - Performance history links
    """
    st.title("📋 Use Cases")
    st.markdown("---")
    
    st.info("🚧 Use case management page - Coming soon!")
    st.write("This page will allow you to:")
    st.write("- View all use cases with filtering and sorting")
    st.write("- Edit existing use cases")
    st.write("- Delete use cases")
    st.write("- View detailed performance history")


def render_create_use_case():
    """
    Display form for creating or editing use cases.
    
    Provides input fields for:
    - Use case name
    - Description
    - Test questions (add/edit/remove)
    - Judge criteria
    - Data generation prompt
    - Judge prompt
    """
    st.title("➕ Create Use Case")
    st.markdown("---")
    
    st.info("🚧 Use case creation form - Coming soon!")
    st.write("This page will provide a form to:")
    st.write("- Enter use case name and description")
    st.write("- Add test questions (one per line)")
    st.write("- Define judge criteria")
    st.write("- Configure data generation prompt")
    st.write("- Configure judge prompt")
    st.write("- Validate and save the use case")


def render_run_pipeline():
    """
    Display interface for starting and monitoring pipeline execution.
    
    Features:
    - Use case selection
    - Pipeline configuration options
    - Start/pause/resume/cancel controls
    - Real-time progress monitoring
    - Live log display
    """
    st.title("▶️ Run Pipeline")
    st.markdown("---")
    
    st.info("🚧 Pipeline execution interface - Coming soon!")
    st.write("This page will allow you to:")
    st.write("- Select a use case to run")
    st.write("- Configure pipeline parameters")
    st.write("- Start pipeline execution")
    st.write("- Monitor real-time progress")
    st.write("- View live logs")
    st.write("- Pause/resume/cancel execution")


def render_results():
    """
    Display detailed results including response comparisons and judgments.
    
    Shows:
    - Side-by-side response comparisons
    - Judge reasoning and confidence
    - Win rate and performance metrics
    - Filtering and sorting options
    """
    st.title("📊 View Results")
    st.markdown("---")
    
    st.info("🚧 Results visualization page - Coming soon!")
    st.write("This page will display:")
    st.write("- Side-by-side response comparisons")
    st.write("- Finetuned vs baseline model responses")
    st.write("- Judge decisions with reasoning")
    st.write("- Win rate and performance metrics")
    st.write("- Filtering and sorting options")


def render_training_data():
    """
    Display generated training data with pagination.
    
    Features:
    - Paginated view of training examples
    - Search and filter functionality
    - Dataset statistics
    - Example formatting and display
    """
    st.title("📝 Training Data")
    st.markdown("---")
    
    st.info("🚧 Training data viewer - Coming soon!")
    st.write("This page will show:")
    st.write("- Generated training examples with pagination")
    st.write("- Instruction, context, and response fields")
    st.write("- Search and filter functionality")
    st.write("- Dataset statistics and analysis")


def render_performance():
    """
    Display performance charts and metrics across iterations.
    
    Shows:
    - Win rate progression chart
    - Iteration history table
    - Improvement metrics
    - Export functionality
    """
    st.title("📈 Performance")
    st.markdown("---")
    
    st.info("🚧 Performance visualization page - Coming soon!")
    st.write("This page will display:")
    st.write("- Win rate progression chart")
    st.write("- Iteration history table")
    st.write("- Improvement metrics")
    st.write("- Best iteration identification")
    st.write("- Export functionality for reports")


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
