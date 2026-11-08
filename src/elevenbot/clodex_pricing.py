"""CLODEX quote source. Public catalogue numbers are not account quotes."""

import httpx

from .pricing import NoProviderPrice, PriceUnavailable, ProviderCost, number
from .video import VIDEO_PARAMS, VideoProtocolError

class ClodexPricing:
    def __init__(self, video_api):
        self.video_api = video_api

    async def cost(self, request):
        if request.operation != 'video':
            # /api/pricing does not establish the account's group or a unit for
            # images, chat, or TTS. Use an approved manual tariff for these routes.
            raise NoProviderPrice()
        if (not self.video_api.supports_model(request.model)
                or not 1 <= len(request.prompt) <= 4000 or '\x00' in request.prompt):
            raise PriceUnavailable()
        params = request.params
        if params != VIDEO_PARAMS:
            raise PriceUnavailable()
        try:
            raw,unit,field = await self.video_api.estimate_cost(request.model,request.prompt)
            amount = number(raw)
        except (httpx.HTTPError, TimeoutError, VideoProtocolError):
            raise PriceUnavailable() from None
        return ProviderCost(amount, unit, True, f'CLODEX /v1/videos/estimate · {field}',
                            f"{params['duration']} с · {params['resolution']} · {params['aspect_ratio']}")
