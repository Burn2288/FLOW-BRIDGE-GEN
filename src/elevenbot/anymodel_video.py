"""AnyModel text-to-video transport and durable polling."""

import asyncio
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from .anymodel import AnyModelError, AnyModelProvider, BASE
from .video import ID_PATTERN, MAX_VIDEO_BYTES, InvalidVideoError, VideoPilot, VideoProtocolError, video_status_detail

MODEL='xai/grok-imagine-video-1.5'
TITLE='Grok Imagine Video 1.5'
DURATION=4
RESOLUTION='480p'
ASPECT_RATIO='16:9'
VIDEO_PATH='/v1/videos/generations'
CONNECTION_HEADER='x-9router-connection-id'
USD_PER_TOKEN=Decimal('0.00000005')


def validate_mp4(video):
    if len(video)<12 or video[4:8]!=b'ftyp':
        raise InvalidVideoError('content_mp4')
    with TemporaryDirectory() as tmp:
        path=Path(tmp)/'clip.mp4'
        path.write_bytes(video)
        try:
            probe=subprocess.run(
                ['ffprobe','-v','error','-show_entries','format=format_name:stream=codec_type',
                 '-of','json',str(path)],capture_output=True,check=True,timeout=10,
            )
            data=json.loads(probe.stdout)
            if 'mp4' in data['format']['format_name'].split(',') and any(
                stream.get('codec_type')=='video' for stream in data['streams']
            ):
                return video
        except (subprocess.SubprocessError,OSError,ValueError,KeyError,TypeError):
            pass
    raise InvalidVideoError('content_mp4')


class AnyModelVideoProvider(AnyModelProvider):
    async def video_json(self,method,path,**kwargs):
        try:
            response=await self.read_response(method,BASE+path,authenticated=True,max_body=65_536,**kwargs)
            data=self.decode(response.body)
        except AnyModelError as error:
            raise VideoProtocolError(error.code) from None
        if not isinstance(data,dict):
            raise VideoProtocolError('video_schema')
        return data,response

    async def create_video(self,model,prompt,idempotency_key,*,params=None):
        parameters=params or {'duration':DURATION,'resolution':RESOLUTION,'aspect_ratio':ASPECT_RATIO}
        data,reply=await self.video_json('POST','/videos/generations',accepted=(200,201,202),submission=True,
            request_headers={'Idempotency-Key':str(idempotency_key)},
            json={'model':model,'prompt':prompt,**parameters})
        task=data.get('request_id')
        if not isinstance(task,str) or not ID_PATTERN.fullmatch(task):
            raise VideoProtocolError('create_id')
        connection=reply.connection_id
        if connection and (len(connection)>4096 or not connection.isascii() or not connection.isprintable()):
            raise VideoProtocolError('connection_header')
        return task,connection

    @staticmethod
    def video_headers(connection):
        return {CONNECTION_HEADER:connection} if connection else {}

    async def video_status(self,task,connection):
        data,_=await self.video_json('GET',f'/videos/{task}',request_headers=self.video_headers(connection))
        status=data.get('status')
        if status=='pending':
            return video_status_detail(data)
        video=data.get('video')
        if status=='done' and isinstance(video,dict) and isinstance(video.get('url'),str) and video['url']:
            return status
        if status in ('failed','expired'):
            return 'failed'
        raise VideoProtocolError('status_shape')

    async def download_video(self,task,connection):
        try:
            response=await self.read_response('GET',f'{BASE}/videos/{task}/content',authenticated=True,
                max_body=MAX_VIDEO_BYTES,request_headers=self.video_headers(connection))
        except AnyModelError as error:
            if error.code=='response_size':
                raise InvalidVideoError('content_size') from None
            raise VideoProtocolError(error.code) from None
        if response.content_type not in ('video/mp4','application/octet-stream'):
            raise InvalidVideoError('content_type')
        return await asyncio.to_thread(validate_mp4,response.body)


class AnyModelVideoPilot(VideoPilot):
    provider='anymodel'
    label='AnyModel'
    title=TITLE

    def __init__(self,pool,cfg,*,api=None):
        super().__init__(pool,cfg,api=api or AnyModelVideoProvider(cfg.anymodel_key))
        self.key_fingerprint=hashlib.sha256(cfg.anymodel_key.encode()).hexdigest()

    def enabled(self):
        cfg=self.cfg
        return (cfg.anymodel_test_enabled and cfg.anymodel_video_live and cfg.access_mode=='private'
                and not cfg.payments_enabled and cfg.interaction_limit>0 and bool(cfg.anymodel_key))

    async def prepare(self,conn,user,quote):
        req=quote.request
        amount=Decimal(quote.price['provider_amount'])
        unit=quote.price['provider_unit']
        usd=None
        if unit=='USD':
            usd=amount
        elif unit=='anymodel_balance_token':
            usd=amount*USD_PER_TOKEN
        await conn.execute("""
            INSERT INTO video_jobs(id,user_id,model_id,prompt,cost_usd,provider,key_fingerprint,
                status,next_poll_at,idempotency_key)
            VALUES($1,$2,$3,$4,$5,'anymodel',$6,'submitting',now()+interval '1 minute',$1)
            """,quote.id,user,req.model,req.prompt,usd,self.key_fingerprint)

    async def dispatch(self,quote,*,on_accepted):
        req=quote.request
        async def create(model,prompt,key):
            return await self.api.create_video(model,prompt,key,params=req.params)
        await self.submit_task(quote.id,req.model,req.prompt,quote.id,on_accepted=on_accepted,create=create)

    async def task_status(self,task,connection):
        return await self.api.video_status(task,connection)

    async def task_content(self,task,connection):
        return await self.api.download_video(task,connection)
