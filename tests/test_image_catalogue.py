"""Check quality selection through the Telegram backend and HTTP request body."""

from base64 import b64encode
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from elevenbot import interaction
from elevenbot.core import Rejected
from elevenbot.discovery import SnapshotStore, snapshot
from elevenbot.telegram import TelegramApp
from test_image_validation import encoded_image
from test_ui import Bot, event


@pytest.mark.parametrize(("model_id", "quality"), [
    ("flux-schnell", None),
    ("gpt-image-2.5-sunburst", None),
    ("gpt-image-2.5-sunburst", "high"),
])
async def test_gpt_image_quality_reaches_provider(funded_env, tmp_path, monkeypatch, quality, model_id, manual_tariff):
    pool,base,_,user=funded_env
    path = tmp_path / "catalogue.json"
    operation = "images.generate"
    model = {
        "id": model_id,
        "title": model_id,
        "provider": "clodex",
        "availability": "key_available",
        "operations": [operation],
        "protocols": ["image-generation"],
    }
    catalogue = snapshot([model])
    SnapshotStore(path).write(catalogue)
    cfg = replace(
        base, access_mode="private", admin_ids=(100,), catalogue_path=str(path), interaction_limit=3,
        interaction_mode="live", interaction_pairs=(f"{operation}:{model_id}",),
        public_catalogue_models=(f"image:{model_id}",), clodex_key="fixture-only",
    )
    bot = Bot()
    bot.send_photo = AsyncMock()
    app = TelegramApp(pool, cfg, bot)
    params={'n':1} if quality is None else {'n':1,'quality':quality}
    await manual_tariff(app,user,model_id,operation,params)
    await app.pricing.set_rule(user,100,'clodex',model_id,'percent','25')
    await app.show_store_model(100, catalogue, "image", 0, 0)
    _, markup = bot.sent[-1]
    prefix = f"srun:{catalogue['version']}:image:0:0"
    route = prefix if quality is None else f"{prefix}:high"
    actions = {button.callback_data: button for row in markup.inline_keyboard for button in row}
    assert (f"{prefix}:high" in actions) == (model_id == "gpt-image-2.5-sunburst")
    action = actions[route]
    await app.callback(user, 100, action.callback_data)
    context = await app.svc.aggregate_context(user)
    assert context.get("quality") == quality
    if quality is not None:
        assert "Качество: high" in bot.sent[-1][0]

    requests = []
    png = encoded_image("PNG")

    def respond(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/images/generations"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"b64_json": b64encode(png).decode("ascii")}]})

    execute = interaction.execute
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        async def execute_against_stub(*args, **kwargs):
            return await execute(*args, **kwargs, client=client)

        monkeypatch.setattr(interaction, "execute", execute_against_stub)
        await app.interaction_input(user, 100, event("Баннер"), context)
        assert not requests
        assert 'Ручная себестоимость: 100 токенов DarkFlow | Gen' in bot.sent[-1][0]
        assert "Наценка: 25" in bot.sent[-1][0]
        assert "Оценка: 125" in bot.sent[-1][0]
        confirm=bot.sent[-1][1].inline_keyboard[0][0].callback_data
        await app.callback(user,100,confirm,request_id=2)
        with pytest.raises(Rejected):
            await app.callback(user,100,confirm,request_id=3)

    expected = {"model": model_id, "prompt": "Баннер", "n": 1, "response_format": "b64_json"}
    if quality is not None:
        expected["quality"] = quality
    assert requests == [expected]
    bot.send_photo.assert_awaited_once()
    assert bot.send_photo.await_args.args[1].data==png
    await app.callback(user,100,'history:0')
    await app.callback(user,100,bot.sent[-1][1].inline_keyboard[0][0].callback_data)
    assert bot.send_photo.await_count==2 and bot.send_photo.await_args.args[1].data==png

async def test_image_menu_blocks_old_launches_and_keeps_saved_work(env, tmp_path, monkeypatch):
    pool, config, service, user = env
    operation = "images.generate"
    titles = {
        "flux-schnell": "FLUX Schnell",
        "gpt-image-2.5-sunburst": "Sunburst",
        "nano-banana-2": "Nano Banana 2",
        "gpt-image-2": "GPT Image 2",
    }
    models = [
        {"id": ident, "title": title, "provider": "clodex", "availability": "key_available",
         "operations": [operation], "protocols": ["image-generation"]}
        for ident, title in titles.items()
    ]
    catalogue = snapshot(models)
    version = catalogue["version"]
    path = tmp_path / "catalogue.json"
    SnapshotStore(path).write(catalogue)
    config = replace(
        config, access_mode="private", admin_ids=(100,), catalogue_path=str(path),
        interaction_mode="live", interaction_pairs=tuple(f"{operation}:{ident}" for ident in titles),
        public_catalogue_models=tuple(f"image:{ident}" for ident in titles), clodex_key="fixture-only",
        interaction_limit=1,
    )
    execute = AsyncMock(side_effect=AssertionError("No generation should be attempted"))
    monkeypatch.setattr(interaction, "execute", execute)
    bot = Bot()
    bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=20))
    app = TelegramApp(pool, config, bot)
    await app.callback(user, 100, "store")
    _, menu = bot.sent[-1]
    image_section, = [b for row in menu.inline_keyboard for b in row if b.callback_data == "slist:current:image:0"]
    await app.callback(user, 100, image_section.callback_data)
    _, menu = bot.sent[-1]
    assert [b.text for row in menu.inline_keyboard for b in row if b.callback_data.startswith("smodel:")] == [
        "FLUX Schnell", "Sunburst",
    ]

    for index, model in enumerate(models):
        if index < 2:
            continue
        for route in (f"srun:{version}:image:0:{index}", f"runmodel:{version}:{index}:{operation}"):
            with pytest.raises(Rejected):
                await app.callback(user, 100, route)
        with pytest.raises(Rejected):
            await app.interaction_input(user, 100, event("Old prompt"), {
                "interaction": operation, "model_id": model["id"], "history": [],
            })
    execute.assert_not_awaited()
    assert await pool.fetchval("SELECT count(*) FROM interaction_attempts") == 0

    png = encoded_image("PNG")
    work_id = await service.save_image_work(
        user, 1001, "nano-banana-2", "Previous work", interaction.image_result(png),
    )
    await app.callback(user, 100, "history:0")
    _, menu = bot.sent[-1]
    open_button, = [b for row in menu.inline_keyboard for b in row if b.callback_data == f"image:{work_id}"]
    await app.callback(user, 100, open_button.callback_data)
    bot.send_photo.assert_awaited_once()
    assert bot.send_photo.await_args.args[1].data == png
    execute.assert_not_awaited()
