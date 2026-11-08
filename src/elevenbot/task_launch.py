"""Apply launch policy, consume a quote once, and dispatch using the accepted request."""

import asyncio
from decimal import Decimal
from dataclasses import dataclass

from .anymodel import AnyModelError, IMAGE_OP, can_view
from .anymodel_speech import validate_mp3
from .core import Rejected
from .providers import DefinitiveFailure, UnknownOutcome, catalog


@dataclass
class Outcome:
    kind: str
    value: object


class TaskLaunch:
    def __init__(self, pricing, *, any_video, images, speech, video, any_chat,
                 clodex_run, clodex_speech):
        self.pricing, self.cfg, self.svc = pricing, pricing.config, pricing.service
        self.any_video, self.images, self.speech, self.video = any_video, images, speech, video
        self.any_chat, self.clodex_run, self.clodex_speech = any_chat, clodex_run, clodex_speech

    async def confirm(self, user, external, quote_id, update_id, *, clodex_model, progress, background):
        cfg = self.cfg
        if cfg.access_mode != 'private' or cfg.payments_enabled or external not in cfg.admin_ids:
            raise Rejected('Действие доступно только администратору.')

        async with self.pricing.pool.acquire() as conn:
            await self.pricing.admin(conn,user,external)
        selected = None

        async def prepare(conn, quote):
            nonlocal selected
            await self.pricing.admin(conn,user,external)
            req = quote.request
            if req.provider == 'anymodel':
                allowed = {
                    'video':self.any_video.enabled(),
                    'audio.speech':self.speech.enabled(external),
                    IMAGE_OP:cfg.anymodel_image_live and req.params.get('n',1)==1,
                    'chat':cfg.anymodel_chat_live,
                }
                if not can_view(cfg,external) or not allowed.get(req.operation):
                    raise Rejected('AnyModel: тестовый запуск выключен.')
                if req.operation == 'video':
                    await self.any_video.prepare(conn,user,quote)
                elif req.operation == IMAGE_OP:
                    await self.images.prepare(conn,user,update_id,req.prompt,req.model)
                elif req.operation == 'audio.speech':
                    await self.speech.prepare(conn,user,quote)
            elif req.provider == 'clodex':
                selected = clodex_model(req)
                if not selected:
                    raise Rejected('CLODEX: тестовый запуск недоступен.')
                if req.operation == 'video':
                    await self.video.prepare_price(conn,user,quote)
                elif req.operation == 'audio.speech':
                    await conn.execute("""
                        INSERT INTO task_speech_works(id,user_id,model_id,title,input,cost_tokens,claimed,expires_at,provider)
                        VALUES($1,$2,$3,$4,$5,$6,true,now()+interval '7 days','clodex')
                        """,quote.id,user,req.model,req.title,req.prompt,Decimal(quote.price['provider_amount']))
            else:
                raise Rejected('Агрегатор недоступен.')

        quote, accepted = await self.pricing.confirm(user,quote_id,update_id,prepare)
        if not accepted:
            return quote, accepted, None
        req = quote.request
        if req.operation == 'video':
            start = lambda job:background(req,'video',job)
            if req.provider == 'anymodel':
                await self.any_video.dispatch(quote,on_accepted=start)
            else:
                await self.video.submit_task(quote.id,req.model,req.prompt,None,on_accepted=start)
            return quote, accepted, None
        if req.operation == IMAGE_OP and req.provider == 'anymodel':
            await self.images.dispatch(user,update_id,req.prompt,req.model,params=req.params,
                on_accepted=lambda job:background(req,'image',job))
            return quote, accepted, None
        async with progress(req):
            outcome = await self.execute(user,quote,update_id,selected)
        return quote,accepted,outcome

    async def execute(self,user,quote,update_id,model):
        req = quote.request
        if req.operation == 'audio.speech':
            if req.provider == 'anymodel':
                await self.speech.synthesize(quote.id,req.model,req.prompt,req.title)
            else:
                try:
                    audio = await self.clodex_speech(req)
                    await asyncio.to_thread(validate_mp3,audio)
                except UnknownOutcome:
                    raise Rejected('Исход запроса неизвестен. Автоповтора нет.') from None
                except (DefinitiveFailure,AnyModelError):
                    raise Rejected('Не удалось получить озвучку.') from None
                await self.pricing.pool.execute('UPDATE task_speech_works SET audio=$2 WHERE id=$1',quote.id,audio)
            return Outcome('audio',quote.id)
        if req.provider == 'anymodel':
            try:
                text = await self.any_chat().chat(req.model,req.prompt,req.history,max_tokens=req.params['max_tokens'])
            except AnyModelError as error:
                detail = ('Исход запроса неизвестен. Автоповтора нет.' if error.code in
                          ('response_timeout','transport_error','connect_timeout','connect_error') else str(error))
                raise Rejected(f'AnyModel: {detail}') from None
        else:
            result = await self.clodex_run(req.operation,model,req.prompt,req.history,mode='live',
                                          key=self.cfg.clodex_key,request_id=update_id,
                                          quality=req.params.get('quality'))
            if req.operation == IMAGE_OP:
                work = await self.svc.save_image_work(user,update_id,req.model,req.prompt,result)
                return Outcome('image',work)
            text = result.text
        await self.pricing.pool.execute('INSERT INTO task_chat_works(quote_id,answer) VALUES($1,$2)',quote.id,text)
        return Outcome('chat',text)
