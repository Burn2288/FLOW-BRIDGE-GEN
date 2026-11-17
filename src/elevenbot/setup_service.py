"""One-time portable configuration. No DB mutation or external API calls."""
import argparse,getpass,os,re
from pathlib import Path
from urllib.parse import urlsplit

def write_configuration(path,token,admin_id,dsn,state_dir=None,clodex_key=""):
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]{30,}',token):raise ValueError('Invalid BotFather token format')
    if not str(admin_id).isdigit() or int(admin_id)<1:raise ValueError('Positive Telegram owner ID required')
    parsed=urlsplit(dsn)
    if parsed.scheme not in ('postgres','postgresql') or not parsed.hostname or not parsed.path.strip('/'):raise ValueError('PostgreSQL URL required')
    values={'DATABASE_URL':dsn,'TELEGRAM_BOT_TOKEN':token,'ADMIN_TELEGRAM_IDS':str(admin_id),'ACCESS_MODE':'private',
      'PROVIDER_MODE':'catalogue','GENERATION_ENABLED':'false','PAYMENTS_ENABLED':'false','ECONOMY_VERIFIED':'false',
      'CATALOGUE_ENABLED':'true','CATALOGUE_PATH':'data/catalogue/models.json','AUDIO_STORAGE_DIR':'data/audio',
      'PAYMENT_BACKEND':'platega','PLATEGA_ENABLED':'false',
      'TERMS_TEXT':'Сервис DarkFlow | Gen. Сейчас доступен каталог и подготовка запросов без генерации и оплаты.',
      'PRIVACY_TEXT':'Telegram ID и согласие сохраняются в PostgreSQL. Введённые в форму данные могут сохраняться до суток. Не отправляйте личные данные.',
      'SUPPORT_CONTACT':'Владелец сервиса'}
    if clodex_key:
        if not clodex_key.isascii() or not clodex_key.isprintable() or any(c.isspace() for c in clodex_key):
            raise ValueError('Invalid Clodex API key format')
        values['CLODEX_API_KEY'] = clodex_key
    if state_dir is not None:
        state_dir=Path(state_dir).resolve()
        values.update(AUDIO_STORAGE_DIR=str(state_dir/'audio'),CATALOGUE_PATH=str(state_dir/'catalogue'/'models.json'))
    for value in values.values():
        if any(ord(c)<32 for c in value) or value.startswith(('"',"'")) or value!=value.strip():raise ValueError('Invalid configuration value')
    path=Path(path).expanduser().resolve();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Never overwrite existing credentials or reset an established owner silently.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
        f.write('# DarkFlow Gen persistent runtime - keep private, never commit\n')
        for key,value in values.items():f.write(key+'='+value+'\n')
        f.flush();os.fsync(f.fileno())
    return path

def main():
    p=argparse.ArgumentParser();p.add_argument('--env-file',default='.env');p.add_argument('--database-file',default='private-db/database.env');p.add_argument('--state-dir');a=p.parse_args()
    if Path(a.env_file).exists():print('Configuration already exists. It was not changed.');return
    try:
        token=getpass.getpass('BotFather token (hidden; saved locally): ').strip()
        owner=input('Your numeric Telegram account ID: ').strip()
        database_file=Path(a.database_file)
        if database_file.exists():
            lines=database_file.read_text(encoding='utf-8').splitlines()
            if len(lines)!=1 or not lines[0].startswith('DATABASE_URL='):raise ValueError('Invalid database file')
            dsn=lines[0].partition('=')[2]
            print('Using saved runtime database connection (no administrator credentials).')
        else:dsn=getpass.getpass('PostgreSQL runtime URL (hidden): ').strip()
        clodex_key = getpass.getpass('Clodex API key for /v1/models (hidden, Enter for public catalog): ').strip()
        write_configuration(a.env_file,token,owner,dsn,a.state_dir,clodex_key)
        print('Configuration saved. Protect this file. Run migrations with the database owner before starting bot/worker.')
    except (ValueError,OSError):print('Setup failed: invalid input, existing file or file access. Secret values are hidden.');raise SystemExit(1)

if __name__=='__main__':main()
