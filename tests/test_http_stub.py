"""Real localhost HTTP failure stub. No requests to Clodex."""
import httpx,pytest
from aiohttp import web
from elevenbot.providers import ClodexProvider,UnknownOutcome
from elevenbot.config import Config

class LocalTransport(httpx.AsyncBaseTransport):
    def __init__(self,port):self.port=port;self.inner=httpx.AsyncHTTPTransport()
    async def handle_async_request(self,r):
        assert r.url.host=='clodex.xyz'
        r.url=r.url.copy_with(scheme='http',host='127.0.0.1',port=self.port)
        return await self.inner.handle_async_request(r)
    async def aclose(self):await self.inner.aclose()

async def test_local_http_500_one_request():
    calls=[]
    async def respond(req):calls.append(await req.json());return web.Response(status=500,text='failure')
    app=web.Application();app.router.add_post('/v1/audio/speech',respond)
    runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1]
    try:
        async with httpx.AsyncClient(transport=LocalTransport(port)) as client:
            with pytest.raises(UnknownOutcome):await ClodexProvider(Config(clodex_key="fixture-token"),client).synthesize('test','demo',1.0)
        assert len(calls)==1
    finally:await runner.cleanup()
