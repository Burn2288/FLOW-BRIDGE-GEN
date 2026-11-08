"""Execution contracts for the existing AnyModel and CLODEX pilots."""

import asyncio
from decimal import Decimal

from .anymodel import AnyModelError, IMAGE_OP, can_view
from .anymodel_speech import validate_mp3
from .core import Rejected
from .task_launch import Outcome


class AnyModelExecution:
    def __init__(self,app,chat_factory):
        self.app,self.chat_factory = app,chat_factory

    def background(self,operation):
        return {'video':'video',IMAGE_OP:'image'}.get(operation)

    async def prepare(self,conn,user,external,quote,update_id):
        app,req = self.app,quote.request
        allowed = {
            'video':app.anymodel_video.enabled(),
            'audio.speech':app.anymodel_speech.enabled(external),
            IMAGE_OP:app.cfg.anymodel_image_live and req.params.get('n',1)==1,
            'chat':app.cfg.anymodel_chat_live,
        }
        if not can_view(app.cfg,external) or not allowed.get(req.operation):
            raise Rejected('AnyModel: тестовый запуск выключен.')
        if req.operation=='video':
            await app.anymodel_video.prepare(conn,user,quote)
        elif req.operation==IMAGE_OP:
            await app.anymodel_images.prepare(conn,user,update_id,req.prompt,req.model)
        elif req.operation=='audio.speech':
            await app.anymodel_speech.prepare(conn,user,quote)

    async def run(self,user,quote,update_id,prepared,on_accepted):
        app,req = self.app,quote.request
        if req.operation=='video':
            await app.anymodel_video.dispatch(quote,on_accepted=on_accepted)
            return None
        if req.operation==IMAGE_OP:
            await app.anymodel_images.dispatch(user,update_id,req.prompt,req.model,params=req.params,
                                               on_accepted=on_accepted)
            return None
        if req.operation=='audio.speech':
            await app.anymodel_speech.synthesize(quote.id,req.model,req.prompt,req.title)
            return Outcome('audio',quote.id)
        try:
            text = await self.chat_factory().chat(req.model,req.prompt,req.history,max_tokens=req.params['max_tokens'])
        except AnyModelError as error:
            detail = ('Исход запроса неизвестен. Автоповтора нет.' if error.code in
                      ('response_timeout','transport_error','connect_timeout','connect_error') else str(error))
            raise Rejected(f'AnyModel: {detail}') from None
        await app.pool.execute('INSERT INTO task_chat_works(quote_id,answer) VALUES($1,$2)',quote.id,text)
        return Outcome('chat',text,'AnyModel')


class ClodexExecution:
    def __init__(self,app):
        self.app = app

    def background(self,operation):
        return 'video' if operation=='video' else None

    async def prepare(self,conn,user,external,quote,update_id):
        app,req = self.app,quote.request
        model = app.clodex_launch_model(external,req)
        if not model:
            raise Rejected('CLODEX: тестовый запуск недоступен.')
        if req.operation=='video':
            await app.video.prepare_price(conn,user,quote)
        elif req.operation=='audio.speech':
            await conn.execute("""
                INSERT INTO task_speech_works(id,user_id,model_id,title,input,cost_tokens,claimed,expires_at,provider)
                VALUES($1,$2,$3,$4,$5,$6,true,now()+interval '7 days','clodex')
                """,quote.id,user,req.model,req.title,req.prompt,Decimal(quote.price['base']))
        return model

    async def run(self,user,quote,update_id,model,on_accepted):
        from .interaction import execute
        from .providers import ClodexProvider, DefinitiveFailure, UnknownOutcome

        app,req = self.app,quote.request
        if req.operation=='video':
            await app.video.submit_task(quote.id,req.model,req.prompt,None,on_accepted=on_accepted)
            return None
        if req.operation=='audio.speech':
            provider = ClodexProvider(app.cfg)
            try:
                audio = await provider.synthesize(req.prompt,req.params['voice'],1.0)
                await asyncio.to_thread(validate_mp3,audio)
            except UnknownOutcome:
                raise Rejected('Исход запроса неизвестен. Автоповтора нет.') from None
            except (DefinitiveFailure,AnyModelError):
                raise Rejected('Не удалось получить озвучку.') from None
            finally:
                await provider.close()
            await app.pool.execute('UPDATE task_speech_works SET audio=$2 WHERE id=$1',quote.id,audio)
            return Outcome('audio',quote.id)
        result = await execute(req.operation,model,req.prompt,req.history,mode='live',key=app.cfg.clodex_key,
                               request_id=update_id,quality=req.params.get('quality'))
        if req.operation==IMAGE_OP:
            work = await app.svc.save_image_work(user,update_id,req.model,req.prompt,result)
            return Outcome('image',work)
        await app.pool.execute('INSERT INTO task_chat_works(quote_id,answer) VALUES($1,$2)',quote.id,result.text)
        return Outcome('chat',result.text)
