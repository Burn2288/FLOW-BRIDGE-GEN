"""Provider-neutral quote, conversion, markup and confirmation lifecycle."""

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
from typing import Protocol
from uuid import UUID, uuid4

from .core import Rejected, Service

BOT_UNIT = 'токенов баланса'
UNKNOWN_PRICE = 'Не удалось рассчитать стоимость. Запуск закрыт.'
POLICY_LOCK = 921189


class PriceUnavailable(Rejected):
    def __init__(self):
        super().__init__(UNKNOWN_PRICE)


def number(value):
    if type(value) not in (int, float, str, Decimal):
        raise PriceUnavailable()
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise PriceUnavailable() from None
    if not amount.is_finite() or not 0 <= amount <= 10**12 or amount.as_tuple().exponent < -12:
        raise PriceUnavailable()
    return amount


def display(amount):
    return f'{int(Decimal(amount)):,}'.replace(',', '\u202f')


@dataclass(frozen=True)
class Request:
    provider: str
    model: str
    operation: str
    title: str
    prompt: str
    params: dict = field(default_factory=dict)
    history: list = field(default_factory=list)


@dataclass(frozen=True)
class ProviderCost:
    amount: Decimal
    unit: str
    estimate: bool
    source: str
    details: str


class PriceAdapter(Protocol):
    async def cost(self, request: Request) -> ProviderCost: ...


@dataclass(frozen=True)
class Quote:
    id: UUID
    request: Request
    price: dict

    def card(self):
        label = 'Оценка' if self.price['estimate'] else 'Стоимость'
        return (f"{self.request.title}\n{self.price['details']}\n"
                f"{label}: {display(self.price['total'])} {BOT_UNIT}\nЗапустить генерацию?")


