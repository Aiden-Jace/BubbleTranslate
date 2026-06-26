import hashlib
import random
import time
import uuid

import requests

from src import config

PROVIDERS = ("LLM", "DEEPL", "BAIDU", "YOUDAO", "GOOGLE")

DEEPL_LANGUAGE_MAPPING = {
    "": "自动检测",
    "BG": "保加利亚语",
    "CS": "捷克语",
    "DA": "丹麦语",
    "DE": "德语",
    "EL": "希腊语",
    "EN": "英语",
    "ES": "西班牙语",
    "ET": "爱沙尼亚语",
    "FI": "芬兰语",
    "FR": "法语",
    "HU": "匈牙利语",
    "ID": "印尼语",
    "IT": "意大利语",
    "JA": "日语",
    "KO": "韩语",
    "LT": "立陶宛语",
    "LV": "拉脱维亚语",
    "NB": "挪威语（书面挪威语）",
    "NL": "荷兰语",
    "PL": "波兰语",
    "PT": "葡萄牙语（混合所有葡萄牙语变体）",
    "RO": "罗马尼亚语",
    "RU": "俄语",
    "SK": "斯洛伐克语",
    "SL": "斯洛文尼亚语",
    "SV": "瑞典语",
    "TR": "土耳其语",
    "UK": "乌克兰语",
    "ZH": "中文",
}
DEEPL_LANGUAGE_CODES = {
    name: code for code, name in DEEPL_LANGUAGE_MAPPING.items()
}

LANGUAGE_CODES = {
    "自动检测": {
        "baidu": "auto",
        "youdao": "auto",
        "google": "auto",
    },
    "中文": {
        "baidu": "zh",
        "youdao": "zh-CHS",
        "google": "zh-CN",
    },
    "中文（简体）": {
        "baidu": "zh",
        "youdao": "zh-CHS",
        "google": "zh-CN",
    },
    "中文（繁体）": {
        "baidu": "cht",
        "youdao": "zh-CHT",
        "google": "zh-TW",
    },
    "英语": {"baidu": "en", "youdao": "en", "google": "en"},
    "保加利亚语": {"baidu": "bul", "youdao": "bg", "google": "bg"},
    "捷克语": {"baidu": "cs", "youdao": "cs", "google": "cs"},
    "丹麦语": {"baidu": "dan", "youdao": "da", "google": "da"},
    "希腊语": {"baidu": "el", "youdao": "el", "google": "el"},
    "爱沙尼亚语": {"baidu": "est", "youdao": "et", "google": "et"},
    "芬兰语": {"baidu": "fin", "youdao": "fi", "google": "fi"},
    "匈牙利语": {"baidu": "hu", "youdao": "hu", "google": "hu"},
    "日语": {"baidu": "jp", "youdao": "ja", "google": "ja"},
    "韩语": {"baidu": "kor", "youdao": "ko", "google": "ko"},
    "法语": {"baidu": "fra", "youdao": "fr", "google": "fr"},
    "德语": {"baidu": "de", "youdao": "de", "google": "de"},
    "西班牙语": {"baidu": "spa", "youdao": "es", "google": "es"},
    "俄语": {"baidu": "ru", "youdao": "ru", "google": "ru"},
    "葡萄牙语（混合所有葡萄牙语变体）": {
        "baidu": "pt",
        "youdao": "pt",
        "google": "pt",
    },
    "意大利语": {"baidu": "it", "youdao": "it", "google": "it"},
    "立陶宛语": {"baidu": "lt", "youdao": "lt", "google": "lt"},
    "拉脱维亚语": {"baidu": "lav", "youdao": "lv", "google": "lv"},
    "挪威语（书面挪威语）": {
        "baidu": "nor",
        "youdao": "no",
        "google": "no",
    },
    "荷兰语": {"baidu": "nl", "youdao": "nl", "google": "nl"},
    "波兰语": {"baidu": "pl", "youdao": "pl", "google": "pl"},
    "罗马尼亚语": {"baidu": "rom", "youdao": "ro", "google": "ro"},
    "斯洛伐克语": {"baidu": "slo", "youdao": "sk", "google": "sk"},
    "斯洛文尼亚语": {"baidu": "slo", "youdao": "sl", "google": "sl"},
    "瑞典语": {"baidu": "swe", "youdao": "sv", "google": "sv"},
    "土耳其语": {"baidu": "tr", "youdao": "tr", "google": "tr"},
    "乌克兰语": {"baidu": "ukr", "youdao": "uk", "google": "uk"},
    "越南语": {"baidu": "vie", "youdao": "vi", "google": "vi"},
    "印尼语": {"baidu": "id", "youdao": "id", "google": "id"},
    "泰语": {"baidu": "th", "youdao": "th", "google": "th"},
}

