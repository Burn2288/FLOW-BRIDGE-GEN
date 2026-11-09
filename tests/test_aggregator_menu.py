from dataclasses import replace

import pytest

from elevenbot.aggregate import make_snapshot
from elevenbot.anymodel import model_store
from elevenbot.core import Rejected
from elevenbot.discovery import SnapshotStore
from elevenbot.pricing import NoProviderPrice
from elevenbot.telegram import TelegramApp
from test_anymodel import routes
from test_ui import Bot, event


class NoPrice:
    async def cost(self, request):
        raise NoProviderPrice()


def model(provider, model_id, operation, protocol):
    return dict(provider=provider, id=model_id, title=model_id, availability='key_available',
                operations=[operation], protocols=[protocol])


async def test_admin_aggregator_menu_routes_and_permissions(env, tmp_path):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),catalogue_path=str(tmp_path/'models.json'),
                anymodel_test_enabled=True,interaction_mode='live',video_pilot=True)
    clodex=[model('clodex','clodex-video/veo-3.1','video','openai-video'),
            model('clodex','flux-schnell','images.generate','image-generation'),
            model('clodex','fixture/unapproved','chat','openai')]
    clodex_functions=[dict(provider='clodex',id='chat',title='Текстовый диалог',
                           method='POST',path='/v1/chat/completions',request_preview_supported=False)]
    SnapshotStore(cfg.catalogue_path).write(make_snapshot(clodex,clodex_functions,[{
        'provider':'clodex','scope':'key_available',
    }]))
    anymodel=[model('anymodel','anymedia/fibo-2','images.generate','image-generation'),
              model('anymodel','ds/deepseek-v4-flash-vision','chat','openai')]
    model_store(cfg).write(make_snapshot(anymodel,[],[{'provider':'anymodel','scope':'key_available'}]))
    await pool.execute("DELETE FROM approved_models WHERE model_id IN ('xai/grok-imagine-video-1.5','fish-farm/s2.1-pro-free')")
    bot=Bot()
    app=TelegramApp(pool,cfg,bot)
    app.pricing.adapters.update(clodex=NoPrice(),anymodel=NoPrice())

    async def click(label):
        await app.handle(event(callback=routes(bot)[label]))

    await app.handle(event('/start'))
    welcome=await app.svc.welcome_message(100)
    await app.handle(event('🌐 Агрегаторы'))
    chooser=bot.sent[-1]
    animation=bot.animations[-1].data
    for command in ('/menu','/menu@FixtureBot'):
        await click('AnyModel')
        await click('🎆 Генерировать изображение')
        await click('FIBO 2')
        card=(await app.navigation.read(100)).active_id
        await app.handle(event(command))
        assert bot.sent[-1]==chooser and bot.animations[-1].data==animation
        assert card in bot.deleted and welcome not in bot.deleted
        assert await app.svc.welcome_message(100)==welcome

    expected={
        'CLODEX':['🎬 Генерировать видео','🎆 Генерировать изображение'],
        'AnyModel':['🎆 Генерировать изображение','💬 Классический чат'],
    }
    for title,working in expected.items():
        key=title.lower()
        await app.handle(event('🌐 Агрегаторы'))
        await click(title)
        home=dict(routes(bot))
        assert list(home)==working+['📁 Мои работы','⚙️ Управление агрегатором','← Агрегаторы']
        assert home['📁 Мои работы']=='history:0'
        assert bot.sent[-1][0]==title+'\nВыберите, что хотите сделать.'
        for action in working:
            await app.handle(event(callback=home[action]))
            assert 'пока нет' not in bot.sent[-1][0] and 'fixture/unapproved' not in routes(bot)
            origin=dict(routes(bot))
            for model_label in ('Veo 3.1','FIBO 2','ds/deepseek-v4-flash-vision','flux-schnell'):
                if model_label not in origin:
                    continue
                await click(model_label)
                assert [label for label in routes(bot) if label.startswith('←')]==['← К списку моделей']
                await click('← К списку моделей')
                assert routes(bot)==origin
        await app.handle(event(callback=home['⚙️ Управление агрегатором']))
        management=dict(routes(bot))
        options=['Наши модели','Курс и калькулятор','Все модели']
        if key=='clodex':options.append('Функции и возможности')
        assert list(management)==options+['← К агрегатору']
        assert 'операций API:' in bot.sent[-1][0]
        await click('Наши модели')
        assert bot.sent[-1][0].startswith(f'Наши модели · {title.upper()}')
        assert routes(bot)['← К управлению']==f'agmanage:{key}'
        await click('← К управлению')
        await click('Курс и калькулятор')
        assert bot.sent[-1][0]==f'Курс и калькулятор · {title}'
        await click('← К управлению')
        await click('Все модели')
        assert routes(bot)['← Назад']==f'agmanage:{key}'
        await click('← Назад')
        if key=='clodex':
            await click('Функции и возможности')
            assert 'Текстовый диалог' in routes(bot)
            await click('← К управлению')
        await click('← К агрегатору')
        assert routes(bot)==home
        await click('← Агрегаторы')
        assert title in routes(bot)

    await app.handle(event('/revoke clodex flux-schnell images.generate'))
    await app.handle(event(callback='agroot:clodex'))
    assert '🎆 Генерировать изображение' not in routes(bot)
    guest=await app.svc.identity(101)
    await app.svc.accept(guest)
    for key in ('clodex','anymodel'):
        for data in (f'agmanage:{key}',f'ours:{key}:0',f'rates:{key}'):
            with pytest.raises(Rejected,match='только администратору'):
                await app.callback(guest,101,data)
    assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==0