class Pricing:
    def __init__(self, pool, config, adapters):
        self.pool, self.config, self.adapters = pool, config, adapters
        self.service = Service(pool, config)

    async def cost(self, request):
        adapter = self.adapters.get(request.provider)
        if adapter is None:
            raise PriceUnavailable()
        return await adapter.cost(request)

    async def calculate(self, conn, request, cost):
        rate = await conn.fetchrow('SELECT multiplier,revision FROM task_price_rates WHERE source_unit=$1', cost.unit)
        if rate is None:
            raise PriceUnavailable()
        rule = await conn.fetchrow("""
            SELECT provider,model_id,kind,amount,revision FROM task_price_rules
            WHERE (provider,model_id) IN (('',''),($1,''),($1,$2))
            ORDER BY (model_id<>'') DESC,(provider<>'') DESC LIMIT 1
            """, request.provider, request.model)
        base = cost.amount * rate['multiplier']
        markup = Decimal(0)
        if rule:
            markup = base * rule['amount'] / 100 if rule['kind'] == 'percent' else rule['amount']
        return {
            'provider_amount': str(cost.amount), 'provider_unit': cost.unit, 'source': cost.source,
            'estimate': cost.estimate, 'details': cost.details, 'bot_unit': BOT_UNIT,
            'rate': str(rate['multiplier']), 'rate_revision': rate['revision'], 'rounding': 'ceiling',
            'base': str(base), 'markup': str(markup), 'total': str((base+markup).to_integral_value(rounding=ROUND_CEILING)),
            'rule_revision': rule['revision'] if rule else None,
            'rule_scope': [rule['provider'], rule['model_id']] if rule else None,
        }

    async def insert(self, conn, user, request, price):
        quote = Quote(uuid4(), request, price)
        await conn.execute("""
            INSERT INTO task_price_quotes(id,user_id,provider,model_id,operation,request,price)
            VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb)
            """, quote.id, user, request.provider, request.model, request.operation,
            json.dumps(asdict(request)), json.dumps(price))
        return quote

    async def quote(self, user, request):
        cost = await self.cost(request)
        async with self.pool.acquire() as conn, conn.transaction():
            await self.service.authorize(conn, user)
            await conn.execute('SELECT pg_advisory_xact_lock($1::bigint)', POLICY_LOCK)
            await conn.execute("""
                UPDATE task_price_quotes SET state='superseded' WHERE user_id=$1 AND state='pending'
                AND provider=$2 AND model_id=$3 AND operation=$4
                """, user, request.provider, request.model, request.operation)
            return await self.insert(conn, user, request, await self.calculate(conn, request, cost))

    async def confirm(self, user, quote_id, update_id, prepare):
        async with self.pool.acquire() as conn:
            await self.service.authorize(conn, user)
            raw = await conn.fetchval("""
                SELECT request::text FROM task_price_quotes WHERE id=$1 AND user_id=$2 AND state='pending'
                """, quote_id, user)
        if not raw:
            raise Rejected('Оценка отменена или запрос уже принят.')
        request = Request(**json.loads(raw))
        cost = await self.cost(request)
        async with self.pool.acquire() as conn, conn.transaction():
            await self.service.authorize(conn, user)
            await conn.execute('SELECT pg_advisory_xact_lock($1::bigint)', POLICY_LOCK)
            row = await conn.fetchrow("""
                SELECT price::text,expires_at<=clock_timestamp() AS expired
                FROM task_price_quotes WHERE id=$1 AND user_id=$2 AND state='pending' FOR UPDATE
                """, quote_id, user)
            if not row:
                raise Rejected('Оценка отменена или запрос уже принят.')
            price = await self.calculate(conn, request, cost)
            if row['expired'] or price != json.loads(row['price']):
                await conn.execute("UPDATE task_price_quotes SET state='superseded' WHERE id=$1", quote_id)
                return await self.insert(conn, user, request, price), False
            quote = Quote(quote_id, request, price)
            if not await self.service.reserve_interaction_on(conn, user, update_id, unlimited=False):
                raise Rejected('Запрос уже принят.')
            await prepare(conn, quote)
            await conn.execute("""
                UPDATE task_price_quotes SET state='accepted',accepted_at=now(),update_id=$2 WHERE id=$1
                """, quote_id, update_id)
            return quote, True

    async def invalidate(self, user, provider, model, operation):
        async with self.pool.acquire() as conn:
            await self.service.authorize(conn, user)
            await conn.execute("""
                UPDATE task_price_quotes SET state='superseded' WHERE user_id=$1 AND state='pending'
                AND provider=$2 AND model_id=$3 AND operation=$4
                """, user, provider, model, operation)

    async def cancel(self, user, quote_id):
        async with self.pool.acquire() as conn:
            await self.service.authorize(conn, user)
            return await conn.fetchval("""
                UPDATE task_price_quotes SET state='cancelled' WHERE id=$1 AND user_id=$2 AND state='pending'
                RETURNING id
                """, quote_id, user)

    async def admin(self, conn, user, external):
        if external not in self.config.admin_ids:
            raise Rejected('Действие доступно только администратору.')
        await self.service.authorize(conn, user)
        if not await conn.fetchval("""
            SELECT EXISTS(SELECT 1 FROM identities WHERE user_id=$1 AND platform='telegram' AND external_id=$2)
            """, user, external):
            raise Rejected('Действие доступно только администратору.')

    async def set_rule(self, user, external, provider, model, kind, amount=None):
        async with self.pool.acquire() as conn, conn.transaction():
            await self.admin(conn, user, external)
            await conn.execute('SELECT pg_advisory_xact_lock($1::bigint)', POLICY_LOCK)
            if kind == 'remove':
                await conn.execute('DELETE FROM task_price_rules WHERE provider=$1 AND model_id=$2', provider, model)
            elif kind in ('percent', 'fixed'):
                await conn.execute("""
                    INSERT INTO task_price_rules(provider,model_id,kind,amount) VALUES($1,$2,$3,$4)
                    ON CONFLICT(provider,model_id) DO UPDATE SET kind=excluded.kind,amount=excluded.amount,
                        revision=excluded.revision
                    """, provider, model, kind, number(amount))
            else:
                raise Rejected('Доступные правила: percent, fixed, remove.')

    async def set_rate(self, user, external, unit, amount):
        rate = number(amount)
        if not rate:
            raise PriceUnavailable()
        async with self.pool.acquire() as conn, conn.transaction():
            await self.admin(conn, user, external)
            await conn.execute('SELECT pg_advisory_xact_lock($1::bigint)', POLICY_LOCK)
            await conn.execute("""
                INSERT INTO task_price_rates(source_unit,multiplier) VALUES($1,$2)
                ON CONFLICT(source_unit) DO UPDATE SET multiplier=excluded.multiplier,revision=excluded.revision
                """, unit, rate)

    async def reconcile(self, user, external, quote_id, debit, refund, provider_cost, reference):
        debit, refund = number(debit), number(refund)
        actual = None if provider_cost == '-' else number(provider_cost)
        if refund > debit or not 1 <= len(reference) <= 200:
            raise Rejected('Проверьте суммы и ссылку на подтверждение.')
        async with self.pool.acquire() as conn, conn.transaction():
            await self.admin(conn, user, external)
            if not await conn.fetchval("""
                SELECT id FROM task_price_quotes WHERE id=$1 AND state='accepted' FOR UPDATE
                """, quote_id):
                raise Rejected('Принятая задача не найдена.')
            await conn.execute("""
                INSERT INTO task_price_accounting(quote_id,user_debit,user_refund,provider_cost,reference)
                VALUES($1,$2,$3,$4,$5)
                ON CONFLICT(quote_id) DO UPDATE SET user_debit=excluded.user_debit,
                    user_refund=excluded.user_refund,provider_cost=excluded.provider_cost,
                    reference=excluded.reference
                """, quote_id, debit, refund, actual, reference)

    async def report(self, user, external):
        async with self.pool.acquire() as conn:
            await self.admin(conn, user, external)
            return await conn.fetchrow("""
                SELECT count(*) AS jobs, count(a.quote_id) AS reconciled,
                    count(a.provider_cost) AS cost_count,
                    sum(a.user_debit-a.user_refund) AS revenue,
                    sum(a.provider_cost*(q.price->>'rate')::numeric) AS actual_cost,
                    sum(a.user_debit-a.user_refund-a.provider_cost*(q.price->>'rate')::numeric) AS actual_margin,
                    sum(COALESCE(a.user_debit-a.user_refund,(q.price->>'total')::numeric)-(q.price->>'base')::numeric)
                        FILTER (WHERE a.provider_cost IS NULL) AS estimated_margin
                FROM task_price_quotes q LEFT JOIN task_price_accounting a ON a.quote_id=q.id
                WHERE q.state='accepted'
                """)
