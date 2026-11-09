from dataclasses import dataclass, field
import os
from pathlib import Path

@dataclass(frozen=True)
class Config:
    brand: str = 'DarkFlow | Gen'
    dsn: str = 'postgresql://elevenbot:localtest@localhost:55432/elevenbot'
    mode: str = 'mock'
    access_mode: str = 'public'
    migration_dsn: str = ''
    generation_enabled: bool = False
    payments_enabled: bool = False
    payment_backend: str = 'platega'
    telegram_api_base: str = ''
    catalogue_enabled: bool = False
    catalogue_path: str = 'data/catalogue/models.json'
    catalogue_profile: str = ''
    budget: int | None = 0
    cost_per_char: int = 0
    retail_per_char: int = 1
    concurrency: int = 2
    token: str = ''
    storage: Path = Path('data/audio')
    support: str = 'Поддержка пока не настроена.'
    terms: str = 'Условия коммерческого сервиса пока не опубликованы.'
    privacy: str = 'Политика обработки данных пока не опубликована.'
    admin_ids: tuple[int, ...] = ()
    admin_password: str = field(default='', repr=False)
    clodex_key: str = ''
    clodex_music_owner: int = 0
    clodex_music_live: bool = False
    anymodel_key: str = ''
    anymodel_test_enabled: bool = False
    anymodel_chat_live: bool = False
    anymodel_image_live: bool = False
    anymodel_video_live: bool = False
    anymodel_speech_live: bool = False
    interaction_mode: str = 'off'
    video_pilot: bool = False
    interaction_limit: int = 0
    interaction_pairs: tuple[str, ...] = ()
    public_catalogue_models: tuple[str, ...] = ()
    clodex_model: str = ''
    voices_file: str = ''
    speech_pilot: bool = False
    economy_verified: bool = False

    @property
    def wallet_mode(self): return 'demo' if self.mode == 'mock' else 'live'

    @property
    def balance_wallet_mode(self):
        return 'live' if self.access_mode=='private' else self.wallet_mode

    @property
    def voice_catalogue_path(self):
        if self.speech_pilot:
            return Path(self.catalogue_path).with_name('elevenlabs-api-voices.json')
        return Path(self.voices_file) if self.voices_file else None

    @classmethod
    def env(cls,env_file=None):
        from .runtime_config import load_env_file
        root=load_env_file(env_file) if env_file else Path.cwd()
        def local(value):return str((root/Path(value).expanduser()).resolve()) if value else ""
        def flag(k): return os.getenv(k,'false').lower()=='true'
        budget = os.getenv('DAILY_PROVIDER_BUDGET_UNITS','0').strip()
        c=cls(dsn=os.getenv('DATABASE_URL',cls.dsn),mode=os.getenv('PROVIDER_MODE','mock'),
              access_mode=os.getenv('ACCESS_MODE','public'),migration_dsn=os.getenv('DATABASE_MIGRATION_URL',''),
              generation_enabled=flag('GENERATION_ENABLED'),payments_enabled=flag('PAYMENTS_ENABLED'),
              payment_backend=os.getenv('PAYMENT_BACKEND','platega'),telegram_api_base=os.getenv('TELEGRAM_API_BASE',''),
              catalogue_enabled=flag('CATALOGUE_ENABLED'),catalogue_path=local(os.getenv('CATALOGUE_PATH','data/catalogue/models.json')),catalogue_profile=local(os.getenv('CATALOGUE_PROFILE','')),
              budget=int(budget) if budget else None,
              cost_per_char=int(os.getenv('PROVIDER_COST_BOUND_PER_CHAR','0')),
              retail_per_char=int(os.getenv('RETAIL_CREDITS_PER_CHAR','1')),
              concurrency=int(os.getenv('PROVIDER_CONCURRENCY','2')),token=os.getenv('TELEGRAM_BOT_TOKEN',''),
              storage=Path(local(os.getenv('AUDIO_STORAGE_DIR','data/audio'))),
              support=os.getenv('SUPPORT_CONTACT',cls.support),terms=os.getenv('TERMS_TEXT',cls.terms),
              privacy=os.getenv('PRIVACY_TEXT',cls.privacy),
              admin_ids=tuple(int(x) for x in os.getenv('ADMIN_TELEGRAM_IDS','').split(',') if x.strip()),
              admin_password=os.getenv('ADMIN_PASSWORD',''),
              interaction_mode=os.getenv('CLODEX_INTERACTION_MODE','off'),
              video_pilot=flag('CLODEX_VIDEO_PILOT'),
              interaction_limit=int(os.getenv('CLODEX_INTERACTION_LIMIT','0')),
              interaction_pairs=tuple(x.strip() for x in os.getenv('CLODEX_INTERACTION_PAIRS','').split(',') if x.strip()),
              public_catalogue_models=tuple(x.strip() for x in os.getenv('PUBLIC_CATALOGUE_MODELS','').split(',') if x.strip()),
              anymodel_key=os.getenv('ANYMODEL_API_KEY',''),
              anymodel_test_enabled=flag('ANYMODEL_TEST_ENABLED'),
              anymodel_chat_live=flag('ANYMODEL_TEST_CHAT_LIVE'),
              anymodel_image_live=flag('ANYMODEL_TEST_IMAGE_LIVE'),
              anymodel_video_live=flag('ANYMODEL_TEST_VIDEO_LIVE'),
              anymodel_speech_live=flag('ANYMODEL_TEST_SPEECH_LIVE'),
              clodex_key=os.getenv('CLODEX_API_KEY',''),clodex_model=os.getenv('CLODEX_TTS_MODEL',''),
              clodex_music_owner=int(os.getenv('CLODEX_MUSIC_OWNER','0') or 0),
              clodex_music_live=flag('CLODEX_MUSIC_LIVE'),
              voices_file=local(os.getenv('VOICES_FILE','')),speech_pilot=flag('CLODEX_SPEECH_PILOT'),economy_verified=flag('ECONOMY_VERIFIED'))
        if c.access_mode not in ('private','public') or (c.access_mode=='private' and not c.admin_ids):raise ValueError('Private access requires ADMIN_TELEGRAM_IDS')
        if c.clodex_music_owner and (c.access_mode!='private' or c.clodex_music_owner not in c.admin_ids
                                    or not c.admin_password or c.payments_enabled or not c.clodex_key):
            raise ValueError('Music pilot requires one listed administrator, a password and a CLODEX key without payments')
        if c.clodex_music_live and not c.clodex_music_owner:
            raise ValueError('Music pilot requires CLODEX_MUSIC_OWNER')
        if c.speech_pilot and (c.access_mode!='private' or c.payments_enabled):
            raise ValueError('Speech pilot requires private access without payments')
        if c.speech_pilot and c.generation_enabled and (c.mode!='clodex' or c.clodex_model!='eleven_v4'):
            raise ValueError('Live speech pilot requires CLODEX_TTS_MODEL=eleven_v4')
        if c.interaction_mode not in ('off','mock','live'):
            raise ValueError('Invalid CLODEX_INTERACTION_MODE')
        if c.interaction_mode=='live' and not (
            c.access_mode=='private' and c.clodex_key and c.catalogue_enabled and
            c.interaction_pairs and 0<=c.interaction_limit<=100 and not c.payments_enabled
            and (c.interaction_limit>0 or set(c.interaction_pairs)=={'images.generate:nano-banana-2'})
        ):
            raise ValueError('Live interaction pilot requires private access, key, catalogue, explicit pairs and a positive request limit for models other than Nano Banana 2 image generation')
        if c.anymodel_test_enabled and c.access_mode!='private':
            raise ValueError('AnyModel pilot requires private access')
        if (c.anymodel_chat_live or c.anymodel_image_live or c.anymodel_video_live or c.anymodel_speech_live) and not (
            c.anymodel_test_enabled and c.anymodel_key and not c.payments_enabled and 1<=c.interaction_limit<=100
        ):
            raise ValueError('Live AnyModel requests require a test key and positive request limit')
        if c.video_pilot and (c.interaction_mode!='live' or not 1<=c.interaction_limit<=100):
            raise ValueError('Video pilot requires private live interaction and a positive request limit')
        if c.mode=='catalogue' and (c.generation_enabled or c.payments_enabled):raise ValueError('Catalogue mode cannot generate or charge')
        if c.catalogue_enabled:
            from .discovery import SchemaProfile
            SchemaProfile.load(c.catalogue_profile)
        if c.payment_backend not in ('stars','platega'):raise ValueError('Invalid payment backend')
        if c.telegram_api_base:
            from urllib.parse import urlparse
            parsed=urlparse(c.telegram_api_base)
            if not(flag('ALLOW_LOCAL_TELEGRAM_STUB') and c.mode=='mock' and not c.payments_enabled and parsed.hostname=='127.0.0.1' and parsed.scheme=='http' and not parsed.username and not parsed.password):
                raise ValueError('Local Telegram stub allowed only in explicit unpaid mock mode')
        if c.mode not in ('mock','clodex','catalogue') or c.concurrency<1 or c.retail_per_char<1: raise ValueError('Invalid configuration')
        if c.mode=='mock' and c.payments_enabled: raise ValueError('Real payments forbidden in mock')
        if c.mode=='clodex' and (c.generation_enabled or c.payments_enabled):
            if not(c.economy_verified and c.clodex_key and c.clodex_model and c.voice_catalogue_path and c.cost_per_char>0 and (c.budget is None or c.budget>0)):
                raise ValueError('Verified contract/economy/key/catalog required')
        if c.payments_enabled and (c.support==cls.support or c.terms==cls.terms or c.privacy==cls.privacy):
            raise ValueError('Published terms, privacy and support required')
        return c
