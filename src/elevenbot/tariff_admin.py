"""Telegram navigation and forms for the Admin Edition tariff catalogue."""

import json
from uuid import uuid4

from .anymodel import AnyModelError, can_view
from .anymodel_speech import voice_key
from .core import Rejected
from .pricing import (BOT_TOKEN, BOT_UNIT, MANUAL_BASES, RATE_UNITS, UNIT_LABELS, MissingRate,
                      PriceUnavailable, Request, cost_lines, decimal_text, number, total_text)

ROUTES = {'tariffs','tariffmodel','tariffop','tariffedit','tariffdisable','tariffinspect',
          'tariffpreset','tariffapply','tariffdiscard','rates','rateunit','rublerate'}
OPERATIONS = {'chat':'Чат','images.generate':'Изображение','video':'Видео','audio.speech':'Озвучка'}
PROVIDERS = {'anymodel':'AnyModel','anyvoice':'AnyVoice','clodex':'CLODEX'}
RUBLE_MENU = 'Стоимость токенов бота'
BASIS_LABELS = {'request':'запрос','utf16':'ед. UTF-16','image':'изображение','second':'секунду',
                'started_minute':'начатую минуту','token':'входной:выходной токен'}


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


TYPICAL_PARAMS = {
    'images.generate': [('n',1),('quality','auto'),('quality','high')],
    'video': [('duration',4),('duration',6),('resolution','480p'),('resolution','720p'),
              ('aspect_ratio','16:9'),('aspect_ratio','9:16')],
    'chat': [('max_tokens',128),('max_tokens',256),('max_tokens',512)],
}


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
        if provider not in PROVIDERS and provider not in self.app.providers.interactive:
            raise Rejected('Агрегатор недоступен.')
        if provider=='anyvoice':
            if not can_view(self.app.cfg,ext):
                raise Rejected('Раздел AnyVoice недоступен.')
            try:
                voices = await self.app.anymodel_speech.voices()
            except AnyModelError:
                raise Rejected('Каталог AnyVoice временно недоступен.') from None
            return [(model,voice['name'],['audio.speech']) for model,voice in voices.items()]
        if provider in self.app.providers.interactive:
            snapshot = await self.app.providers.collect(provider)
        else:
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
        if route in ('rates','rateunit','rublerate'):
            await self.rates(user,ext,route,arg)
            return
        if route in ('tariffapply','tariffdiscard'):
            await self.finish_preview(user,ext,arg,save=route=='tariffapply')
            return
        svc = self.app.svc
        if route=='tariffs':
            await svc.conversation(user,'home')
            if not arg:
                options = ['clodex']
                if can_view(self.app.cfg,ext):
                    options += ['anymodel','anyvoice']
                rows = [[(PROVIDERS[key],f'tariffs:{key}:0')] for key in options]
                rows.extend([(title,f'tariffs:{key}:0')] for key,title in self.app.providers.interactive.items())
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
            rows += [[('Курс и калькулятор',f"rates:{'anymodel' if provider=='anyvoice' else provider}")],
                     [('↻ Обновить каталог',f'tariffs:{provider}:{page}')],[('← Тарифы моделей','tariffs')]]
            await self.screen(ext,f'Тарифы моделей · {(PROVIDERS|self.app.providers.interactive)[provider]} ({len(models)})',rows)
            return
        if route=='tariffmodel':
            provider,key,page = arg.split(':',2)
            matches = [(model,title,ops) for model,title,ops in await self.models(ext,provider)
                       if voice_key(model)==key]
            if len(matches)!=1:
                raise Rejected('Модель отсутствует в актуальном каталоге.')
            model,title,ops = matches[0]
            await self.open_model(user,ext,provider,int(page),model,title,ops)
            return
        code,_,value = arg.partition(':')
        state = await self.state(user,code)
        if route=='tariffop':
            if value not in state['operations']:
                raise Rejected('Операция недоступна.')
            state = state|{'operation':value,'params':default_params(state['provider'],value),
                           'code':uuid4().hex[:12]}
            await svc.aggregate_context(user,{'tariff_admin':state})
            if state.get('our_provider'):
                await self.edit(user,ext,state,'confirmed')
                return
        elif route=='tariffpreset':
            req = self.request(state)
            options = TYPICAL_PARAMS.get(req.operation,[])
            if value=='defaults':
                params = default_params(req.provider,req.operation)
            else:
                index = int(value)
                if not 0<=index<len(options):
                    raise Rejected('Параметр недоступен.')
                field,selected = options[index]
                params = req.params|{field:selected}
            state = state|{'params':params,'code':uuid4().hex[:12]}
            await svc.aggregate_context(user,{'tariff_admin':state})
        elif route=='tariffedit' and value in ('confirmed','test'):
            await self.edit(user,ext,state,value)
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

    async def open_model(self,user,ext,origin,page,model,title,operations,*,our_provider=None):
        state = dict(provider='anymodel' if origin=='anyvoice' else origin,model=model,title=title,
                     operations=operations,origin=origin,page=page,code=uuid4().hex[:12],our_provider=our_provider)
        if our_provider and len(operations)==1:
            op=operations[0]
            state |= {'operation':op,'params':default_params(our_provider,op)}
            await self.edit(user,ext,state,'confirmed')
            return
        await self.app.svc.aggregate_context(user,{'tariff_admin':state})
        rows = [[(OPERATIONS[op],f"tariffop:{state['code']}:{op}")] for op in operations]
        await self.screen(ext,f'{title}\nID: {model}\nВыберите операцию.',rows+[self.back(state)])

    @staticmethod
    def back(state):
        if state.get('our_provider'):
            return [('← Наши модели',f"ours:{state['our_provider']}:{state['page']}")]
        return [('← Модели',f"tariffs:{state['origin']}:{state['page']}")]

    async def edit(self,user,ext,state,value):
        state = state|{'edit':value,'code':uuid4().hex[:12]}
        await self.app.svc.aggregate_context(user,{'tariff_admin':state})
        options = ', '.join(key for key,op in MANUAL_BASES.items() if op in (None,state['operation']))
        expiry = 'СРОК' if value=='test' else '[СРОК]'
        source = '\nДля AnyVoice укажите источник studio:… или support:….' if state['origin']=='anyvoice' and value=='confirmed' else ''
        await self.screen(ext,f"Укажите ставку в токенах DarkFlow | Gen для {state['model']}. Основания: {options}.\n"
            f"/tariff_set {state['code']} ОСНОВАНИЕ {BOT_TOKEN} СТАВКА {expiry} ИСТОЧНИК\n"
            'Срок в формате ISO 8601 с часовым поясом. Для token укажите вход:выход.'+source,
            [[('Подтверждённая ставка' if value=='test' else 'Временная тестовая ставка',
               f"tariffedit:{state['code']}:{'confirmed' if value=='test' else 'test'}")], self.back(state)])

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
            if state.get('our_provider') and fields['unit']!=BOT_TOKEN:
                raise Rejected('Введите ручную себестоимость в токенах DarkFlow | Gen.')
            await self.preview(user,ext,req.provider,[req.model],req.operation,req.params,fields,state=state)
            return
        state.pop('edit',None)
        state['code']=uuid4().hex[:12]
        await self.app.svc.aggregate_context(user,{'tariff_admin':state})
        await self.inspect(user,ext,state)

    async def preview(self,user,ext,provider,models,operation,params,fields,*,state=None):
        examples = await self.app.pricing.preview_manual(user,ext,provider,models,operation,params,fields)
        code = uuid4().hex[:12]
        draft = dict(code=code,provider=provider,models=models,operation=operation,params=params,
                     fields=fields,state=state)
        await self.app.svc.aggregate_context(user,{'tariff_preview':draft})
        expiry = fields.get('expires')
        term = expiry if expiry and expiry!='-' else 'без срока'
        lines = [f"{model} · {details} · наценка {decimal_text(price['markup'])} {BOT_UNIT} · итог {total_text(price)}"
                 for model,price,details in examples]
        listing = '\n'.join(lines)
        unit = UNIT_LABELS.get(fields['unit'],fields['unit'])
        text = (f"Предпросмотр · {len(models)} поз.\nСтавка: {fields['amount']} {unit} за {BASIS_LABELS[fields['basis']]}"
                f"\nСрок: {term}\nИсточник: {fields['evidence']}\n"
                'Пример итоговой цены с наценкой при применении ручной ставки:\n')
        if len(text)+len(listing)>3800:
            from aiogram.types import BufferedInputFile
            await self.app.bot.send_document(ext,BufferedInputFile(listing.encode(),filename='tariff-preview.txt'),
                                             caption='Все выбранные ID и итоговые цены')
            listing = 'Список всех ID приложен файлом.'
        await self.screen(ext,text+listing,[[('Сохранить ставки',f'tariffapply:{code}'),
                                             ('Отмена',f'tariffdiscard:{code}')]])

    async def finish_preview(self,user,ext,code,*,save):
        context = await self.app.svc.aggregate_context(user) or {}
        draft = context.get('tariff_preview')
        if not draft or draft['code']!=code:
            raise Rejected('Предпросмотр устарел.')
        if save:
            voice_ids = {model for model in draft['models'] if model.startswith('anyvoice/')}
            if draft['provider']=='anymodel' and voice_ids:
                current = {row[0] for row in await self.models(ext,'anyvoice')}
                if not voice_ids.issubset(current):
                    raise Rejected('AnyVoice: список изменился. Ставки не изменены.')
            await self.app.pricing.set_tariffs(user,ext,draft['provider'],draft['models'],
                draft['operation'],draft['params'],**draft['fields'])
        state = draft['state']
        if state:
            if state.get('our_provider'):
                await self.app.svc.conversation(user,'home')
                await self.app.models.show(user,ext,state['our_provider'],state['page'])
                return
            state.pop('edit',None)
            state['code']=uuid4().hex[:12]
            await self.app.svc.aggregate_context(user,{'tariff_admin':state})
            await self.inspect(user,ext,state)
        else:
            await self.app.svc.conversation(user,'home')
            text = f"Тарифы обновлены. Позиций: {len(draft['models'])}." if save else 'Изменение отменено.'
            await self.screen(ext,text,[[('← Тарифы моделей','tariffs')]])

    async def inspect(self,user,ext,state):
        req = self.request(state)
        source,cost,manual = await self.app.pricing.inspect_tariff(user,ext,req)
        active = {'api':'API','manual':'Ручная ставка','missing':'Цена недоступна',
                  'unavailable':'Цена недоступна: API не подтвердил актуальную цену'}[source]
        params = json.dumps(req.params,ensure_ascii=False,separators=(',',':'))
        text = f'{req.title}\nID: {req.model}\n{OPERATIONS[req.operation]} · {params}\nДействующий источник: {active}'
        missing_rate = None
        if cost:
            if source=='api':
                text += f'\n{cost.source.rsplit(" · ",1)[0] if " · billing · " in cost.source else cost.source}'
            try:
                async with self.app.pool.acquire() as conn:
                    price = await self.app.pricing.calculate(conn,req,cost)
            except MissingRate as error:
                missing_rate = error.cost.unit
                text += f'\n{cost.details}\n{error}'
            else:
                scope = price['rule_scope']
                mode = 'Ручная' if scope and scope[1] else 'Общая'
                rate = decimal_text(price['rule_amount'])+('%' if price['rule_kind']=='percent' else f' {BOT_UNIT}')
                text += (f"\n{cost.details}\n{cost_lines(price)}"
                         f"\n{mode} наценка {rate} · {decimal_text(price['markup'])} {BOT_UNIT}"
                         f"\n{'Итоговая оценка' if price['estimate'] else 'Итог'}: {total_text(price)}")
        if manual:
            status = 'действует' if manual['active'] else 'истекла' if manual['enabled'] else 'отключена'
            expiry = manual['expires_at'].isoformat() if manual['expires_at'] else 'без срока'
            checked = manual['verified_at'].isoformat() if manual['verified_at'] else 'дата не записана'
            amount = f"{manual['amount'].normalize():f}"
            if manual['output_amount'] is not None:
                amount += f":{manual['output_amount'].normalize():f}"
            kind = 'тестовая' if manual['temporary'] else 'подтверждённая'
            text += (f"\nРучная ставка ({kind}, {status}): {amount} {UNIT_LABELS.get(manual['source_unit'],manual['source_unit'])} за {BASIS_LABELS[manual['basis']]}"
                     f"\nИсточник: {manual['evidence']}\nПроверка: {checked}\nСрок: {expiry}\nВерсия: {manual['revision']}")
        code = state['code']
        text += f'\nПараметры другого режима: /tariff_scope {code} JSON'
        rows = [[('Задать ручную ставку',f'tariffedit:{code}:confirmed')],
                [('Временная тестовая ставка',f'tariffedit:{code}:test')]]
        if missing_rate:
            rows.insert(0,[rate_button(req.provider,missing_rate)])
        presets = TYPICAL_PARAMS.get(req.operation,[])
        if presets:
            rows += [[(f'{field} · {value}',f'tariffpreset:{code}:{i}')]
                     for i,(field,value) in enumerate(presets)]
            rows.append([('Параметры по умолчанию',f'tariffpreset:{code}:defaults')])
        if manual and manual['enabled']:
            rows.append([('Отключить ручную ставку',f'tariffdisable:{code}')])
        rows += [[('↻ Проверить источник',f'tariffinspect:{code}')],self.back(state)]
        await self.screen(ext,text,rows)

    async def rates(self,user,ext,route,arg,*,sample=None):
        pricing = self.app.pricing
        if route=='rates':
            if arg not in pricing.adapters:
                raise Rejected('Агрегатор недоступен.')
            stored = await self.app.pool.fetch('SELECT source_unit FROM task_price_conversions WHERE provider=$1',arg)
            units = dict.fromkeys([unit for unit,provider in RATE_UNITS.items() if provider==arg]
                                  + [row['source_unit'] for row in stored])
            rows = [[(UNIT_LABELS.get(unit,unit),f'rateunit:{arg}:{unit}')] for unit in units]
            await self.app.svc.conversation(user,'home')
            await self.screen(ext,'Курс и калькулятор · '+provider_title(self.app,arg),rows+[[('← К управлению',f'agmanage:{arg}')]])
            return
        code = uuid4().hex[:12]
        if route=='rublerate':
            rate = await self.app.pool.fetchrow('SELECT bot_amount,rubles FROM task_ruble_equivalent WHERE id=1')
            value = f"{decimal_text(rate['bot_amount'])} {BOT_UNIT} = {decimal_text(rate['rubles'])} ₽" if rate else 'Курс не настроен'
            await self.app.svc.aggregate_context(user,{'price_rate':{'code':code,'ruble':True}})
            await self.screen(ext,f'{RUBLE_MENU}\n{value}\n/ruble_set {code} ТОКЕНЫ РУБЛИ',[[('Главное меню','home')]])
            return
        provider,unit = arg.split(':',1)
        if provider not in pricing.adapters or not unit or unit==BOT_TOKEN or len(arg.encode())>55:
            raise Rejected('Единица курса недоступна.')
        async with self.app.pool.acquire() as conn:
            rate = await pricing.rate(conn,provider,unit)
        label = UNIT_LABELS.get(unit,unit)
        value = f"{decimal_text(rate['source_amount'])} {label} = {decimal_text(rate['target_amount'])} {BOT_UNIT}" if rate else 'Курс не настроен'
        if sample is not None and rate:
            value += f"\n{decimal_text(sample)} {label} ≈ {decimal_text(pricing.convert(sample,rate))} {BOT_UNIT}"
        await self.app.svc.aggregate_context(user,{'price_rate':{'code':code,'provider':provider,'unit':unit}})
        await self.screen(ext,f'Курс и калькулятор · {provider_title(self.app,provider)} · {label}\n{value}\n'
                          f'/rate_set {code} СУММА_ПРОВАЙДЕРА ТОКЕНЫ_БОТА\n/rate_calc {code} СУММА_ПРОВАЙДЕРА',
                          [[('← Курс и калькулятор',f'rates:{provider}')],[('← К управлению',f'agmanage:{provider}')]])

    async def rate_command(self,user,ext,command,args):
        await self.authorize(user,ext)
        state = (await self.app.svc.aggregate_context(user) or {}).get('price_rate')
        if not state or not args or state['code']!=args[0]:
            raise Rejected('Откройте настройку курса заново.')
        if command=='/ruble_set' and state.get('ruble') and len(args)==3:
            await self.app.pricing.set_ruble_rate(user,ext,*args[1:])
            await self.rates(user,ext,'rublerate','')
            return
        if state.get('ruble'):
            raise Rejected('Используйте команду с экрана настройки курса.')
        provider,unit = state['provider'],state['unit']
        sample = None
        if command=='/rate_set' and len(args)==3:
            await self.app.pricing.set_rate(user,ext,unit,args[2],provider=provider,source_amount=args[1])
        elif command=='/rate_calc' and len(args)==2:
            sample = number(args[1])
        else:
            raise Rejected('Используйте команду с экрана настройки курса.')
        await self.rates(user,ext,'rateunit',f'{provider}:{unit}',sample=sample)


def rate_button(provider,unit):
    route = f'rateunit:{provider}:{unit}'
    return ('Настроить курс',route if len(route.encode())<=64 else f'rates:{provider}')


def provider_title(app,provider):
    return (PROVIDERS|app.providers.interactive).get(provider,provider)
