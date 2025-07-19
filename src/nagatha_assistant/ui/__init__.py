"""
Nagatha Assistant UI package.

This package contains the user interface components for Nagatha Assistant,
including the main chat interface and the enhanced dashboard view.
"""

from .dashboard import DashboardApp

# Re-export functions from the main ui module for backward compatibility
def _get_main_ui_functions():
    """Lazy import to avoid circular imports."""
    import sys
    import os
    from pathlib import Path
    
    # Add the parent directory to path to access the main ui module
    parent_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(parent_dir))
    
    # Import directly from the ui.py file
    import importlib.util
    ui_path = parent_dir / "nagatha_assistant" / "ui.py"
    spec = importlib.util.spec_from_file_location("main_ui", ui_path)
    main_ui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_ui)
    
    return main_ui

# Lazy loading for backward compatibility
def __getattr__(name):
    """Provide backward compatibility for imports from main ui module."""
    if name in ["markdown_to_rich", "run_app", "ToolsInfoModal", "SessionSelectorModal", "ChatApp"]:
        main_ui = _get_main_ui_functions()
        return getattr(main_ui, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "DashboardApp", 
    "markdown_to_rich", 
    "run_app", 
    "ToolsInfoModal", 
    "SessionSelectorModal", 
    "ChatApp"
]