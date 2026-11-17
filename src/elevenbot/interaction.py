"""Bounded request/response handlers shared by models on the same protocol."""
import asyncio
import base64
import binascii
from io import BytesIO
import json
import socket
import struct
from ipaddress import ip_address
import time
import zlib
from contextvars import ContextVar
from dataclasses import dataclass

import httpx
from PIL import Image
from simplejpeg import decode_jpeg, decode_jpeg_header

from .submission import check_submission_refusal
from .core import Rejected

provider_request_id = ContextVar('provider_request_id', default=None)

TEXT_LIMIT = 6000
IMAGE_LIMIT = 5 * 1024 * 1024
IMAGE_MAX_SIDE = 8192
IMAGE_MAX_PIXELS = 4096 * 4096
IMAGE_MAX_FRAMES = 64
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
PNG_END = b'\x00\x00\x00\x00IEND\xae\x42\x60\x82'
PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
ADAM7_PASSES = (
    (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
    (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
)
PATHS = {'chat': '/v1/chat/completions', 'images.generate': '/v1/images/generations'}
PROTOCOLS = {'chat': 'openai', 'images.generate': 'image-generation'}
DISABLED_CLODEX_MODELS = frozenset({'nano-banana-2', 'gpt-image-2'})
HIGH_QUALITY_IMAGE_MODELS = frozenset({'gpt-image-2.5-sunburst'})

# Small PNG fixture for checking Telegram delivery without sending data to CLODEX.
MOCK_IMAGE = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAeklEQVR4nO3PUQkAIBTAwFfIfmYypSH8OITBAtxm7fN1wwUNaEEDWtCAFjSgBQ1oQQNa0IAWNKAFDWhBA1rQgBY0oAUNaEEDWtCAFjSgBQ1oQQNa0IAWNKAFDWhBA1rQgBY0oAUNaEEDWtCAFjSgBQ1oQQNa0IAWPHYB+j3xLYWCDNkAAAAASUVORK5CYII='
)


@dataclass(frozen=True)
class Result:
    text: str = ''
    image: bytes = b''
    filename: str = ''


def is_disabled_model(model):
    return model.get('provider') == 'clodex' and model.get('id') in DISABLED_CLODEX_MODELS


def supports(model, operation, *, live):
    return (
        operation in PATHS and model.get('provider') == 'clodex'
        and not is_disabled_model(model)
        and (not live or (
            model.get('availability') == 'key_available'
            and PROTOCOLS[operation] in model.get('protocols', [])
        ))
    )


def decode_result(operation, payload):
    try:
        if operation == 'chat':
            text = payload['choices'][0]['message']['content']
            if isinstance(text, str) and 0 < len(text.strip()) and len(text) <= 16000:
                return Result(text=text)
        else:
            image = base64.b64decode(payload['data'][0]['b64_json'], validate=True)
            return image_result(image)
    except (KeyError, IndexError, TypeError, ValueError, binascii.Error):
        pass
    raise Rejected('CLODEX вернул неподдерживаемый результат.')


def _check_image_size(width, height, frames=1):
    if not (1 <= width <= IMAGE_MAX_SIDE and 1 <= height <= IMAGE_MAX_SIDE
            and 1 <= frames <= IMAGE_MAX_FRAMES
            and width * height * frames <= IMAGE_MAX_PIXELS):
        raise ValueError('Image dimensions exceed the decode budget')


def _png_scanline_bytes(width, height, bits_per_pixel, interlaced):
    passes = ADAM7_PASSES if interlaced else ((0, 0, 1, 1),)
    total = 0
    for x, y, dx, dy in passes:
        if x < width and y < height:
            columns = (width - x + dx - 1) // dx
            rows = (height - y + dy - 1) // dy
            total += rows * (1 + (columns * bits_per_pixel + 7) // 8)
    return total


def _verify_png_streams(image, canvas, bits_per_pixel, interlaced, frames_left):
    # Pillow can finish reading pixels before zlib has validated the stream trailer.
    source = memoryview(image)
    offset = len(PNG_SIGNATURE)
    stream = None
    frame_size = None
    while offset < len(source):
        length, kind = struct.unpack_from('>I4s', source, offset)
        start = offset + 8
        offset = start + length + 4  # Include the chunk CRC.
        if offset > len(source):
            raise ValueError('Truncated PNG chunk')
        if kind in (b'fcTL', b'IEND'):
            if stream is not None and (not stream.eof or remaining != 0):
                raise ValueError('Incomplete PNG compression stream')
            stream = None
        if kind == b'fcTL':
            if length != 26:
                raise ValueError('Invalid APNG frame control')
            frame_size = struct.unpack_from('>II', source, start + 4)
            if not (0 < frame_size[0] <= canvas[0] and 0 < frame_size[1] <= canvas[1]):
                raise ValueError('Invalid APNG frame size')
        if kind == b'IEND':
            if offset == len(source):
                return
            break
        if kind not in (b'IDAT', b'fdAT'):
            continue
        if kind == b'fdAT' and (length < 4 or frame_size is None):
            raise ValueError('APNG frame data without frame control')
        if stream is None:
            if frames_left == 0:
                raise ValueError('Too many PNG compression streams')
            frames_left -= 1
            width, height = canvas if kind == b'IDAT' else frame_size
            remaining = _png_scanline_bytes(width, height, bits_per_pixel, interlaced)
            stream = zlib.decompressobj()
        # APNG frame data starts with a four-byte sequence number.
        data = source[start + (4 if kind == b'fdAT' else 0):start + length]
        while data:
            remaining -= len(stream.decompress(data, min(65536, remaining + 1)))
            if remaining < 0 or stream.unused_data:
                raise ValueError('Invalid or oversized PNG compression stream')
            data = stream.unconsumed_tail
    raise ValueError('Invalid PNG end chunk')


def _verify_png(image):
    if image[8:16] != b'\x00\x00\x00\x0dIHDR' or not image.endswith(PNG_END):
        raise ValueError('Invalid PNG boundaries')
    width, height, depth, color_type, _, _, interlace = struct.unpack_from('>IIBBBBB', image, 16)
    _check_image_size(width, height)
    with Image.open(BytesIO(image), formats=('PNG',)) as decoded:
        frames = decoded.n_frames
        _check_image_size(width, height, frames)
        decoded.verify()
    _verify_png_streams(image, (width, height), depth * PNG_CHANNELS[color_type], interlace, frames)
    # verify() checks PNG chunks. Reopen and decode the pixels as well.
    with Image.open(BytesIO(image), formats=('PNG',)) as decoded:
        for frame in range(frames):
            decoded.seek(frame)
            decoded.load()


def image_result(image):
    try:
        if 0 < len(image) <= IMAGE_LIMIT:
            if image.startswith(PNG_SIGNATURE):
                _verify_png(image)
                return Result(image=image, filename='result.png')
            if image.startswith(b'\xff\xd8\xff') and image.endswith(b'\xff\xd9'):
                height, width, colorspace, _ = decode_jpeg_header(image, strict=True)
                _check_image_size(width, height)
                # Reject recoverable decoder errors, including truncated scan data with a valid EOI.
                output = 'CMYK' if colorspace in ('CMYK', 'YCCK') else 'RGB'
                decode_jpeg(image, colorspace=output, strict=True)
                return Result(image=image, filename='result.jpg')
    except (OSError, ValueError, SyntaxError, EOFError, struct.error, zlib.error,
            Image.DecompressionBombError):
        pass
    raise Rejected('CLODEX вернул неподдерживаемое изображение.')


def image_url(payload):
    if not isinstance(payload, dict):
        return None
    data = payload.get('data')
    item = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
    url = item.get('url') or payload.get('url')
    return url if isinstance(url, str) and url else None


class _ImageDownloadError(ValueError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


async def download_image(http, url, request_id):
    trace_interaction(request_id, 'image_download_start')
    phase = 'url_parse'
    try:
        async with asyncio.timeout(30):
            for _ in range(4):
                phase = 'url_parse'
                target = httpx.URL(url)
                if target.scheme != 'https':
                    raise _ImageDownloadError('url_scheme')
                if not target.host:
                    raise _ImageDownloadError('url_host_missing')
                if target.userinfo:
                    raise _ImageDownloadError('url_userinfo')
                if target.port not in (None, 443):
                    raise _ImageDownloadError('url_port')
                phase = 'dns_lookup'
                addresses = await asyncio.get_running_loop().getaddrinfo(
                    target.raw_host.decode('ascii'), 443, type=socket.SOCK_STREAM,
                )
                phase = 'dns_invalid_address'
                ips = [ip_address(address[4][0]) for address in addresses]
                if not ips:
                    raise _ImageDownloadError('dns_no_addresses')
                if any(not ip.is_global or ip.is_multicast for ip in ips):
                    raise _ImageDownloadError('dns_non_public')
                # Pin the checked address and keep TLS verification on the original hostname.
                phase = 'request_build'
                request = httpx.Request(
                    'GET', target.copy_with(host=str(ips[0])),
                    headers={'Host': target.netloc.decode('ascii')},
                    extensions={'sni_hostname': target.raw_host.decode('ascii')},
                )
                phase = 'http_request'
                response = await http.send(request, stream=True, auth=None, follow_redirects=False)
                try:
                    trace_interaction(request_id, 'image_download_headers', status=response.status_code)
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get('location')
                        if location is None:
                            raise _ImageDownloadError('redirect_location_missing')
                        phase = 'redirect_url'
                        url = str(target.join(location))
                        continue
                    phase = 'http_status'
                    response.raise_for_status()
                    image = bytearray()
                    phase = 'body_read'
                    async for part in response.aiter_bytes(65536):
                        if len(image) + len(part) > IMAGE_LIMIT:
                            raise _ImageDownloadError('image_too_large')
                        image.extend(part)
                    phase = 'image_invalid'
                    result = await asyncio.to_thread(image_result, bytes(image))
                    trace_interaction(request_id, 'image_download_ok', image_bytes=len(image))
                    return result
                finally:
                    await response.aclose()
            raise _ImageDownloadError('redirect_limit')
    except (Rejected, httpx.HTTPError, httpx.InvalidURL, OSError, KeyError, ValueError) as error:
        reason = error.reason if isinstance(error, _ImageDownloadError) else phase
        trace_interaction(request_id, 'image_download_failed', reason=reason, error_type=type(error).__name__)
        raise Rejected('Не удалось скачать готовое изображение CLODEX.') from None


def trace_interaction(request_id, stage, **fields):
    if request_id is not None:
        print(json.dumps({'event': 'interaction', 'request_id': request_id, 'stage': stage, **fields}), flush=True)


def response_shape(payload):
    if not isinstance(payload, dict):
        return {'json_type': type(payload).__name__}
    data = payload.get('data')
    item = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
    encoded = item.get('b64_json')
    error = payload.get('error')
    code = error.get('code') if isinstance(error, dict) else None
    return {
        'has_error': 'error' in payload,
        'error_code': code if type(code) is int or code in (
            'model_not_found', 'invalid_request_error', 'unsupported_model', 'insufficient_quota',
            'rate_limit_exceeded', 'invalid_api_key', 'content_policy_violation',
        ) else None,
        'data_items': len(data) if isinstance(data, list) else None,
        'has_base64': 'b64_json' in item,
        'base64_chars': len(encoded) if isinstance(encoded, str) else None,
        'has_url': 'url' in item or 'url' in payload,
        'has_choices': 'choices' in payload,
        'has_candidates': 'candidates' in payload,
        'has_task_id': 'task_id' in payload or 'task_id' in item,
    }


async def execute(operation, model, prompt, history, *, mode, key='', client=None, request_id=None, quality=None):
    if mode not in ('mock', 'live') or not supports(model, operation, live=mode == 'live'):
        raise Rejected('Для этой модели запуск пока недоступен.')
    if quality is not None and (quality != 'high' or operation != 'images.generate'
                                or model['id'] not in HIGH_QUALITY_IMAGE_MODELS):
        raise Rejected('Это качество недоступно для выбранной модели.')
    if mode == 'mock':
        if operation == 'chat':
            return Result(text='Тестовый ответ. Получен текст: '+prompt[:1000])
        return Result(image=MOCK_IMAGE, filename='test.png')
    if not key:
        raise Rejected('Ключ CLODEX не настроен.')
    body = {'model': model['id']}
    if operation == 'chat':
        body.update(messages=[*history, {'role': 'user', 'content': prompt}], max_tokens=512)
    else:
        body.update(prompt=prompt, n=1, response_format='b64_json')
        if quality is not None:
            body['quality'] = quality
    async def call(http):
        started = time.monotonic()
        trace_interaction(request_id, 'http_start', method='POST', endpoint='https://clodex.xyz'+PATHS[operation],
                          model=model['id'], operation=operation, request_fields=sorted(body),
                          response_format=body.get('response_format'), quality=body.get('quality'))
        async with http.stream('POST', 'https://clodex.xyz'+PATHS[operation],
                               json=body, headers={'Authorization': 'Bearer '+key},
                               follow_redirects=False) as response:
            content_type = response.headers.get('content-type', '').partition(';')[0].lower()
            trace_interaction(request_id, 'http_headers', status=response.status_code,
                              content_type=content_type if content_type in (
                                  'application/json', 'text/html', 'text/plain', 'application/octet-stream',
                                  'image/png', 'image/jpeg', 'text/event-stream',
                              ) else 'other',
                              elapsed_ms=round((time.monotonic()-started)*1000))
            if not response.is_success:
                if operation=='chat':
                    await check_submission_refusal(response)
                response.raise_for_status()
            raw = bytearray()
            async for part in response.aiter_bytes(65536):
                if len(raw)+len(part) > 8*1024*1024:
                    trace_interaction(request_id, 'http_body_too_large')
                    raise Rejected('Ответ CLODEX слишком большой.')
                raw.extend(part)
        trace_interaction(request_id, 'http_body_received', bytes=len(raw),
                          elapsed_ms=round((time.monotonic()-started)*1000))
        payload = json.loads(raw)
        trace_interaction(request_id, 'response_shape', **response_shape(payload))
        try:
            if operation == 'images.generate':
                result = await asyncio.to_thread(decode_result, operation, payload)
            else:
                result = decode_result(operation, payload)
        except Rejected:
            url = image_url(payload) if operation == 'images.generate' else None
            if not url:
                trace_interaction(request_id, 'decode_failed')
                raise
            if client is not None:
                result = await download_image(client, url, request_id)
            else:
                async with httpx.AsyncClient(
                    trust_env=False, limits=httpx.Limits(max_keepalive_connections=0),
                ) as downloader:
                    result = await download_image(downloader, url, request_id)
        trace_interaction(request_id, 'decode_ok', image_bytes=len(result.image))
        return result
    try:
        async with asyncio.timeout(25):
            if client is not None:
                return await call(client)
            async with httpx.AsyncClient(timeout=20, trust_env=False) as http:
                return await call(http)
    except httpx.HTTPStatusError as error:
        trace_interaction(request_id, 'http_error', status=error.response.status_code)
        raise Rejected(f'CLODEX вернул HTTP {error.response.status_code}.') from None
    except (httpx.TimeoutException, TimeoutError) as error:
        trace_interaction(request_id, 'timeout', error_type=type(error).__name__)
        raise Rejected('CLODEX не ответил вовремя. Статус генерации неизвестен. Автоповтора нет.') from None
    except httpx.RequestError as error:
        trace_interaction(request_id, 'network_error', error_type=type(error).__name__)
        raise Rejected('Сетевая ошибка при запросе к CLODEX. Исход запроса неизвестен. Автоповтора нет.') from None
    except ValueError:
        trace_interaction(request_id, 'invalid_json')
        raise Rejected('CLODEX вернул ответ, который не удалось прочитать как JSON. Автоповтора нет.') from None
