"""Top-up menus share navigation, identity and administrator session checks."""

from uuid import uuid4

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .core import Rejected, uid
from .platega import PaymentInvalid, PaymentUnknown
from .pricing import display
from .topups import ORDER, amount, rubles

TOPUP_MENU='➕ Пополнить'
ADMIN_TITLE='Платежи и пополнение'
USER_ROUTES={'topups','tupick','tuown','tucreate','tucheck','tuhistory','tuorder'}
ADMIN_ROUTES={'tuadmin','tupresets','tuedit','tutoggle','tudelete','tumove','tuadd','tulimits','tucustom','tuaudit'}
ROUTES=USER_ROUTES|ADMIN_ROUTES
LABELS={'new':'Готов к оплате','creating':'Создание платежа','unknown':'Проверяем исход создания',
        'pending':'Ожидание оплаты','paid':'Оплачено','cancelled':'Отменён',
        'expired':'Срок оплаты истёк','error':'Ошибка','review':'Требуется сверка','refunded':'Возвращён'}


class TopupUI:
    def __init__(self,app,keyboard):
        self.app,self.keyboard=app,keyboard
        self.payments=app.topups

    async def screen(self,chat,text,rows,*,fresh=False):
        await self.app.catalogue_screen(chat,text,self.keyboard(rows),fresh_panel=fresh)

    async def authorize(self,user,chat):
        await self.app.tariffs.authorize(user,chat)

    async def panel(self,user,chat,page=0,*,fresh=False):
        await self.app.svc.conversation(user,'home')
        settings=await self.payments.settings()
        rate=await self.app.pool.fetchrow('SELECT * FROM task_ruble_equivalent WHERE id=1')
        choices=await self.app.pool.fetch("""SELECT * FROM topup_presets
            WHERE enabled AND amount BETWEEN $1 AND $2 ORDER BY position,id""",settings['minimum'],settings['maximum'])
        page=max(0,min(page,max(0,(len(choices)-1)//8)))
        code=uuid4().hex[:12]
        await self.app.svc.aggregate_context(user,{'topup_pick':code})
        rows=[]
        for choice in choices[page*8:(page+1)*8]:
            label=rubles(choice['amount'])+' ₽'
            if rate:
                from fractions import Fraction
                credits=int(Fraction(choice['amount'])*Fraction(rate['bot_amount'])/(100*Fraction(rate['rubles'])))
                label+=' · '+display(credits)+' токенов'
            rows.append([(label,f"tupick:{choice['id']}:{code}")])
        nav=[]
        if page:nav.append(('← Назад',f'topups:{page-1}'))
        if (page+1)*8<len(choices):nav.append(('Далее →',f'topups:{page+1}'))
        if nav:rows.append(nav)
        if settings['custom_enabled']:
            rows.append([('✏️ Своя сумма','tuown:'+code)])
        rows += [[('Мои платежи','tuhistory:0')],[('← Назад','section:2')]]
        text='Пополнение баланса'
        if self.app.cfg.topup_mode=='test':
            text+='\nТестовый кошелёк. Зачисления отдельно от общего баланса.'
        if not rate:text+='\nСтоимость токенов бота пока не настроена.'
        if self.app.cfg.topup_mode=='off':text+='\nПодключение оплаты готовится.'
        await self.screen(chat,text,rows,fresh=fresh)

    async def order(self,user,chat,order):
        row=await self.payments.owned(user,order)
        title='Тестовое пополнение' if row['mode']=='demo' else 'Пополнение баланса'
        text=(f"{title}\nК оплате {rubles(row['amount'])} ₽\n"
              f"Будет зачислено {display(row['credits'])} токенов\n{LABELS[row['state']]}")
        rows=[]
        if row['checkout_url'] and row['state']=='pending':
            rows.append([InlineKeyboardButton(text='Перейти к оплате',url=row['checkout_url'])])
        elif row['state']=='new':
            rows.append([InlineKeyboardButton(text='Перейти к оплате',callback_data=f"tucreate:{row['id']}")])
        rows += [[InlineKeyboardButton(text='Проверить оплату',callback_data=f"tucheck:{row['id']}")],
                 [InlineKeyboardButton(text='← Назад',callback_data='topups:0')]]
        await self.app.catalogue_screen(chat,text,InlineKeyboardMarkup(inline_keyboard=rows))

    async def callback(self,user,chat,route,arg):
        if route in ADMIN_ROUTES:
            await self.authorize(user,chat)
            await self.admin(user,chat,route,arg)
            return
        if route=='topups':
            await self.panel(user,chat,int(arg or 0));return
        if route=='tuhistory':
            await self.history(user,chat,int(arg));return
        if route in ('tucreate','tucheck','tuorder'):
            try:
                if route=='tucreate':
                    await self.payments.create(user,uid(arg),test_session=self.app.has_admin_session(chat))
                elif route=='tucheck':
                    await self.payments.check(user,uid(arg))
            except (PaymentInvalid,PaymentUnknown):
                raise Rejected('Платёж пока не подтверждён. Проверку можно повторить позже.') from None
            await self.order(user,chat,uid(arg));return
        context=await self.app.svc.aggregate_context(user) or {}
        code=arg.split(':')[-1]
        if context.get('topup_pick')!=code:
            raise Rejected('Панель устарела. Откройте пополнение заново.')
        settings=await self.payments.settings()
        if route=='tuown':
            if not settings['custom_enabled']:
                raise Rejected('Произвольная сумма отключена.')
            await self.app.svc.aggregate_context(user,{'topup_amount':code})
            await self.screen(chat,
                f"Введите сумму от {rubles(settings['minimum'])} до {rubles(settings['maximum'])} ₽.",
                [[('← Назад','topups:0')]])
            return
        choice=await self.app.pool.fetchrow('SELECT * FROM topup_presets WHERE id=$1 AND enabled',uid(arg.split(':')[0]))
        if not choice:
            raise Rejected('Этот вариант больше недоступен.')
        await self.quote(user,chat,choice['amount'],code)

    async def quote(self,user,chat,minor,code):
        row=await self.payments.quote(user,chat,minor,code,test_session=self.app.has_admin_session(chat))
        await self.order(user,chat,row['id'])

    async def input(self,user,chat,text,context):
        if 'topup_amount' in context:
            if not (await self.payments.settings())['custom_enabled']:
                raise Rejected('Произвольная сумма отключена.')
            await self.quote(user,chat,amount(text),context['topup_amount'])
            return
        await self.authorize(user,chat)
        form=context['topup_admin']
        fields=text.split()
        async with self.app.pool.acquire() as conn,conn.transaction():
            await conn.execute('SELECT id FROM topup_settings WHERE id=1 FOR UPDATE')
            if form['action']=='limits':
                if len(fields)!=2:
                    raise Rejected('Введите минимальную и максимальную сумму через пробел.')
                minimum,maximum=map(amount,fields)
                if minimum>maximum:
                    raise Rejected('Минимальная сумма превышает максимальную.')
                await conn.execute('UPDATE topup_settings SET minimum=$1,maximum=$2,revision=revision+1 WHERE id=1',minimum,maximum)
            elif form['action']=='add':
                value=amount(text)
                await conn.execute("""INSERT INTO topup_presets(amount,position)
                    SELECT $1,coalesce(max(position),0)+1 FROM topup_presets""",value)
            else:
                value=amount(text)
                await conn.execute('UPDATE topup_presets SET amount=$2 WHERE id=$1',uid(form['id']),value)
            await conn.execute("INSERT INTO audit_events(action) VALUES('topup_settings_changed')")
        await self.app.svc.conversation(user,'home')
        await self.admin(user,chat,'tuadmin','')

    async def admin(self,user,chat,route,arg):
        pool=self.app.pool
        if route=='tuadmin':
            await self.app.svc.conversation(user,'home')
            settings=await self.payments.settings()
            text=(f"{ADMIN_TITLE}\nРежим: {self.app.cfg.topup_mode}\n"
                  f"Магазин: {'настроен' if self.app.cfg.platega_merchant else 'не настроен'}\n"
                  f"Ограничения: {rubles(settings['minimum'])}–{rubles(settings['maximum'])} ₽\n"
                  'Курс берётся из «Стоимость токенов бота».')
            await self.screen(chat,text,[
                [('Готовые суммы','tupresets:0')],[('Добавить сумму','tuadd')],
                [('Изменить ограничения','tulimits')],
                [('Своя сумма: '+('включена' if settings['custom_enabled'] else 'выключена'),'tucustom')],
                [('Предпросмотр','topups:0')],[('История платежей','tuaudit:0')],
                [('Стоимость токенов бота','rublerate')],[('← Назад','providers')]])
            return
        if route in ('tupresets','tuaudit'):
            await self.app.svc.conversation(user,'home')
            if route=='tuaudit':
                await self.history(user,chat,int(arg),admin=True);return
            items=await pool.fetch('SELECT * FROM topup_presets ORDER BY position,id')
            page=max(0,min(int(arg),max(0,(len(items)-1)//8)))
            rows=[[(rubles(r['amount'])+' ₽ · '+('вкл' if r['enabled'] else 'выкл'),f"tuedit:{r['id']}")]
                  for r in items[page*8:(page+1)*8]]
            nav=[]
            if page:nav.append(('← Назад',f'tupresets:{page-1}'))
            if (page+1)*8<len(items):nav.append(('Далее →',f'tupresets:{page+1}'))
            if nav:rows.append(nav)
            rows.append([('← К настройкам','tuadmin')])
            await self.screen(chat,'Готовые суммы',rows);return
        if route in ('tuadd','tulimits'):
            await self.app.svc.aggregate_context(user,{'topup_admin':{
                'action':'add' if route=='tuadd' else 'limits'}})
            await self.screen(chat,'Введите сумму в рублях.' if route=='tuadd' else
                              'Введите минимальную и максимальную сумму через пробел.',
                              [[('← К настройкам','tuadmin')]])
            return
        if route=='tucustom':
            await pool.execute('UPDATE topup_settings SET custom_enabled=NOT custom_enabled,revision=revision+1 WHERE id=1')
            await self.admin(user,chat,'tuadmin','');return
        parts=arg.split(':')
        ident=uid(parts[0])
        row=await pool.fetchrow('SELECT * FROM topup_presets WHERE id=$1',ident)
        if not row:raise Rejected('Сумма больше недоступна.')
        if route=='tuedit':
            await self.app.svc.aggregate_context(user,{'topup_admin':{'action':'edit','id':str(ident)}})
            await self.screen(chat,f"{rubles(row['amount'])} ₽\nВведите новую сумму или выберите действие.",[
                [('Включить / выключить',f'tutoggle:{ident}')],
                [('Выше',f'tumove:{ident}:up'),('Ниже',f'tumove:{ident}:down')],
                [('Удалить',f'tudelete:{ident}')],[('← К суммам','tupresets:0')]])
            return
        async with pool.acquire() as conn,conn.transaction():
            await conn.execute('SELECT id FROM topup_settings WHERE id=1 FOR UPDATE')
            if route=='tutoggle':
                await conn.execute('UPDATE topup_presets SET enabled=NOT enabled WHERE id=$1',ident)
            elif route=='tudelete':
                await conn.execute('DELETE FROM topup_presets WHERE id=$1',ident)
            elif route=='tumove':
                ids=[r['id'] for r in await conn.fetch('SELECT id FROM topup_presets ORDER BY position,id')]
                if ident not in ids:raise Rejected('Сумма больше недоступна.')
                index=ids.index(ident)
                other=index+(-1 if parts[1]=='up' else 1)
                if 0<=other<len(ids):
                    ids[index],ids[other]=ids[other],ids[index]
                await conn.executemany('UPDATE topup_presets SET position=$2 WHERE id=$1',[(v,i) for i,v in enumerate(ids)])
        await self.app.svc.conversation(user,'home')
        await self.admin(user,chat,'tupresets','0')

    async def history(self,user,chat,page,admin=False):
        rows=await self.app.pool.fetch(ORDER+(' ORDER BY p.created_at DESC LIMIT 11 OFFSET $1' if admin
                      else ' WHERE p.user_id=$2 ORDER BY p.created_at DESC LIMIT 11 OFFSET $1'),
                      *([max(0,page)*10] if admin else [max(0,page)*10,user]))
        lines=['История платежей' if admin else 'Мои платежи']
        buttons=[]
        for row in rows[:10]:
            lines.append(f"{str(row['id'])[:8]} · {rubles(row['amount'])} ₽ · {LABELS[row['state']]}"
                         +(' · тест' if row['mode']=='demo' else ''))
            if not admin:
                buttons.append([(str(row['id'])[:8],f"tuorder:{row['id']}")])
        prefix='tuaudit' if admin else 'tuhistory'
        nav=[]
        if page:nav.append(('← Назад',f'{prefix}:{page-1}'))
        if len(rows)>10:nav.append(('Далее →',f'{prefix}:{page+1}'))
        if nav:buttons.append(nav)
        buttons.append([('← Назад','tuadmin' if admin else 'topups:0')])
        await self.screen(chat,'\n'.join(lines),buttons)

