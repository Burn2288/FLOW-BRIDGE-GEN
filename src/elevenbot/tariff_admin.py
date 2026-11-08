"""Telegram navigation and forms for the Admin Edition tariff catalogue."""

import json
from uuid import uuid4

from .anymodel import AnyModelError, can_view
from .anymodel_speech import voice_key
from .core import Rejected
from .pricing import MANUAL_BASES, Request

ROUTES = {'tariffs','tariffmodel','tariffop','tariffedit','tariffdisable','tariffinspect'}
OPERATIONS = {'chat':'Чат','images.generate':'Изображение','video':'Видео','audio.speech':'Озвучка'}
PROVIDERS = {'anymodel':'AnyModel','anyvoice':'AnyVoice','clodex':'CLODEX'}


def tariff_fields(args, *, temporary=False):
    if len(args) not in (4,5):
        raise Rejected('Укажите основание, единицу, ставку, срок при необходимости и источник.')
    basis,unit,amount,*rest = args
    expires = rest[0] if len(rest)==2 else None
    return dict(basis=basis,unit=unit,amount=amount,expires=expires,evidence=rest[-1],temporary=temporary)


def tariff_params(text):
    try:
        params = json.loads(text)
    except ValueError:
        raise Rejected('Укажите JSON параметров, например {}.') from None
    if (not isinstance(params,dict) or len(params)>12 or len(text)>1024
            or any(type(value) not in (str,int,float,bool) for value in params.values())):
        raise Rejected('Параметры должны быть JSON-объектом с простыми значениями.')
    try:
        json.dumps(params,allow_nan=False)
    except ValueError:
        raise Rejected('Недопустимые параметры тарифа.') from None
    return params


def default_params(provider,operation):
    if operation=='chat':
        return {'max_tokens':256 if provider=='anymodel' else 512}
    if operation=='video':
        return {'duration':4,'resolution':'480p' if provider=='anymodel' else '720p','aspect_ratio':'16:9'}
    return {'n':1} if provider=='clodex' and operation=='images.generate' else {}


