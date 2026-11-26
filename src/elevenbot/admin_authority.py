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
    capabilities = list(CAPABILITIES[role])
    if role == 'OWNER_ADMIN':
        from .fixture_tariff import CAPABILITY, fixture_profile
        if fixture_profile() is not None:
            capabilities.append(CAPABILITY)
    return {'role': role, 'capabilities': capabilities}


def has_capability(authority, capability):
    return authority is not None and capability in authority['capabilities']
