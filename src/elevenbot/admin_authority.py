"""D-04 HTTP authority. Every read uses a current database role event."""

CAPABILITIES = {
    'OWNER_ADMIN': ('operations.read', 'settings.visibility', 'support.operate'),
    'READ_ONLY_ADMIN': ('operations.read',),
    'SUPPORT_OPERATOR': ('support.operate',),
    'SETTINGS_OPERATOR': ('settings.visibility',),
}


async def current_capabilities(conn, user):
    role = await conn.fetchval("""
        SELECT e.role FROM http_admin_role_events e JOIN users u ON u.id=e.subject_id
        WHERE e.subject_id=$1 AND NOT u.blocked ORDER BY e.revision DESC LIMIT 1
    """, user)
    if role not in CAPABILITIES:
        return None
    return {'role': role, 'capabilities': list(CAPABILITIES[role])}
