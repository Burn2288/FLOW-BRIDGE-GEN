"""Admission only; administrator privileges are checked independently."""

def admitted(config, external, platform='telegram'):
    if config.access_mode == 'public':
        return True
    return (platform == 'telegram' and type(external) is int and external > 0
            and external in (*config.admin_ids, *config.pilot_user_ids))
