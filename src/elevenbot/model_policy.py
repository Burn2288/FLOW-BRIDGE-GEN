"""Approved model operations and the Admin Edition price overview."""

import asyncio
from uuid import uuid4

from .core import Rejected
from .pricing import BOT_UNIT, PriceUnavailable, Request, display
from .tariff_admin import OPERATIONS, default_params

ROUTES = {'ours','ourmode','ourmarkup'}
SAMPLE = 'Проверка тарифа'


def canonical(provider,model,operation):
    if provider=='clodex' and operation=='audio.speech' and model=='eleven-v4':
        return 'eleven_v4'
    return model


async def admitted(conn,provider,model,operation):
    return bool(await conn.fetchval("""
        SELECT 1 FROM approved_models WHERE provider=$1 AND model_id=$2 AND operation=$3 FOR KEY SHARE
        """,provider,canonical(provider,model,operation),operation))


def rule_label(kind,amount):
    amount = str(amount)
    if '.' in amount:
        amount = amount.rstrip('0').rstrip('.')
    return amount+'%' if kind=='percent' else amount+' токенов'


class ModelPolicy:
    def __init__(self,app,keyboard):
        self.app,self.keyboard = app,keyboard

    async def list(self,provider,operation=None,*,snapshot=None):
        rows = await self.app.pool.fetch("""
            SELECT model_id,operation,title FROM approved_models
            WHERE provider=$1 AND ($2::text IS NULL OR operation=$2)
            ORDER BY title,model_id,operation
            """,provider,operation)

        if provider!='clodex' or not any(row['operation']=='video' for row in rows):
            return rows
        try:
            active=self.app.clodex_video_ids(snapshot if snapshot is not None else self.app.catalogue_snapshot())
        except Rejected:
            active=set()
        return [row for row in rows if row['operation']!='video' or row['model_id'] in active]

    async def allowed(self,provider,model,operation):
        # Transport-only fakes have no production execution path.
        if self.app.pool is None:
            return self.app.cfg.interaction_mode=='mock'
        async with self.app.pool.acquire() as conn:
            return await admitted(conn,provider,model,operation)

    async def change_admission(self,user,ext,args):
        await self.app.tariffs.authorize(user,ext)
        if len(args)!=3 or args[2] not in OPERATIONS:
            raise Rejected('Формат: /admit агрегатор ID операция или /revoke агрегатор ID операция.')
        provider,model,operation=args
        return provider,canonical(provider,model,operation),operation

    async def command(self,user,ext,command,args):
        await self.app.tariffs.authorize(user,ext)
        if command in ('/admit','/revoke'):
            provider,model,operation=await self.change_admission(user,ext,args)
            if command=='/admit':
                if provider=='clodex' and operation=='video':
                    from .video import catalogue_video_ids
                    if not self.app.video.api.supports_model(model):
                        raise Rejected('Для этой модели CLODEX ещё не подключён маршрут запуска видео.')
                    if model not in catalogue_video_ids(self.app.catalogue_snapshot()):
                        raise Rejected('Для модели нет доступного видеопротокола CLODEX в актуальном каталоге.')
                origin='anyvoice' if provider=='anymodel' and model.startswith('anyvoice/') else provider
                models=await self.app.tariffs.models(ext,origin)
                match=next((title for ident,title,ops in models if canonical(provider,ident,operation)==model
                            and operation in ops),None)
                if not match or (provider=='clodex' and model in ('nano-banana-2','gpt-image-2')):
                    raise Rejected('Модель или операция недоступна для допуска.')
                await self.app.pool.execute("""
                    INSERT INTO approved_models VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING
                    """,provider,model,operation,match)
            else:
                await self.app.pool.execute("""
                    DELETE FROM approved_models WHERE provider=$1 AND model_id=$2 AND operation=$3
                    """,provider,model,operation)
            ordered=list(dict.fromkeys(row['model_id'] for row in await self.list(provider)))
            page=ordered.index(model)//4 if model in ordered else 0
            await self.show(user,ext,provider,page)
            return
        context=await self.app.svc.aggregate_context(user) or {}
        draft=context.get('our_markup')
        if len(args)!=2 or not draft or draft['code']!=args[0]:
            raise Rejected('Откройте настройку наценки в «Наших моделях».')
        if draft['model'] and not any(row['model_id']==draft['model'] for row in await self.list(draft['provider'])):
            raise Rejected('Модель больше не допущена.')
        await self.app.pricing.set_rule(user,ext,draft['provider'],draft['model'],'percent',args[1])
        await self.app.svc.conversation(user,'home')
        await self.show(user,ext,draft['provider'],draft['page'])

    async def callback(self,user,ext,route,parts):
        await self.app.tariffs.authorize(user,ext)
        provider,page=parts[0],int(parts[1])
        if route=='ours':
            await self.app.svc.conversation(user,'home')
            await self.show(user,ext,provider,page)
            return
        from .anymodel_speech import voice_key
        key=parts[2]
        candidates={row['model_id'] for row in await self.list(provider) if voice_key(row['model_id'])[:16]==key}
        if key!='general' and len(candidates)!=1:
            raise Rejected('Модель больше не допущена.')
        model=next(iter(candidates),'')
        if route=='ourmode':
            async with self.app.pool.acquire() as conn:
                rule=await self.app.pricing.markup_rule(conn,provider,model)
                current=bool(rule and rule['model_id'])
                has_manual=await conn.fetchval('SELECT 1 FROM task_price_rules WHERE provider=$1 AND model_id=$2',
                                               provider,model)
            if current or has_manual:
                await self.app.pricing.set_markup_mode(user,ext,provider,model,'general' if current else 'manual')
                await self.show(user,ext,provider,page)
                return
        code=uuid4().hex[:12]
        await self.app.svc.aggregate_context(user,{'our_markup':dict(code=code,provider=provider,model=model,page=page)})
        await self.app.catalogue_screen(ext,
            ('Ручная наценка модели. ' if model else 'Общая наценка агрегатора. ')+
            f'Введите процент через /markup_value {code} ПРОЦЕНТ.',
            self.keyboard([[('← Наши модели',f'ours:{provider}:{page}')]]))

    async def show(self,user,ext,provider,page):
        from .anymodel_speech import voice_key
        if provider not in self.app.providers.prices:
            raise Rejected('Агрегатор недоступен.')
        grouped={}
        for row in await self.list(provider):
            grouped.setdefault(row['model_id'],[]).append(row)
        page=max(0,min(page,max(0,(len(grouped)-1)//4)))
        async with self.app.pool.acquire() as conn:
            general=await self.app.pricing.markup_rule(conn,provider,'')
        rate=rule_label(general['kind'],general['amount']) if general else '0%'
        lines=[f'Наши модели · {self.app.providers.interactive.get(provider,provider.upper())}',
               f'Общая наценка агрегатора: {rate}',
               f'Пример для чата и озвучки: «{SAMPLE}».']
        rows=[[('Изменить общую наценку',f'ourmarkup:{provider}:{page}:general')]]

        async def estimate(model,operation,title):
            params=default_params(provider,operation)
            try:
                return await self.app.pricing.preview_price(Request(provider,model,operation,title,SAMPLE,params))
            except PriceUnavailable:
                return None

        for model,entries in list(grouped.items())[page*4:(page+1)*4]:
            title=entries[0]['title']
            lines.append('\n'+title)
            async with self.app.pool.acquire() as conn:
                rule=await self.app.pricing.markup_rule(conn,provider,model)
            mode='Ручная' if rule and rule['model_id'] else 'Общая'
            applied=rule_label(rule['kind'],rule['amount']) if rule else '0%'
            estimates=await asyncio.gather(*(estimate(model,item['operation'],title) for item in entries))
            for entry,price in zip(entries,estimates):
                op=OPERATIONS[entry['operation']]
                if price:
                    from decimal import Decimal
                    base=f"{Decimal(price['base']).normalize():f}"
                    lines.append(f"{op} · {price['details']}\nСебестоимость {base} · {mode} наценка {applied} · "
                                 f"{'Итоговая оценка' if price['estimate'] else 'Итог'} {display(price['total'])} {BOT_UNIT}")
                else:
                    lines.append(f'{op} · Цена недоступна · {mode} наценка {applied}')
            key=voice_key(model)[:16]
            rows.append([(f'{title[:28]} · {mode}',f'ourmode:{provider}:{page}:{key}'),
                         ('Ручная наценка',f'ourmarkup:{provider}:{page}:{key}')])
            origin='anyvoice' if provider=='anymodel' and model.startswith('anyvoice/') else provider
            rows.append([('Источник · '+title[:35],f'tariffmodel:{origin}:{voice_key(model)}:0')])
        if not grouped:
            lines.append('Допущенных моделей пока нет.')
        nav=[]
        if page:nav.append(('← Назад',f'ours:{provider}:{page-1}'))
        if (page+1)*4<len(grouped):nav.append(('Далее →',f'ours:{provider}:{page+1}'))
        if nav:rows.append(nav)
        rows += [[('Источники и ручные тарифы','tariffs')],[('← Агрегаторы','providers')]]
        await self.app.catalogue_screen(ext,'\n'.join(lines),self.keyboard(rows))