LLM_LANGUAGE_NAMES = [
    "中文",
    "中文（简体）",
    "中文（繁体）",
    "英语",
    "日语",
    "韩语",
    "法语",
    "德语",
    "西班牙语",
    "俄语",
    "葡萄牙语（混合所有葡萄牙语变体）",
    "意大利语",
    "荷兰语",
    "波兰语",
    "土耳其语",
    "乌克兰语",
    "越南语",
    "印尼语",
    "泰语",
    "保加利亚语",
    "捷克语",
    "丹麦语",
    "希腊语",
    "爱沙尼亚语",
    "芬兰语",
    "匈牙利语",
    "立陶宛语",
    "拉脱维亚语",
    "挪威语（书面挪威语）",
    "罗马尼亚语",
    "斯洛伐克语",
    "斯洛文尼亚语",
    "瑞典语",
]

BAIDU_LANGUAGE_NAMES = [
    name
    for name in LLM_LANGUAGE_NAMES
    if name not in {
        "中文（简体）",
        "挪威语（书面挪威语）",
        "斯洛文尼亚语",
    }
]

YOUDAO_LANGUAGE_NAMES = [
    "中文",
    "中文（简体）",
    "中文（繁体）",
    "英语",
    "日语",
    "韩语",
    "法语",
    "德语",
    "西班牙语",
    "俄语",
    "葡萄牙语（混合所有葡萄牙语变体）",
    "意大利语",
    "越南语",
    "印尼语",
]

GOOGLE_LANGUAGE_NAMES = list(LLM_LANGUAGE_NAMES)

PROVIDER_LANGUAGE_NAMES = {
    "LLM": LLM_LANGUAGE_NAMES,
    "BAIDU": BAIDU_LANGUAGE_NAMES,
    "YOUDAO": YOUDAO_LANGUAGE_NAMES,
    "GOOGLE": GOOGLE_LANGUAGE_NAMES,
}


class TranslationServiceError(RuntimeError):
    pass


def get_language_options(provider):
    provider = provider.upper()
    if provider == "LLM":
        targets = list(PROVIDER_LANGUAGE_NAMES["LLM"])
    elif provider == "DEEPL":
        targets = [
            name for code, name in DEEPL_LANGUAGE_MAPPING.items() if code
        ]
    else:
        targets = list(PROVIDER_LANGUAGE_NAMES.get(provider, GOOGLE_LANGUAGE_NAMES))

    return ["自动检测", *targets], targets


def normalize_language_selection(provider, source_language, target_language):
    source_languages, target_languages = get_language_options(provider)
    source = (
        source_language
        if source_language in source_languages
        else "自动检测"
    )
    default_target = "中文" if "中文" in target_languages else target_languages[0]
    target = (
        target_language
        if target_language in target_languages
        else default_target
    )
    return source, target


def translate(text, source_lang, target_lang, provider=None):
    provider = (provider or config.TRANSLATION_MODE).upper()
    if provider == "DEEPL":
        return _translate_deepl(text, source_lang, target_lang)
    if provider == "BAIDU":
        return _translate_baidu(text, source_lang, target_lang)
    if provider == "YOUDAO":
        return _translate_youdao(text, source_lang, target_lang)
    if provider == "GOOGLE":
        return _translate_google(text, source_lang, target_lang)
    raise TranslationServiceError(f"不支持的翻译服务: {provider}")


def _language_code(language, provider, default):
    return LANGUAGE_CODES.get(language, {}).get(provider, default)


