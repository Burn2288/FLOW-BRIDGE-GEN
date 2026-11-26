"""Generate a synthetic Stars receipt for the isolated DEV Telegram transport."""

from dataclasses import replace

from elevenbot.core import Rejected, Service
from elevenbot.referral_rewards import functional_test_database


async def successful_payment(pool, cfg, chat):
    """Open and precheck a fixture order. Telegram handles the actual credit."""
    if (functional_test_database() != 'flowbridge_dev' or cfg.dsn !=
            'postgresql://postgres:isolated-test-only@127.0.0.1:5432/flowbridge_dev'
            or cfg.payments_enabled or cfg.mode != 'clodex' or type(chat) is not int
            or chat not in (100, 101, 102, 103, 104)):
        raise Rejected('Платёж доступен только на изолированном тестовом стенде.')
    async with pool.acquire() as conn:
        if not await conn.fetchval("""
            SELECT current_database()='flowbridge_dev' AND session_user='postgres'
                AND inet_server_addr()='127.0.0.1'::inet AND inet_server_port()=5432
        """):
            raise Rejected('Платёж доступен только на изолированном тестовом стенде.')
        user = await conn.fetchval("""
            SELECT user_id FROM identities WHERE platform='telegram' AND external_id=$1
        """, chat)
    fixture = Service(pool, replace(cfg, payments_enabled=True, payment_backend='stars'))
    order = await fixture.order(user)
    if not await fixture.precheckout(user, order, 100, 'XTR'):
        raise Rejected('Тестовый счёт недоступен.')
    return {
        'currency': 'XTR',
        'total_amount': 100,
        'invoice_payload': str(order),
        'telegram_payment_charge_id': f'dev-stars-{order}',
        'provider_payment_charge_id': '',
    }
