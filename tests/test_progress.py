import asyncio

import pytest

from elevenbot.core import Rejected
from elevenbot.progress import ReportedTaskError
from test_ui import app, event


async def test_parallel_statuses_survive_menu_and_finish_independently():
    gateway, bot = app()
    await gateway.svc.accept(gateway.svc.u)
    await gateway.handle(event('/start'))
    release = asyncio.Event()
    ready = asyncio.Queue()
    edited = {}
    edit = bot.edit_message_text

    async def observe(text, *, chat_id, message_id, reply_markup=None):
        edited[message_id] = text
        return await edit(text,chat_id=chat_id,message_id=message_id,reply_markup=reply_markup)

    bot.edit_message_text = observe

    async def run(model, operation, fails):
        async with gateway.progress.track(100,model,operation):
            await ready.put((model,100+len(bot.sent)))
            await release.wait()
            if fails:
                raise Rejected('Провайдер отклонил запрос.')

    image = asyncio.create_task(run('FLUX','images.generate',False))
    chat = asyncio.create_task(run('DeepSeek','chat',True))
    try:
        ids = dict([await ready.get(),await ready.get()])
        await gateway.handle(event('Открыть каталог'))
        await gateway.handle(event(callback='home'))
        assert not set(ids.values()).intersection(bot.deleted)
    finally:
        release.set()
        results = await asyncio.gather(image,chat,return_exceptions=True)
    assert results[0] is None
    assert isinstance(results[1],ReportedTaskError)
    assert edited[ids['FLUX']]=='✅ FLUX · Готово.'
    assert edited[ids['DeepSeek']]=='⚠️ DeepSeek · Провайдер отклонил запрос.'


@pytest.mark.parametrize('progress,expected',[(32,32),(True,None),(-2,None),(101,None)])
def test_video_uses_only_reported_valid_percent(progress,expected):
    from elevenbot.video import video_status_detail
    assert video_status_detail({'status':'in_progress','progress':progress})==('processing',expected)
