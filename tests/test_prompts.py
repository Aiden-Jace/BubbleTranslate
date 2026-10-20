import configparser
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src import config
from src.core.llm_engine import LLMTextWorker, LLMVisionWorker, _translation_prompt


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'config.ini'
        self.parser = configparser.ConfigParser(interpolation=None)
        self.enterContext(patch.object(config, 'CONFIG_FILE', str(self.path)))
        self.enterContext(patch.object(config, '_parser', self.parser))

    def test_new_config_contains_editable_prompts(self):
        config.load_config()
        saved = configparser.ConfigParser(interpolation=None)
        saved.read(self.path, encoding='utf-8')
        self.assertEqual(dict(saved['Prompts']), dict(self.parser['Prompts']))
        self.assertEqual(saved.get('Prompts', 'OCR_USER'), 'OCR:')

    def test_existing_config_preserves_custom_values_and_adds_missing_prompts(self):
        self.path.write_text(
            '[API]\nAPI_KEY = existing-key\n[Prompts]\n'
            'TRANSLATION_SYSTEM = Translate 100% into {target_language}\n',
            encoding='utf-8',
        )
        config.load_config()
        saved = configparser.ConfigParser(interpolation=None)
        saved.read(self.path, encoding='utf-8')
        self.assertEqual(saved.get('API', 'API_KEY'), 'existing-key')
        self.assertEqual(saved.get('Prompts', 'VLM_SYSTEM'), config.defaults['Prompts']['VLM_SYSTEM'])
        self.assertEqual(_translation_prompt('English', '中文'), 'Translate 100% into 中文')

    def test_old_config_without_prompts_is_migrated(self):
        self.path.write_text('[Translation]\nMODE = GOOGLE\n', encoding='utf-8')
        config.load_config()
        self.assertEqual(self.parser.get('Translation', 'MODE'), 'GOOGLE')
        self.assertEqual(len(self.parser['Prompts']), len(config.defaults['Prompts']))
        self.assertIn('[Prompts]', self.path.read_text(encoding='utf-8'))

    def test_multiline_percent_and_json_survive_save_and_reload(self):
        config.load_config()
        template = 'Translate {source_language} to {target_language}, 100%.\n{"text": "..."} {unknown}'
        config.update_config('Prompts', 'TRANSLATION_SYSTEM', template)
        self.parser.clear()
        config.load_config()
        self.assertEqual(
            _translation_prompt('English', '中文'),
            'Translate English to 中文, 100%.\n{"text": "..."} {unknown}',
        )

    def test_ocr_context_only_applies_to_screenshot_translation(self):
        config.load_config()
        config.update_configs([
            ('Prompts', 'TRANSLATION_SYSTEM', '{ocr_context}{source_language} -> {target_language}'),
            ('Prompts', 'OCR_CONTEXT', 'OCR ({source_language}): '),
        ])
        self.assertEqual(_translation_prompt('English', '中文'), 'English -> 中文')
        self.assertEqual(_translation_prompt('English', '中文', True), 'OCR (English): English -> 中文')
        config.update_config('Prompts', 'OCR_CONTEXT', '')
        self.assertEqual(_translation_prompt('English', '中文', True), 'English -> 中文')

    def test_missing_or_blank_prompt_uses_default(self):
        expected = config.defaults['Prompts']['TRANSLATION_SYSTEM'].replace('{ocr_context}', '').replace(
            '{source_language}', 'English',
        ).replace('{target_language}', '中文')
        self.assertEqual(_translation_prompt('English', '中文'), expected)
        self.parser['Prompts'] = {'TRANSLATION_SYSTEM': '   '}
        self.assertEqual(_translation_prompt('English', '中文'), expected)

    def test_workers_send_custom_prompts_in_request_payloads(self):
        config.load_config()
        config.update_configs([
            ('Prompts', 'TRANSLATION_SYSTEM', 'Translate {source_language} to {target_language}.'),
            ('Prompts', 'VLM_SYSTEM', 'Read {source_language}.'),
            ('Prompts', 'VLM_USER', 'Transcribe, then translate to {target_language}.'),
            ('Prompts', 'OCR_USER', 'Extract {source_language}.'),
        ])
        text = LLMTextWorker('hello', source_lang='English', target_lang='中文')
        vision = LLMVisionWorker(Image.new('RGB', (2, 2)), source_lang='English', target_lang='中文')
        with patch('src.core.llm_engine.openai_client.request_chat_completion', return_value='hello') as request:
            text._request_llm_translation('hello')
            messages = request.call_args.args[2]['messages']
            self.assertEqual(messages[0]['content'], 'Translate English to 中文.')
            self.assertEqual(messages[1]['content'], 'hello')

            vision._recognize_with_vlm('image-data')
            messages = request.call_args.args[2]['messages']
            self.assertEqual(messages[0]['content'], 'Read English.')
            self.assertEqual(messages[1]['content'][1]['text'], 'Transcribe, then translate to 中文.')
            self.assertEqual(messages[1]['content'][0]['image_url']['url'], 'data:image/png;base64,image-data')

            vision._recognize_with_ocr('image-data')
            messages = request.call_args.args[2]['messages']
            self.assertEqual(messages[0]['content'][1]['text'], 'Extract English.')


if __name__ == '__main__':
    unittest.main()
