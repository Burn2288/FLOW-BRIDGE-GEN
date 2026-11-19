"""VO-01 normalization and regression using existing speech execution."""
from dataclasses import replace
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from elevenbot.anymodel import AnyModelError
from elevenbot.anymodel_pricing import AnyModelPricing, tariff
from elevenbot.anymodel_speech import FISH, FISH_TITLE, SpeechPilot
from elevenbot.config import Config
from elevenbot.core import Rejected
from elevenbot.pricing import PriceUnavailable, ProviderCost, Request
from elevenbot.providers import catalog
from elevenbot.speech_capabilities import anymodel_voice, clodex_tts_voice, utf16_units
from test_anymodel_speech import test_speech_confirmation_and_library as run_speech_scenario
from test_anymodel_speech import test_voice_without_price_and_disabled_pilot as run_no_price_scenario


def test_source_ids_language_and_price_evidence_are_not_inferred():
    voice = {'model':'anyvoice/builtin-7', 'name':'Спокойный', 'lang':'ru'}
    desc = anymodel_voice(voice, model_id=voice['model'], voice_id=voice['model'], title=voice['name'])
    assert (desc.provider, desc.model_id, desc.voice_id, desc.language) == ('anymodel', voice['model'], voice['model'], 'ru')
    assert desc.available and desc.availability_scope == 'catalogue_only'
    assert desc.audio_format == 'audio/mpeg' and desc.counting_unit == 'utf16_code_units'
    assert desc.price_available is None and desc.price_source is None
    unknown = anymodel_voice({'name':'English'}, model_id='anyvoice/x', voice_id='anyvoice/x', title='English')
    assert unknown.language is None
    cost = ProviderCost(Decimal('4'), 'anymodel_balance_token', False, '/v1/models/info · billing · fixture', 'units')
    assert anymodel_voice(voice, model_id=voice['model'], voice_id=voice['model'], title=voice['name'], cost=cost).price_source == cost.source
    clodex = clodex_tts_voice('eleven_v4', {'id':'source-voice','name':'Voice'}, available=True)
    assert clodex.voice_id == 'source-voice' and clodex.model_id == 'eleven_v4'
    assert clodex.price_available is None and clodex.counting_unit is None
    clodex_quoted = clodex_tts_voice('eleven_v4', {'id':'source-voice','name':'Voice'}, available=True,
                                     price={'source':'manual:fixture'})
    assert clodex_quoted.price_source == 'manual:fixture' and clodex_quoted.price_available is True
    assert clodex_tts_voice('eleven_v4', {'id':'source-voice','name':'Voice'}, available=True,
                            price={'source':'public catalogue'}).price_available is None
    legacy = catalog(Config(mode='mock', generation_enabled=True))[0]
    assert legacy['id'] == 'demo' and legacy['speech_capability']['voice_id'] == 'demo'
    assert legacy['speech_capability']['counting_unit'] == 'unicode_codepoints'
    assert legacy['speech_capability']['price_source'] == 'legacy_config.retail_per_char'


async def test_actual_speech_selection_returns_source_descriptions():
    api = AsyncMock()
    api.anyvoice_voices.return_value = {'anyvoice/v': {'model':'anyvoice/v','name':'Voice','lang':'en'}}
    pilot = SpeechPilot(None, Config(), api=api)
    pilot.catalogue = AsyncMock(return_value=[{'id':FISH}])
    fish = await pilot.describe(FISH)
    assert fish.model_id == FISH and fish.voice_id is None and fish.title == FISH_TITLE and fish.language is None
    voice = await pilot.describe('anyvoice/v')
    assert voice.voice_id == 'anyvoice/v' and voice.language == 'en'
    with pytest.raises(AnyModelError) as error:
        await pilot.describe('anyvoice/absent')
    assert error.value.code == 'speech_voice'


async def test_utf16_non_bmp_and_surrogate_rejected_before_price_fetch():
    assert utf16_units('Я😀') == 3
    req = Request('anymodel', FISH, 'audio.speech', 'Fish', 'Я😀')
    metadata = {'id':FISH, 'endpoint':'/v1/audio/speech',
                'billing':{'unit':'character','base_tokens':50,'coefficient':{'output':1}}}
    result = tariff(metadata, req)
    assert result.amount == 150 and result.details == '3 ед. UTF-16'
    api = AsyncMock()
    pricing = AnyModelPricing('fixture', api=api)
    with pytest.raises(PriceUnavailable):
        await pricing.cost(replace(req, prompt='invalid\ud800'))
    api.request.assert_not_awaited()


async def test_legacy_quote_preserves_python_character_pricing(env):
    pool, cfg, svc, user = env
    quote, price = await svc.quote(user, 'Я😀', 'demo')
    assert price == 2 * cfg.retail_per_char
    assert await pool.fetchval('SELECT price FROM quotes WHERE id=$1', quote) == price


async def test_existing_mock_speech_bills_once_and_reopens(funded_env):
    pool, _, _, user = funded_env
    await run_speech_scenario(funded_env, FISH, 'success')
    quote = await pool.fetchrow("SELECT id,price::text FROM task_price_quotes WHERE operation='audio.speech' AND state='accepted'")
    assert quote is not None
    import json
    assert json.loads(quote['price'])['total'] == '250'
    rows = await pool.fetch('SELECT kind FROM ledger WHERE task_quote_id=$1 ORDER BY kind', quote['id'])
    assert [row['kind'] for row in rows] == ['task_capture', 'task_reserve']
    assert await pool.fetchval('SELECT audio IS NOT NULL FROM task_speech_works WHERE id=$1 AND user_id=$2', quote['id'], user)


async def test_no_price_does_not_reserve_or_submit(funded_env):
    pool, _, _, _ = funded_env
    await run_no_price_scenario(funded_env)
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='task_reserve'") == 0


async def test_legacy_unknown_voice_cannot_create_reserve(env):
    pool, _, svc, user = env
    with pytest.raises(Rejected):
        await svc.quote(user, 'Текст', 'not-a-voice')
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind IN ('reserve','task_reserve')") == 0