def _translate_deepl(text, source_lang, target_lang):
    if not config.DEEPL_API_KEY.strip():
        raise TranslationServiceError("请先在设置中填写 DeepL API Key")

    payload = {
        "text": text,
        "target_lang": DEEPL_LANGUAGE_CODES.get(target_lang, "ZH"),
    }
    source_code = DEEPL_LANGUAGE_CODES.get(source_lang, "")
    if source_code:
        payload["source_lang"] = source_code

    response = requests.post(
        config.DEEPL_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"DeepL-Auth-Key {config.DEEPL_API_KEY}",
        },
        timeout=config.TIMEOUT,
    )
    response.raise_for_status()
    translations = response.json().get("translations", [])
    result = (
        str(translations[0].get("text", "")).strip()
        if translations
        else ""
    )
    if not result:
        raise TranslationServiceError("DeepL 未返回有效结果")
    return result


def _translate_baidu(text, source_lang, target_lang):
    app_id = config.BAIDU_APP_ID.strip()
    secret_key = config.BAIDU_SECRET_KEY.strip()
    if not app_id or not secret_key:
        raise TranslationServiceError("请先在设置中填写百度翻译 App ID 和密钥")

    salt = str(random.randint(32768, 65536))
    sign = hashlib.md5(
        f"{app_id}{text}{salt}{secret_key}".encode("utf-8")
    ).hexdigest()
    payload = {
        "q": text,
        "from": _language_code(source_lang, "baidu", "auto"),
        "to": _language_code(target_lang, "baidu", "zh"),
        "appid": app_id,
        "salt": salt,
        "sign": sign,
    }
    response = requests.post(
        config.BAIDU_API_URL,
        data=payload,
        timeout=config.TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if "error_code" in data:
        raise TranslationServiceError(
            f"百度翻译错误 {data['error_code']}: {data.get('error_msg', '未知错误')}"
        )
    translations = data.get("trans_result", [])
    result = "\n".join(str(item.get("dst", "")) for item in translations).strip()
    if not result:
        raise TranslationServiceError("百度翻译未返回有效结果")
    return result


def _youdao_input(text):
    if len(text) <= 20:
        return text
    return f"{text[:10]}{len(text)}{text[-10:]}"


def _translate_youdao(text, source_lang, target_lang):
    app_key = config.YOUDAO_APP_KEY.strip()
    app_secret = config.YOUDAO_APP_SECRET.strip()
    if not app_key or not app_secret:
        raise TranslationServiceError("请先在设置中填写有道翻译应用 ID 和应用密钥")

    salt = str(uuid.uuid4())
    curtime = str(int(time.time()))
    sign_text = f"{app_key}{_youdao_input(text)}{salt}{curtime}{app_secret}"
    payload = {
        "q": text,
        "from": _language_code(source_lang, "youdao", "auto"),
        "to": _language_code(target_lang, "youdao", "zh-CHS"),
        "appKey": app_key,
        "salt": salt,
        "sign": hashlib.sha256(sign_text.encode("utf-8")).hexdigest(),
        "signType": "v3",
        "curtime": curtime,
    }
    response = requests.post(
        config.YOUDAO_API_URL,
        data=payload,
        timeout=config.TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if str(data.get("errorCode", "")) != "0":
        raise TranslationServiceError(
            f"有道翻译错误: {data.get('errorCode', '未知错误')}"
        )
    translations = data.get("translation", [])
    result = "\n".join(str(item) for item in translations).strip()
    if not result:
        raise TranslationServiceError("有道翻译未返回有效结果")
    return result


def _translate_google(text, source_lang, target_lang):
    params = {
        "client": "gtx",
        "sl": _language_code(source_lang, "google", "auto"),
        "tl": _language_code(target_lang, "google", "zh-CN"),
        "dt": "t",
        "q": text,
    }
    response = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params=params,
        timeout=config.TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    segments = data[0] if isinstance(data, list) and data else []
    result = "".join(
        str(segment[0])
        for segment in segments
        if isinstance(segment, list) and segment and segment[0]
    ).strip()
    if not result:
        raise TranslationServiceError("Google 翻译未返回有效结果")
    return result
