import types
import unittest

from core.openai_compat import extract_text_from_openai_response


class TestOpenAICompat(unittest.TestCase):
    def test_extract_from_chat_choices(self):
        msg = types.SimpleNamespace(content='{"questions": []}')
        choice = types.SimpleNamespace(message=msg)
        response = types.SimpleNamespace(choices=[choice])
        self.assertEqual(extract_text_from_openai_response(response), '{"questions": []}')

    def test_extract_from_responses_output_text(self):
        response = types.SimpleNamespace(output_text='{"questions": [{"stem": "x"}]}')
        self.assertIn('questions', extract_text_from_openai_response(response))

    def test_extract_raises_for_unknown_shape(self):
        response = types.SimpleNamespace()
        with self.assertRaises(RuntimeError):
            extract_text_from_openai_response(response)


if __name__ == '__main__':
    unittest.main()
