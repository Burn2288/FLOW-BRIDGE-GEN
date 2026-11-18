"""Normalized speech metadata; source identifiers and billing evidence remain distinct."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SpeechCapability:
    provider: str
    model_id: str | None
    voice_id: str | None
    title: str
    language: str | None
    available: bool
    availability_scope: str
    audio_format: str
    counting_unit: str | None
    price_available: bool | None
    price_source: str | None

    def as_dict(self):
        return asdict(self)


def source_language(record):
    value = record.get('lang')
    return value if isinstance(value, str) and 0 < len(value) <= 35 and value.isascii() and all(c.isalnum() or c == '-' for c in value) else None


def anymodel_voice(record, *, model_id, title, voice_id=None, cost=None):
    # The authenticated catalogue proves presence, not a usable account price.
    return SpeechCapability('anymodel', model_id, voice_id, title, source_language(record),
                            True, 'catalogue_only', 'audio/mpeg', 'utf16_code_units',
                            True if cost is not None else None,
                            cost.source if cost is not None else None)


def legacy_voice(cfg, record):
    # Service.quote uses len(text), i.e. Python Unicode code points, and the
    # configured retail_per_char. This describes legacy, not provider billing.
    return SpeechCapability('clodex' if cfg.mode == 'clodex' else 'mock',
                            cfg.clodex_model if cfg.mode == 'clodex' and cfg.clodex_model else None,
                            record['id'], record['name'], source_language(record),
                            bool(cfg.generation_enabled), 'generation_config_only', 'audio/mpeg', 'unicode_codepoints',
                            True, 'legacy_config.retail_per_char')


def clodex_tts_voice(model_id, record, *, available, price=None):
    # The model's task tariff is an approved manual quote, not a public price.
    return SpeechCapability('clodex', model_id, record['id'], record['name'],
                            source_language(record), bool(available), 'generation_config_only', 'audio/mpeg',
                            None, True if price is not None else None,
                            price.get('source') if price is not None else None)


def utf16_units(text):
    return len(text.encode('utf-16-le')) // 2
