import json, os

LOCALES_DIR = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'locales')
SUPPORTED = ['en', 'pt', 'es', 'ja']

def _load(lang):
    with open(os.path.join(LOCALES_DIR, f'{lang}.json'), encoding='utf-8') as f:
        return json.load(f)

def test_locale_files_exist():
    for lang in SUPPORTED:
        path = os.path.join(LOCALES_DIR, f'{lang}.json')
        assert os.path.exists(path), f'Missing locale file: {lang}.json'

def test_locale_keys_consistent():
    en_keys = set(_load('en').keys())
    for lang in ['pt', 'es', 'ja']:
        data = _load(lang)
        missing = en_keys - set(data.keys())
        extra   = set(data.keys()) - en_keys
        assert not missing, f'{lang}.json missing keys: {missing}'
        assert not extra,   f'{lang}.json extra keys: {extra}'

def test_locale_values_are_strings():
    for lang in SUPPORTED:
        data = _load(lang)
        for key, val in data.items():
            assert isinstance(val, str), f'{lang}.json key {key!r} is not a string'