class TariffAdmin:
    def __init__(self, app, keyboard):
        self.app, self.keyboard = app, keyboard

    async def screen(self,ext,text,rows):
        await self.app.catalogue_screen(ext,text,self.keyboard(rows))

    async def authorize(self,user,ext):
        if self.app.cfg.access_mode!='private' or ext not in self.app.cfg.admin_ids:
            raise Rejected('Действие доступно только администратору.')
        async with self.app.pool.acquire() as conn:
            await self.app.pricing.admin(conn,user,ext)

    async def models(self,ext,provider):
        if provider not in PROVIDERS:
            raise Rejected('Агрегатор недоступен.')
        if provider=='anyvoice':
            if not can_view(self.app.cfg,ext):
                raise Rejected('Раздел AnyVoice недоступен.')
            try:
                voices = await self.app.anymodel_speech.voices()
            except AnyModelError:
                raise Rejected('Каталог AnyVoice временно недоступен.') from None
            return [(model,voice['name'],['audio.speech']) for model,voice in voices.items()]
        snapshot = self.app.anymodel_snapshot(ext) if provider=='anymodel' else self.app.catalogue_snapshot()
        models = []
        for row in snapshot['models']:
            if row.get('provider')!=provider or row.get('availability')!='key_available':
                continue
            operations = [op for op in row['operations'] if op in OPERATIONS]
            if provider=='clodex' and 'openai-video' in row.get('protocols',[]) and 'video' not in operations:
                operations.append('video')
            if operations:
                models.append((row['id'],row['title'],operations))
        return models

    async def callback(self,user,ext,route,arg):
        await self.authorize(user,ext)
        svc = self.app.svc
        if route=='tariffs':
            await svc.conversation(user,'home')
            if not arg:
                options = ['clodex']
                if can_view(self.app.cfg,ext):
                    options += ['anymodel','anyvoice']
                rows = [[(PROVIDERS[key],f'tariffs:{key}:0')] for key in options]
                await self.screen(ext,'Тарифы моделей\nВыберите агрегатор.',rows+[[('← Агрегаторы','providers')]])
                return
            provider,page_arg = arg.split(':',1)
            models = await self.models(ext,provider)
            page = min(max(int(page_arg),0),max(0,(len(models)-1)//10))
            rows = [[(title[:80],f'tariffmodel:{provider}:{voice_key(model)}:{page}')]
                    for model,title,_ in models[page*10:(page+1)*10]]
            nav = []
            if page>0:
                nav.append(('← Назад',f'tariffs:{provider}:{page-1}'))
            if (page+1)*10<len(models):
                nav.append(('Далее →',f'tariffs:{provider}:{page+1}'))
            if nav:
                rows.append(nav)
            if provider=='anyvoice':
                rows.append([('Назначить тариф голосам','amvprices:0')])
            rows += [[('↻ Обновить каталог',f'tariffs:{provider}:{page}')],[('← Тарифы моделей','tariffs')]]
            await self.screen(ext,f'Тарифы моделей · {PROVIDERS[provider]} ({len(models)})',rows)
            return
        if route=='tariffmodel':
            provider,key,page = arg.split(':',2)
            matches = [(model,title,ops) for model,title,ops in await self.models(ext,provider)
                       if voice_key(model)==key]
            if len(matches)!=1:
                raise Rejected('Модель отсутствует в актуальном каталоге.')
            model,title,ops = matches[0]
            state = dict(provider='anymodel' if provider=='anyvoice' else provider,model=model,
                         title=title,operations=ops,origin=provider,page=int(page),code=uuid4().hex[:12])
            await svc.aggregate_context(user,{'tariff_admin':state})
            rows = [[(OPERATIONS[op],f"tariffop:{state['code']}:{op}")] for op in ops]
            await self.screen(ext,f'{title}\nID: {model}\nВыберите операцию.',
                              rows+[[('← Модели',f'tariffs:{provider}:{page}')]])
            return
        code,_,value = arg.partition(':')
        state = await self.state(user,code)
        if route=='tariffop':
            if value not in state['operations']:
                raise Rejected('Операция недоступна.')
            state = state|{'operation':value,'params':default_params(state['provider'],value),
                           'code':uuid4().hex[:12]}
            await svc.aggregate_context(user,{'tariff_admin':state})
        elif route=='tariffedit' and value in ('confirmed','test'):
            state = state|{'edit':value,'code':uuid4().hex[:12]}
            await svc.aggregate_context(user,{'tariff_admin':state})
            options = ', '.join(key for key,op in MANUAL_BASES.items() if op in (None,state['operation']))
            expiry = 'СРОК' if value=='test' else '[СРОК]'
            source = '\nДля AnyVoice подтвердите источник через studio:… или support:….' if state['origin']=='anyvoice' and value=='confirmed' else ''
            await self.screen(ext,f"Укажите ставку для {state['model']}. Основания: {options}.\n"
                f"/tariff_set {state['code']} ОСНОВАНИЕ ЕДИНИЦА СТАВКА {expiry} ИСТОЧНИК\n"
                'Срок в формате ISO 8601 с часовым поясом. Для token укажите вход:выход.'+source,
                [[('← К тарифу',f"tariffinspect:{state['code']}")]])
            return
        elif route=='tariffdisable':
            req = self.request(state)
            await self.app.pricing.set_tariff(user,ext,req.provider,req.model,req.operation,req.params)
        elif route!='tariffinspect':
            raise Rejected('Действие устарело. Откройте тариф заново.')
        if state.pop('edit',None) or route=='tariffdisable':
            state['code']=uuid4().hex[:12]
            await svc.aggregate_context(user,{'tariff_admin':state})
        await self.inspect(user,ext,state)

    async def state(self,user,code):
        context = await self.app.svc.aggregate_context(user) or {}
        state = context.get('tariff_admin')
        if not state or state['code']!=code:
            raise Rejected('Откройте модель в разделе «Тарифы моделей» заново.')
        return state

    @staticmethod
    def request(state):
        if 'operation' not in state:
            raise Rejected('Сначала выберите операцию.')
        return Request(state['provider'],state['model'],state['operation'],state['title'],
                       'Проверка тарифа',state['params'])

    async def command(self,user,ext,command,args):
        await self.authorize(user,ext)
        if not args:
            raise Rejected('Откройте тариф и используйте команду с экрана.')
        state = await self.state(user,args[0])
        req = self.request(state)
        if command=='/tariff_scope':
            state = state|{'params':tariff_params(' '.join(args[1:]))}
        else:
            if state.get('edit') not in ('confirmed','test'):
                raise Rejected('Сначала выберите тип ручной ставки.')
            if state['origin']=='anyvoice' and req.model not in {m[0] for m in await self.models(ext,'anyvoice')}:
                raise Rejected('Голос отсутствует в актуальном каталоге.')
            fields = tariff_fields(args[1:],temporary=state['edit']=='test')
            await self.app.pricing.set_tariff(user,ext,req.provider,req.model,req.operation,req.params,**fields)
        state.pop('edit',None)
        state['code']=uuid4().hex[:12]
        await self.app.svc.aggregate_context(user,{'tariff_admin':state})
        await self.inspect(user,ext,state)

    async def inspect(self,user,ext,state):
        req = self.request(state)
        source,cost,manual = await self.app.pricing.inspect_tariff(user,ext,req)
        active = {'api':'API','manual':'Ручная ставка','missing':'Цена недоступна',
                  'unavailable':'Цена недоступна: API не подтвердил актуальную цену'}[source]
        params = json.dumps(req.params,ensure_ascii=False,separators=(',',':'))
        text = f'{req.title}\nID: {req.model}\n{OPERATIONS[req.operation]} · {params}\nДействующий источник: {active}'
        if cost:
            text += f'\n{cost.source.rsplit(" · ",1)[0] if " · billing · " in cost.source else cost.source}'
            text += f'\nПробный расчёт: {cost.amount.normalize():f} {cost.unit} · {cost.details}'
        if manual:
            status = 'действует' if manual['active'] else 'истекла' if manual['enabled'] else 'отключена'
            expiry = manual['expires_at'].isoformat() if manual['expires_at'] else 'без срока'
            checked = manual['verified_at'].isoformat() if manual['verified_at'] else 'дата не записана'
            amount = f"{manual['amount'].normalize():f}"
            if manual['output_amount'] is not None:
                amount += f":{manual['output_amount'].normalize():f}"
            kind = 'тестовая' if manual['temporary'] else 'подтверждённая'
            text += (f"\nРучная ставка ({kind}, {status}): {amount} {manual['source_unit']} / {manual['basis']}"
                     f"\nИсточник: {manual['evidence']}\nПроверка: {checked}\nСрок: {expiry}\nВерсия: {manual['revision']}")
        code = state['code']
        text += f'\nПараметры другого режима: /tariff_scope {code} JSON'
        rows = [[('Задать ручную ставку',f'tariffedit:{code}:confirmed')],
                [('Временная тестовая ставка',f'tariffedit:{code}:test')]]
        if manual and manual['enabled']:
            rows.append([('Отключить ручную ставку',f'tariffdisable:{code}')])
        rows += [[('↻ Проверить источник',f'tariffinspect:{code}')],
                 [('← Модели',f"tariffs:{state['origin']}:{state['page']}")]]
        await self.screen(ext,text,rows)
