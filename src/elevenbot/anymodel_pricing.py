"""Pricing for documented AnyModel text-to-media and chat contracts."""

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import hashlib
import json

from .anymodel import AnyModelError, AnyModelProvider, BASE, MODEL_ID
from .pricing import NoProviderPrice, PriceUnavailable, ProviderCost, chat_token_estimate, number

UNIT = 'anymodel_balance_token'
OPERATIONS = {
    'chat': ('/v1/chat/completions', 'token'),
    'images.generate': ('/v1/images/generations', 'image'),
    'video': ('/v1/videos/generations', 'second'),
    'audio.speech': ('/v1/audio/speech', 'character'),
}


def tariff(metadata, request):
    path, unit = OPERATIONS[request.operation]
    billing = metadata.get('billing')
    if (metadata.get('id') != request.model or metadata.get('endpoint') != path
            or not isinstance(billing, dict) or billing.get('unit') != unit):
        raise PriceUnavailable()
    parameters = request.params
    allowed = metadata.get('params') or []
    if not isinstance(allowed,list):
        raise PriceUnavailable()
    estimate = unit != 'character'
    try:
        output = number(billing['coefficient']['output'])
        if unit == 'token':
            input_tokens,max_tokens = chat_token_estimate(request)
            raw = input_tokens * number(billing['coefficient']['input']) + max_tokens * output
            details = f'Вход ≈ {input_tokens} токенов (по байтам UTF-8) · ответ до {max_tokens} токенов'
        elif unit == 'image':
            count = parameters.get('n', 1)
            if type(count) is not int or not 1 <= count <= 10:
                raise PriceUnavailable()
            scales = billing.get('scales', {})
            if not isinstance(scales, dict) or set(scales) - {'quality','size'}:
                raise PriceUnavailable()
            base = number(billing['base_tokens'])
            labels = [f'Изображений: {count}']
            for field in ('quality','size'):
                if field in scales:
                    selected = parameters.get(field, 'auto')
                    if field in parameters and field not in allowed:
                        raise PriceUnavailable()
                    base *= number(scales[field][selected])
                    labels.append(selected)
                elif field in parameters:
                    if field not in allowed:
                        raise PriceUnavailable()
                    labels.append(parameters[field])
            raw = base.to_integral_value(rounding=ROUND_HALF_UP) * count * output
            details = ' · '.join(labels)
        elif unit == 'second':
            duration, resolution, ratio = (parameters[key] for key in ('duration','resolution','aspect_ratio'))
            if type(duration) is not int or duration < 1 or set(parameters) - set(allowed):
                raise PriceUnavailable()
            for key, value in (('durations', duration), ('resolutions', resolution), ('aspect_ratios', ratio)):
                if key in metadata and value not in metadata[key]:
                    raise PriceUnavailable()
            rates = billing['rates']
            # A tier is only usable when an exact rate for the chosen mode is published.
            mode = parameters.get('mode')
            rate = rates[resolution] if mode is None else rates[mode][resolution]
            raw = duration * number(rate) * output
            details = f'{duration} с · {resolution} · {ratio}' + (f' · {mode}' if mode else '')
        else:
            units = len(request.prompt.encode('utf-16-le')) // 2
            if not 1 <= units <= 4000:
                raise PriceUnavailable()
            raw = units * number(billing['base_tokens']) * output
            details = f'{units} ед. UTF-16'
    except (KeyError, TypeError, AttributeError, UnicodeError):
        raise PriceUnavailable() from None
    digest = hashlib.sha256(json.dumps(billing, sort_keys=True).encode()).hexdigest()
    return ProviderCost(raw.to_integral_value(rounding=ROUND_CEILING), UNIT, estimate,
                        f'/v1/models/info · billing · {digest}', details)


class AnyModelPricing:
    def __init__(self, key, *, api=None):
        self.api = api or AnyModelProvider(key)

    async def metadata(self, model, operation):
        if operation not in OPERATIONS or not MODEL_ID.fullmatch(model):
            raise PriceUnavailable()
        try:
            response = await self.api.request('GET', BASE+'/models/info', authenticated=True,
                                              params={'id': model})
            metadata = self.api.decode(response)
        except AnyModelError as error:
            if error.status == 404:
                raise NoProviderPrice() from None
            raise PriceUnavailable() from None
        if isinstance(metadata, dict):
            metadata = metadata.get('data', metadata)
        if (not isinstance(metadata, dict) or metadata.get('id') != model
                or metadata.get('endpoint') != OPERATIONS[operation][0]):
            raise PriceUnavailable()
        return metadata

    async def cost(self, request):
        if not request.prompt.strip() or len(request.prompt) > 4000 or '\x00' in request.prompt:
            raise PriceUnavailable()
        data = await self.metadata(request.model, request.operation)
        if data.get('billing') is None or data['billing'] == {}:
            raise NoProviderPrice()
        return tariff(data, request)

    async def options(self, model, operation):
        data = await self.metadata(model, operation)
        fields = data.get('params') or []
        if not isinstance(fields,list):
            raise PriceUnavailable()
        billing = data.get('billing')
        if not isinstance(billing, dict) or billing.get('unit') != OPERATIONS[operation][1]:
            raise PriceUnavailable()
        if operation == 'chat':
            return {'max_tokens':[128,256,512]}
        if operation == 'images.generate':
            scales = billing.get('scales') or {}
            if not isinstance(scales,dict):
                raise PriceUnavailable()
            return {key:list(scales[key]) for key in ('quality','size')
                    if key in fields and isinstance(scales.get(key),dict)}
        if operation == 'video':
            rates = billing.get('rates') or {}
            options = {'duration':data.get('durations') or [],
                       'aspect_ratio':data.get('aspect_ratios') or []}
            if isinstance(rates,dict):
                options['resolution'] = [k for k,v in rates.items() if not isinstance(v,dict)]
                options['mode'] = [k for k,v in rates.items() if isinstance(v,dict)]
            return {k:v for k,v in options.items() if k in fields and isinstance(v,list) and v}
        return {}
