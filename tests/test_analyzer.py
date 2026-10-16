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
    def test_ask_page_sends_page_history_and_question(self, openai):
        client = openai.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(
            output_text='{"answer": "It is about cats.", "questions": ["Who wrote it?", "  ", "When?"]}'
        )
        history = [{"role": "user", "content": "First?"}, {"role": "assistant", "content": "First answer."}]

        result = analyzer.ask_page("Cats page", history, "What is it about?", api_key="test-key", model="test-model")

        self.assertEqual(result, {"answer": "It is about cats.", "questions": ["Who wrote it?", "When?"]})
        openai.assert_called_once_with(api_key="test-key", timeout=30, max_retries=0)
        request = client.responses.create.call_args.kwargs
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(request["input"][0], {"role": "user", "content": "Page content:\nCats page"})
        self.assertEqual(request["input"][1:3], history)
        self.assertEqual(request["input"][-1], {"role": "user", "content": "What is it about?"})
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertEqual(request["store"], False)

    @patch("analyzer.OpenAI")
    def test_ask_page_without_question_asks_for_overview_and_truncates_page(self, openai):
        client = openai.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(output_text='{"answer": "Overview.", "questions": []}')

        analyzer.ask_page("x" * (analyzer.MAX_ANALYSIS_CHARS + 20), [], api_key="test-key")

        request = client.responses.create.call_args.kwargs
        self.assertEqual(len(request["input"][0]["content"]), len("Page content:\n") + analyzer.MAX_ANALYSIS_CHARS)
        self.assertEqual(request["input"][-1]["content"], analyzer.OVERVIEW_PROMPT)

    @patch("analyzer.OpenAI")
    def test_ask_page_leaves_room_for_reasoning_models(self, openai):
        # gpt-5-mini spent ~450 of a 500-token budget on reasoning and returned no text.
        client = openai.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(output_text='{"answer": "a", "questions": []}')

        analyzer.ask_page("text", [], "q", api_key="test-key")

        request = client.responses.create.call_args.kwargs
        self.assertGreaterEqual(request["max_output_tokens"], 2000)
        self.assertEqual(request["reasoning"], {"effort": "low"})

    @patch("analyzer.OpenAI")
    def test_ask_page_explains_an_empty_truncated_response(self, openai):
        client = openai.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(
            output_text="", status="incomplete", incomplete_details=SimpleNamespace(reason="max_output_tokens")
        )

        result = analyzer.ask_page("text", [], "q", api_key="test-key")

        self.assertIn("ran out of output tokens", result["answer"])
        self.assertEqual(result["questions"], [])

    def test_ask_page_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            analyzer.ask_page("text", [])

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
