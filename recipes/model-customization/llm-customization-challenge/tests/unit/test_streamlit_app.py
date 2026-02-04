"""
Unit tests for Streamlit application entry point.

Tests the main application structure, session state initialization,
and page navigation setup.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import streamlit as st

# Import the module to test
import streamlit_app


class TestSessionStateInitialization:
    """Test session state initialization."""
    
    def test_init_session_state_creates_config_manager(self):
        """Test that init_session_state creates ConfigurationManager."""
        # Mock streamlit session state
        mock_session_state = {}
        
        with patch('streamlit_app.st.session_state', mock_session_state):
            with patch('streamlit_app.ConfigurationManager') as mock_cm:
                with patch('streamlit_app.ProgressTracker') as mock_pt:
                    streamlit_app.init_session_state()
                    
                    # Verify ConfigurationManager was created
                    mock_cm.assert_called_once()
                    assert 'config_manager' in mock_session_state
    
    def test_init_session_state_creates_progress_tracker(self):
        """Test that init_session_state creates ProgressTracker."""
        # Mock streamlit session state
        mock_session_state = {}
        
        with patch('streamlit_app.st.session_state', mock_session_state):
            with patch('streamlit_app.ConfigurationManager'):
                with patch('streamlit_app.ProgressTracker') as mock_pt:
                    streamlit_app.init_session_state()
                    
                    # Verify ProgressTracker was created
                    mock_pt.assert_called_once()
                    assert 'progress_tracker' in mock_session_state
    
    def test_init_session_state_initializes_ui_variables(self):
        """Test that init_session_state initializes UI state variables."""
        # Mock streamlit session state
        mock_session_state = {}
        
        with patch('streamlit_app.st.session_state', mock_session_state):
            with patch('streamlit_app.ConfigurationManager'):
                with patch('streamlit_app.ProgressTracker'):
                    streamlit_app.init_session_state()
                    
                    # Verify UI state variables are initialized
                    assert 'selected_use_case' in mock_session_state
                    assert mock_session_state['selected_use_case'] is None
                    assert 'pipeline_running' in mock_session_state
                    assert mock_session_state['pipeline_running'] is False
                    assert 'current_page' in mock_session_state
                    assert mock_session_state['current_page'] == "Dashboard"
    
    def test_init_session_state_handles_config_manager_error(self):
        """Test that init_session_state handles ConfigurationManager initialization errors."""
        # Mock streamlit session state
        mock_session_state = {}
        
        with patch('streamlit_app.st.session_state', mock_session_state):
            with patch('streamlit_app.ConfigurationManager', side_effect=Exception("Config error")):
                with patch('streamlit_app.ProgressTracker'):
                    with patch('streamlit_app.st.error') as mock_error:
                        streamlit_app.init_session_state()
                        
                        # Verify error was displayed
                        mock_error.assert_called()
                        assert 'config_manager' in mock_session_state
                        assert mock_session_state['config_manager'] is None
    
    def test_init_session_state_handles_progress_tracker_error(self):
        """Test that init_session_state handles ProgressTracker initialization errors."""
        # Mock streamlit session state
        mock_session_state = {}
        
        with patch('streamlit_app.st.session_state', mock_session_state):
            with patch('streamlit_app.ConfigurationManager'):
                with patch('streamlit_app.ProgressTracker', side_effect=Exception("Tracker error")):
                    with patch('streamlit_app.st.error') as mock_error:
                        streamlit_app.init_session_state()
                        
                        # Verify error was displayed
                        mock_error.assert_called()
                        assert 'progress_tracker' in mock_session_state
                        assert mock_session_state['progress_tracker'] is None
    
    def test_init_session_state_does_not_reinitialize(self):
        """Test that init_session_state does not reinitialize existing components."""
        # Mock streamlit session state with existing components
        existing_cm = Mock()
        existing_pt = Mock()
        mock_session_state = {
            'config_manager': existing_cm,
            'progress_tracker': existing_pt,
            'selected_use_case': 'test_case',
            'pipeline_running': True,
            'current_page': 'Results'
        }
        
        with patch('streamlit_app.st.session_state', mock_session_state):
            with patch('streamlit_app.ConfigurationManager') as mock_cm:
                with patch('streamlit_app.ProgressTracker') as mock_pt:
                    streamlit_app.init_session_state()
                    
                    # Verify existing components were not replaced
                    mock_cm.assert_not_called()
                    mock_pt.assert_not_called()
                    assert mock_session_state['config_manager'] is existing_cm
                    assert mock_session_state['progress_tracker'] is existing_pt
                    assert mock_session_state['selected_use_case'] == 'test_case'
                    assert mock_session_state['pipeline_running'] is True
                    assert mock_session_state['current_page'] == 'Results'


class TestPageRendering:
    """Test page rendering functions."""
    
    def test_render_dashboard_with_no_config_manager(self):
        """Test that render_dashboard handles missing config manager."""
        mock_session_state = {'config_manager': None}
        
        with patch('streamlit_app.st.session_state', mock_session_state):
            with patch('streamlit_app.st.error') as mock_error:
                with patch('streamlit_app.st.title'):
                    streamlit_app.render_dashboard()
                    
                    # Verify error was displayed
                    mock_error.assert_called_once()
    
    def test_render_dashboard_displays_use_cases(self):
        """Test that render_dashboard displays use cases."""
        mock_cm = Mock()
        mock_cm.list_use_cases.return_value = ['use_case_1', 'use_case_2']
        mock_pt = Mock()
        mock_pt.get_performance_history.return_value = []
        
        mock_session_state = {
            'config_manager': mock_cm,
            'progress_tracker': mock_pt,
            'pipeline_running': False
        }
        
        with patch('streamlit_app.st.session_state', mock_session_state):
            with patch('streamlit_app.st.title'):
                with patch('streamlit_app.st.markdown'):
                    with patch('streamlit_app.st.columns', return_value=[Mock(), Mock(), Mock()]):
                        with patch('streamlit_app.st.metric'):
                            with patch('streamlit_app.st.subheader'):
                                with patch('streamlit_app.st.expander'):
                                    streamlit_app.render_dashboard()
                                    
                                    # Verify list_use_cases was called
                                    mock_cm.list_use_cases.assert_called_once()
    
    def test_render_use_cases_shows_placeholder(self):
        """Test that render_use_cases shows placeholder message."""
        with patch('streamlit_app.st.title'):
            with patch('streamlit_app.st.markdown'):
                with patch('streamlit_app.st.info') as mock_info:
                    streamlit_app.render_use_cases()
                    
                    # Verify placeholder message is shown
                    mock_info.assert_called_once()
    
    def test_render_create_use_case_shows_placeholder(self):
        """Test that render_create_use_case shows placeholder message."""
        with patch('streamlit_app.st.title'):
            with patch('streamlit_app.st.markdown'):
                with patch('streamlit_app.st.info') as mock_info:
                    streamlit_app.render_create_use_case()
                    
                    # Verify placeholder message is shown
                    mock_info.assert_called_once()
    
    def test_render_run_pipeline_shows_placeholder(self):
        """Test that render_run_pipeline shows placeholder message."""
        with patch('streamlit_app.st.title'):
            with patch('streamlit_app.st.markdown'):
                with patch('streamlit_app.st.info') as mock_info:
                    streamlit_app.render_run_pipeline()
                    
                    # Verify placeholder message is shown
                    mock_info.assert_called_once()
    
    def test_render_results_shows_placeholder(self):
        """Test that render_results shows placeholder message."""
        with patch('streamlit_app.st.title'):
            with patch('streamlit_app.st.markdown'):
                with patch('streamlit_app.st.info') as mock_info:
                    streamlit_app.render_results()
                    
                    # Verify placeholder message is shown
                    mock_info.assert_called_once()
    
    def test_render_training_data_shows_placeholder(self):
        """Test that render_training_data shows placeholder message."""
        with patch('streamlit_app.st.title'):
            with patch('streamlit_app.st.markdown'):
                with patch('streamlit_app.st.info') as mock_info:
                    streamlit_app.render_training_data()
                    
                    # Verify placeholder message is shown
                    mock_info.assert_called_once()
    
    def test_render_performance_shows_placeholder(self):
        """Test that render_performance shows placeholder message."""
        with patch('streamlit_app.st.title'):
            with patch('streamlit_app.st.markdown'):
                with patch('streamlit_app.st.info') as mock_info:
                    streamlit_app.render_performance()
                    
                    # Verify placeholder message is shown
                    mock_info.assert_called_once()


class TestMainFunction:
    """Test main application function."""
    
    def test_main_sets_page_config(self):
        """Test that main() sets page configuration."""
        with patch('streamlit_app.st.set_page_config') as mock_config:
            with patch('streamlit_app.init_session_state'):
                with patch('streamlit_app.st.sidebar'):
                    with patch('streamlit_app.st.session_state', {
                        'current_page': 'Dashboard',
                        'pipeline_running': False,
                        'config_manager': Mock(),
                        'progress_tracker': Mock()
                    }):
                        with patch('streamlit_app.render_dashboard'):
                            streamlit_app.main()
                            
                            # Verify page config was set
                            mock_config.assert_called_once()
                            call_kwargs = mock_config.call_args[1]
                            assert call_kwargs['page_title'] == "LLM Finetuning Pipeline"
                            assert call_kwargs['layout'] == "wide"
    
    def test_main_initializes_session_state(self):
        """Test that main() initializes session state."""
        with patch('streamlit_app.st.set_page_config'):
            with patch('streamlit_app.init_session_state') as mock_init:
                with patch('streamlit_app.st.sidebar'):
                    with patch('streamlit_app.st.session_state', {
                        'current_page': 'Dashboard',
                        'pipeline_running': False,
                        'config_manager': Mock(),
                        'progress_tracker': Mock()
                    }):
                        with patch('streamlit_app.render_dashboard'):
                            streamlit_app.main()
                            
                            # Verify init_session_state was called
                            mock_init.assert_called_once()
    
    def test_main_renders_selected_page(self):
        """Test that main() renders the selected page."""
        with patch('streamlit_app.st.set_page_config'):
            with patch('streamlit_app.init_session_state'):
                # Mock sidebar.radio to return 'Dashboard'
                mock_radio = Mock(return_value='Dashboard')
                mock_sidebar = Mock()
                mock_sidebar.radio = mock_radio
                mock_sidebar.title = Mock()
                mock_sidebar.markdown = Mock()
                mock_sidebar.warning = Mock()
                mock_sidebar.success = Mock()
                mock_sidebar.expander = Mock(return_value=Mock(__enter__=Mock(), __exit__=Mock()))
                mock_sidebar.info = Mock()
                
                with patch('streamlit_app.st.sidebar', mock_sidebar):
                    with patch('streamlit_app.st.session_state', {
                        'current_page': 'Dashboard',
                        'pipeline_running': False,
                        'config_manager': Mock(),
                        'progress_tracker': Mock()
                    }):
                        with patch('streamlit_app.render_dashboard') as mock_render:
                            streamlit_app.main()
                            
                            # Verify dashboard was rendered
                            mock_render.assert_called_once()
    
    def test_main_handles_rendering_errors(self):
        """Test that main() handles page rendering errors gracefully."""
        with patch('streamlit_app.st.set_page_config'):
            with patch('streamlit_app.init_session_state'):
                with patch('streamlit_app.st.sidebar'):
                    with patch('streamlit_app.st.session_state', {
                        'current_page': 'Dashboard',
                        'pipeline_running': False,
                        'config_manager': Mock(),
                        'progress_tracker': Mock()
                    }):
                        with patch('streamlit_app.render_dashboard', side_effect=Exception("Render error")):
                            with patch('streamlit_app.st.error') as mock_error:
                                with patch('streamlit_app.st.exception') as mock_exception:
                                    streamlit_app.main()
                                    
                                    # Verify error was displayed
                                    mock_error.assert_called_once()
                                    mock_exception.assert_called_once()


class TestPageNavigation:
    """Test page navigation structure."""
    
    def test_all_pages_have_render_functions(self):
        """Test that all pages in the navigation have corresponding render functions."""
        # Map page names to their actual function names
        page_function_map = {
            "Dashboard": "render_dashboard",
            "Use Cases": "render_use_cases",
            "Create Use Case": "render_create_use_case",
            "Run Pipeline": "render_run_pipeline",
            "View Results": "render_results",  # Note: not render_view_results
            "Training Data": "render_training_data",
            "Performance": "render_performance"
        }
        
        for page, func_name in page_function_map.items():
            # Verify function exists
            assert hasattr(streamlit_app, func_name), f"Missing function: {func_name} for page: {page}"
            assert callable(getattr(streamlit_app, func_name)), f"Not callable: {func_name}"
