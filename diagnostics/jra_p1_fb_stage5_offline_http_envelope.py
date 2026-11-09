"""P1-FB Stage5 offline HTTP-envelope replay.

No sockets, requests, urllib.request, or arbitrary transport callbacks are used.
ScriptedResponse contains bytes already in memory; validating HTTP-like headers
is a dry-run of the future response boundary, not proof of live HTTP readiness.
"""
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType

from diagnostics.jra_p1_fb_stage4_mock_adapter import Response
from diagnostics.jra_p1_fb_stage5_live_preflight_disabled import (
    strict_official_url, LiveNetworkDisabled)

MAX_SOURCE_BYTES=1_800_000
ALLOWED_MIME=("text/html","application/xhtml+xml")
ALLOWED_ENCODINGS=("identity",)

@dataclass(frozen=True)
class ScriptedResponse:
    url: str
    status: int
    content_type: str
    final_url: str
    body: bytes
    content_encoding: str = "identity"
    transfer_redirect_count: int = 0

def verify_envelope(channel, expected_url, response):
    """Validate exact URL, content bytes, response metadata without network."""
    if not strict_official_url(channel, expected_url):
        raise ValueError("unverified_official_endpoint")
    if not isinstance(response,ScriptedResponse):
        raise ValueError("unknown_http_envelope_type")
    if response.url!=expected_url or response.final_url!=expected_url:
        raise ValueError("unexpected_redirect_or_response_url")
    if type(response.transfer_redirect_count) is not int or response.transfer_redirect_count!=0:
        raise ValueError("redirect_forbidden")
    if type(response.status) is not int or response.status!=200:
        raise ValueError("http_non_success")
    if not isinstance(response.body,bytes) or not 0<len(response.body)<=MAX_SOURCE_BYTES:
        raise ValueError("source_body_size_invalid")
    if not isinstance(response.content_type,str):
        raise ValueError("invalid_content_type")
    mime=response.content_type.split(";",1)[0].strip().lower()
    if mime not in ALLOWED_MIME:
        raise ValueError("unexpected_content_type")
    if response.content_encoding.lower() not in ALLOWED_ENCODINGS:
        raise ValueError("compressed_or_ambiguous_encoding_forbidden")
    if b"\x00" in response.body:
        raise ValueError("null_byte_in_html")
    digest=sha256(response.body).hexdigest()
    return Response(body=response.body,status=200,
                    content_type=mime,final_url=expected_url),{
                        "sha256":digest,"size":len(response.body),
                        "mime":mime,"redirect_count":0,"network_requests":0}

class ScriptedOfflineTransport:
    """A fixed in-memory fixture transport, never fetching remote content.

    The mapping is copied to prevent a mutable external dict from swapping
    a response after this instance is created. A single response key is used
    only once within this transport instance.
    """
    offline_replay_only=True
    def __init__(self,responses):
        if not isinstance(responses,dict):
            raise ValueError("fixtures_must_be_dict")
        if not all(isinstance(k,tuple) and len(k)==2
                   and isinstance(k[0],str) and isinstance(k[1],str)
                   and isinstance(v,ScriptedResponse)
                   for k,v in responses.items()):
            raise ValueError("invalid_fixture_map")
        self._responses=MappingProxyType(dict(responses))
        self._seen=set()
        self.audit=[]
    def __call__(self,channel,url):
        key=(channel,url)
        if key in self._seen:
            raise ValueError("scripted_transport_duplicate_attempt")
        self._seen.add(key)
        if key not in self._responses:
            raise ValueError("no_offline_fixture_for_url")
        response,meta=verify_envelope(channel,url,self._responses[key])
        self.audit.append({"channel":channel,"url_sha256":sha256(url.encode()).hexdigest(),**meta})
        return response

def build_live_network_transport(*_args,**_kwargs):
    """Explicitly unavailable until separate official permission and live gate."""
    raise LiveNetworkDisabled("real_http_transport_still_disabled")
