"""Semantics introduced while joining PR #11 with the current composite."""
import httpx
import pytest

from elevenbot.anymodel import AnyModelError, AnyModelProvider


@pytest.mark.parametrize('terminal', [False, True])
async def test_catalogue_error_preserves_endpoint_and_terminal_flag(terminal):
    headers = {'X-Should-Retry': 'false'} if terminal else {}
    def respond(request):
        return httpx.Response(503, headers=headers)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(AnyModelError) as caught:
            await AnyModelProvider('fixture', client=client).collect()
    assert caught.value.status == 503
    assert caught.value.endpoint == '/v1/models'
    assert caught.value.terminal is terminal
