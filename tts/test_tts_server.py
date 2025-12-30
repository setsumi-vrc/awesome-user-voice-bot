import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import functions from core modules
from core.llm import generate_reply, _load_system_prompt


class TestSystemPrompt:
    @patch('core.llm.Path')
    @patch('core.llm.settings')
    def test_load_system_prompt_success(self, mock_settings, mock_path_cls):
        """Test successful system prompt loading."""
        mock_settings.SYSTEM_PROMPT_PATH = "/fake/path.txt"
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "Test prompt"
        mock_path_cls.return_value = mock_path

        result = _load_system_prompt()

        assert result == "Test prompt"

    @patch('core.llm.Path')
    @patch('core.llm.settings')
    def test_load_system_prompt_failure(self, mock_settings, mock_path_cls):
        """Test system prompt loading failure."""
        mock_settings.SYSTEM_PROMPT_PATH = "/fake/path.txt"
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.side_effect = Exception("File not found")
        mock_path_cls.return_value = mock_path

        result = _load_system_prompt()

        assert result == ""


class TestLLMResponse:
    @patch('core.llm._make_ollama_request')
    @patch('core.llm._load_system_prompt')
    def test_generate_reply_success(self, mock_load_prompt, mock_request):
        """Test successful LLM response generation."""
        mock_load_prompt.return_value = "System prompt"
        mock_request.return_value = "Test response"

        result = generate_reply("Hello")

        assert result == "Test response"
        mock_request.assert_called_once()

    @patch('core.llm._make_ollama_request')
    def test_generate_reply_empty_input(self, mock_request):
        """Test LLM response with empty input."""
        result = generate_reply("")

        assert result == ""
        mock_request.assert_not_called()

    @patch('core.llm._make_ollama_request')
    @patch('core.llm._load_system_prompt')
    def test_generate_reply_request_failure(self, mock_load_prompt, mock_request):
        """Test LLM response when request fails."""
        import requests
        from core.llm import LLMError
        
        mock_load_prompt.return_value = "System prompt"
        mock_request.side_effect = requests.RequestException("Connection failed")

        with pytest.raises(LLMError):
            generate_reply("Hello")


class TestBasicFunctionality:
    def test_app_creation(self):
        """Test that the FastAPI app can be imported."""
        from tts.server import app
        assert app is not None

    def test_constants(self):
        """Test that constants are set correctly."""
        from tts.server import DEFAULT_FALLBACK
        from core.config import get_settings
        
        settings = get_settings()
        assert DEFAULT_FALLBACK == "Sorry, can you repeat that?"
        assert settings.OLLAMA_TIMEOUT == 30