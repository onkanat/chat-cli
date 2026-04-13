from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from plugins.wiki_plugin import WikiPlugin

@pytest.fixture
def wiki_plugin():
    plugin = WikiPlugin()
    plugin._cfg["wiki_path"] = "/tmp/fake_wiki"
    return plugin

@patch("plugins.wiki_plugin.console.print")
def test_wiki_help(mock_print, wiki_plugin):
    """Test the /wiki help command."""
    wiki_plugin._cmd_wiki(["help"], {})
    assert mock_print.called

@patch("plugins.wiki_plugin.Path.exists")
@patch("plugins.wiki_plugin.Path.rglob")
@patch("plugins.wiki_plugin.console.print")
def test_wiki_list(mock_print, mock_rglob, mock_exists, wiki_plugin):
    """Test the /wiki list command."""
    mock_exists.return_value = True
    # Simulate finding some markdown files
    mock_rglob.return_value = [Path("/tmp/fake_wiki/file1.md"), Path("/tmp/fake_wiki/db.md")]
    
    wiki_plugin._cmd_wiki(["list"], {})
    assert mock_print.called

@patch("plugins.wiki_plugin.console.print")
@patch("plugins.wiki_plugin.WikiPlugin._post")
def test_wiki_search(mock_post, mock_print, wiki_plugin):
    """Test the /wiki search command."""
    # Mock omni-daemon search response
    mock_post.return_value = {
        "results": [
            {"path": "file1.md", "content": "Test content", "score": 0.95}
        ]
    }
    wiki_plugin._cmd_wiki(["search", "test_query"], {})
    assert len(wiki_plugin._last_search_results) == 1
    assert mock_print.called

@patch("plugins.wiki_plugin.console.print")
def test_wiki_open(mock_print, wiki_plugin):
    """Test the /wiki open command."""
    # First search to populate results
    wiki_plugin._last_search_results = [
        {"path": "file1.md", "content": "Test content", "score": 0.95}
    ]
    
    context = {"history": []}
    wiki_plugin._cmd_wiki(["open", "1"], context)
    
    # Check if context was appended
    assert len(context["history"]) == 1
    assert "Test content" in context["history"][0]["text"]
    assert mock_print.called

@patch("plugins.wiki_plugin.Path.exists")
@patch("plugins.wiki_plugin.Path.read_text")
@patch("plugins.wiki_plugin.console.print")
def test_wiki_show_by_name(mock_print, mock_read_text, mock_exists, wiki_plugin):
    """Test /wiki show <page_name> reads and renders the file."""
    mock_exists.return_value = True
    mock_read_text.return_value = "# Header\nContent of the file"

    wiki_plugin._cmd_wiki(["show", "target_file"], {})
    assert mock_print.called


@patch("plugins.wiki_plugin.console.print")
def test_wiki_show_by_row_number(mock_print, wiki_plugin):
    """/wiki show <n> should display full content from _last_search_results."""
    wiki_plugin._last_search_results = [
        {"path": "/tmp/fake_wiki/page1.md", "content": "# Page1\nSome content", "score": 0.9}
    ]
    # Patch Path.exists so we don't hit the real FS
    with patch("plugins.wiki_plugin.Path.exists", return_value=False):
        wiki_plugin._cmd_wiki(["show", "1"], {})
    assert mock_print.called
    # Should NOT print the "search first" warning
    warning_calls = [c for c in mock_print.call_args_list if "arama yapın" in str(c)]
    assert not warning_calls


@patch("plugins.wiki_plugin.console.print")
def test_wiki_show_no_prior_search(mock_print, wiki_plugin):
    """/wiki show <n> without prior search should warn user."""
    wiki_plugin._last_search_results = []
    wiki_plugin._cmd_wiki(["show", "1"], {})
    warning = any("arama yapın" in str(c) for c in mock_print.call_args_list)
    assert warning


@patch("plugins.wiki_plugin.console.print")
def test_wiki_show_out_of_range(mock_print, wiki_plugin):
    """/wiki show 99 with only 1 result should show range error."""
    wiki_plugin._last_search_results = [
        {"path": "page.md", "content": "content", "score": 0.9}
    ]
    wiki_plugin._cmd_wiki(["show", "99"], {})
    error = any("arası" in str(c) for c in mock_print.call_args_list)
    assert error
