"""Classify an explicit rejection of a generation submission, without logging its body."""

import json

from .core import Rejected


class ProviderRefused(Rejected):
    """The provider rejected the submission before accepting work."""


# AnyModel's Errors contract names these request, authentication and billing rejections.
# A bare HTTP 400 is insufficient: output_budget_exhausted can still be billed.
REFUSALS = {
    400: {'bad_request', 'not_a_chat_model', 'unsupported_builtin_tool'},
    401: {'invalid_api_key'},
    402: {'payment_required'},
    403: {'insufficient_quota'},
    404: {'model_not_found'},
    422: {'unprocessable_request'},
}


async def check_submission_refusal(response):
    codes = REFUSALS.get(response.status_code)
    if codes is None:
        return
    body = bytearray()
    async for part in response.aiter_bytes(chunk_size=8192):
        if len(body)+len(part)>8192:
            return
        body.extend(part)
    try:
        code = json.loads(body)['error']['code']
    except (ValueError, TypeError, KeyError):
        return
    if isinstance(code,str) and code in codes:
        raise ProviderRefused('Провайдер отклонил запрос. Резерв возвращён.')
