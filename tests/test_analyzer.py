import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import analyzer


class AnalyzerTests(unittest.TestCase):
    @patch("analyzer.OpenAI")
    def test_analysis_uses_responses_api_and_returns_output_text(self, openai):
        client = openai.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(output_text="A grounded summary.")

        result = analyzer.analyze_scraped_data("extracted text", api_key="test-key", model="test-model")

        self.assertEqual(result, "A grounded summary.")
        openai.assert_called_once_with(api_key="test-key", timeout=30, max_retries=1)
        client.responses.create.assert_called_once()
        request = client.responses.create.call_args.kwargs
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(request["input"], "extracted text")
        self.assertEqual(request["store"], False)

    @patch("analyzer.OpenAI")
    def test_analysis_truncates_input(self, openai):
        client = openai.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(output_text="summary")

        analyzer.analyze_scraped_data("x" * (analyzer.MAX_ANALYSIS_CHARS + 20), api_key="test-key")

        request = client.responses.create.call_args.kwargs
        self.assertEqual(len(request["input"]), analyzer.MAX_ANALYSIS_CHARS)

    def test_analysis_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            analyzer.analyze_scraped_data("text")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("builtins.input", side_effect=["What is the title?", "exit"])
    @patch("builtins.print")
    @patch("analyzer.OpenAI")
    def test_cli_chat_sends_each_question_once(self, openai, _print, _input):
        client = openai.return_value
        client.responses.create.return_value = SimpleNamespace(output_text="The title is Example.")

        analyzer.start_chat_with_data("Page title: Example")

        openai.assert_called_once_with(api_key="test-key", timeout=30, max_retries=1)
        sent_input = client.responses.create.call_args.kwargs["input"]
        self.assertEqual(len(sent_input), 2)
        self.assertEqual(sent_input[0]["content"], "Webpage extraction:\nPage title: Example")
        self.assertEqual(sent_input[1], {"role": "user", "content": "What is the title?"})
        client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
