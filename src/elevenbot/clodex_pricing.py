"""CLODEX quote source. Public catalogue numbers are not account quotes."""

import httpx

from .pricing import NoProviderPrice, PriceUnavailable, ProviderCost, number
from .video import MODES, VideoProtocolError, payload

USD = 'USD'


class ClodexPricing:
    def __init__(self, video_api):
        self.video_api = video_api

    async def cost(self, request):
        if request.operation != 'video':
            # /api/pricing does not establish the account's group or a unit for
            # images, chat, or TTS. Use an approved manual tariff for these routes.
            raise NoProviderPrice()
        if (request.model not in {mode[0] for mode in MODES.values()}
                or not 1 <= len(request.prompt) <= 4000 or '\x00' in request.prompt):
            raise PriceUnavailable()
        expected = payload(request.model,request.prompt)
        params = {key:expected[key] for key in ('duration','resolution','aspect_ratio')}
        if request.params != params:
            raise PriceUnavailable()
        try:
            amount = number(await self.video_api.estimate(request.model,request.prompt))
        except (httpx.HTTPError, TimeoutError, VideoProtocolError):
            raise PriceUnavailable() from None
        return ProviderCost(amount, USD, True, 'CLODEX /v1/videos/estimate · cost_usd',
                            f"{params['duration']} с · {params['resolution']} · {params['aspect_ratio']}")
