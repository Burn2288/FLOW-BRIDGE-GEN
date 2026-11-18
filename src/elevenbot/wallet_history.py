"""Telegram descriptions of immutable wallet movements."""
LABELS = {
    'payment': 'Пополнение', 'topup': 'Пополнение',
    'demo_grant': 'Демо-начисление', 'pilot_grant': 'Тестовое начисление',
    'reserve': 'В резерв под задание', 'task_reserve': 'В резерв под задание',
    'capture': 'Списано из резерва за задание', 'task_capture': 'Списано из резерва за задание',
    'release': 'Возвращено из резерва', 'task_release': 'Возвращено из резерва',
    'refund_hold': 'В резерв для возврата платежа', 'refund_release': 'Резерв возврата снят',
    'refund': 'Возврат платежа из резерва', 'topup_reversal': 'Отмена пополнения',
    'topup_debt_repay': 'Погашение задолженности', 'task_refund': 'Возврат за задание',
}


def history_screen(operations, page):
    lines = ['История операций · токены']
    for row in operations[:10]:
        task = f" · задание {str(row['task'])[:8]}" if row['task'] else ''
        amount = abs(row['da'] or row['dr'])
        lines.append(f"{row['created_at']:%d.%m.%Y %H:%M} UTC · {LABELS[row['kind']]}: {amount}{task}")
    if not operations:
        lines.append('Операций пока нет.')
    nav = []
    if page:
        nav.append(('← Предыдущие', f'walletlog:{page-1}'))
    if len(operations)>10:
        nav.append(('Далее →', f'walletlog:{page+1}'))
    rows = [nav] if nav else []
    rows.append([('← К балансу','section:2')])
    return '\n'.join(lines), rows
