"""The single text-to-video route approved for the AnyModel pilot."""

import asyncio
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from .anymodel import AnyModelError, AnyModelProvider, BASE
from .video import ID_PATTERN, MAX_VIDEO_BYTES, InvalidVideoError, VideoPilot, VideoProtocolError

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

    async def estimate(self,model,prompt):
        if model!=MODEL:
            raise VideoProtocolError('video_model')
        data,_=await self.video_json('GET','/models/info',params={'id':model})
        if isinstance(data.get('data'),dict):
            data=data['data']
        params=data.get('params')
        billing=data.get('billing')
        if (data.get('id')!=MODEL or data.get('endpoint')!=VIDEO_PATH or not isinstance(params,list)
            or not all(field in params for field in ('duration','resolution','aspect_ratio'))
            or not isinstance(billing,dict) or billing.get('unit')!='second'):
            raise VideoProtocolError('video_tariff')
        # The documented Grok 1.5 contract permits 1–15 s and 16:9. Honor additional limits when present.
        for field,value in (('durations',DURATION),('resolutions',RESOLUTION),('aspect_ratios',ASPECT_RATIO)):
            limits=data.get(field)
            if limits is not None and (not isinstance(limits,list) or value not in limits):
                raise VideoProtocolError('video_parameters')
        coefficient=billing.get('coefficient')
        rates=billing.get('rates')
        rate=rates.get(RESOLUTION) if isinstance(rates,dict) else None
        if (not isinstance(coefficient,dict) or coefficient.get('input')!=1 or coefficient.get('output')!=1
            or type(rate) is not int or not 0<rate<=1_000_000_000):
            raise VideoProtocolError('video_tariff')
        return rate*DURATION*USD_PER_TOKEN

    async def create_video(self,model,prompt,idempotency_key):
        data,reply=await self.video_json('POST','/videos/generations',accepted=(200,201,202),
            request_headers={'Idempotency-Key':str(idempotency_key)},
            json={'model':model,'prompt':prompt,'duration':DURATION,'resolution':RESOLUTION,'aspect_ratio':ASPECT_RATIO})
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
            return status
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

    async def current_price(self,model):
        return await self.api.estimate(model,'')

    async def create_task(self,model,prompt,idempotency_key):
        return await self.api.create_video(model,prompt,idempotency_key)

    async def task_status(self,task,connection):
        return await self.api.video_status(task,connection)

    async def task_content(self,task,connection):
        return await self.api.download_video(task,connection)
