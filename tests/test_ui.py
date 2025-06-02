#!/usr/bin/env python3
"""
Pytest tests for the UI module functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nagatha_assistant.ui import markdown_to_rich, run_app


class TestUI:
    """Test cases for the UI module."""

    def test_markdown_to_rich_basic(self):
        """Test basic markdown conversion."""
        result = markdown_to_rich("**bold** text")
        assert "[bold]bold[/bold]" in result

    def test_markdown_to_rich_italic(self):
        """Test italic markdown conversion."""
        result = markdown_to_rich("*italic* text")
        assert "[italic]italic[/italic]" in result

    def test_markdown_to_rich_code(self):
        """Test code markdown conversion."""
        result = markdown_to_rich("`code` block")
        assert "[cyan]code[/cyan]" in result

    def test_markdown_to_rich_headers(self):
        """Test header markdown conversion."""
        result = markdown_to_rich("# Header")
        assert "[bold]Header[/bold]" in result

    def test_markdown_to_rich_links(self):
        """Test link markdown conversion."""
        result = markdown_to_rich("[text](url)")
        assert "[link=url]text[/link]" in result

    def test_markdown_to_rich_empty(self):
        """Test empty string handling."""
        result = markdown_to_rich("")
        assert result == ""

    def test_markdown_to_rich_none(self):
        """Test None handling."""
        result = markdown_to_rich(None)
        assert result is None

    def test_markdown_to_rich_code_blocks(self):
        """Test code block conversion."""
        result = markdown_to_rich("```python\ncode\n```")
        assert "[cyan]python\ncode\n[/cyan]" in result

    def test_markdown_to_rich_mixed(self):
        """Test mixed markdown elements."""
        text = "**bold** and *italic* with `code`"
        result = markdown_to_rich(text)
        assert "[bold]bold[/bold]" in result
        assert "[italic]italic[/italic]" in result
        assert "[cyan]code[/cyan]" in result

    @patch('nagatha_assistant.ui.ChatApp')
    @pytest.mark.asyncio
    async def test_run_app(self, mock_app_class):
        """Test the run_app function."""
        mock_app = MagicMock()
        mock_app.run_async = AsyncMock()
        mock_app_class.return_value = mock_app
        
        await run_app()
        
        mock_app_class.assert_called_once()
        mock_app.run_async.assert_called_once()

    @patch('nagatha_assistant.ui.ChatApp')
    @pytest.mark.asyncio 
    async def test_run_app_error_handling(self, mock_app_class):
        """Test run_app error handling."""
        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(side_effect=Exception("App error"))
        mock_app_class.return_value = mock_app
        
        # Should handle the error gracefully
        try:
            await run_app()
        except Exception as e:
            assert "App error" in str(e)

    def test_markdown_to_rich_complex_patterns(self):
        """Test complex markdown patterns."""
        text = "## Header with **bold** and *italic*\n\nCode: `function()` and ```\nblock\n```"
        result = markdown_to_rich(text)
        
        assert "[bold]Header with [bold]bold[/bold] and [italic]italic[/italic][/bold]" in result
        assert "[cyan]function()[/cyan]" in result
        assert "[cyan]\nblock\n[/cyan]" in result

    def test_markdown_escaping(self):
        """Test that special characters are handled properly."""
        text = "Text with * and _ and ` characters"
        result = markdown_to_rich(text)
        # Should not create invalid markup
        assert "[italic]" not in result or "Text with" not in result

    def test_ui_module_imports(self):
        """Test that UI module components can be imported."""
        from nagatha_assistant.ui import markdown_to_rich, run_app
        assert callable(markdown_to_rich)
        assert callable(run_app)

    def test_ui_classes_importable(self):
        """Test that UI classes are importable."""
        from nagatha_assistant.ui import ChatApp, ToolsInfoModal, SessionSelectorModal
        assert ChatApp is not None
        assert ToolsInfoModal is not None
        assert SessionSelectorModal is not None 