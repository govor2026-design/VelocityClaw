import aiohttp
from typing import Dict, Optional
from urllib.parse import urlparse
from velocity_claw.config.settings import Settings


class HTTPTool:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.timeout = aiohttp.ClientTimeout(total=60)

    def _validate_url(self, url: str) -> str:
        """Validate URL against allowlist."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ["http", "https"]:
                raise ValueError(f"Unsupported scheme: {parsed.scheme}")
            if parsed.hostname not in self.settings.allowed_hosts:
                raise ValueError(f"Host not allowed: {parsed.hostname}")
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")
        return url

    async def get(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        validated_url = self._validate_url(url)
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(validated_url, headers=headers, params=params) as response:
                    response.raise_for_status()

                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > self.settings.max_http_response_bytes:
                        raise ValueError(f"Response too large: {content_length}")

                    content = b""
                    async for chunk in response.content.iter_chunked(8192):
                        content += chunk
                        if len(content) > self.settings.max_http_response_bytes:
                            raise ValueError(f"Response exceeded size limit: {len(content)}")

                    try:
                        text = content.decode("utf-8")
                    except UnicodeDecodeError:
                        raise ValueError("Binary response not supported")

                    return {
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": text
                    }
        except aiohttp.ClientError as e:
            raise RuntimeError(f"HTTP request failed: {e}")

    async def post(self, url: str, json_payload: Dict, headers: Optional[Dict] = None) -> Dict:
        validated_url = self._validate_url(url)
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(validated_url, json=json_payload, headers=headers) as response:
                    response.raise_for_status()

                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > self.settings.max_http_response_bytes:
                        raise ValueError(f"Response too large: {content_length}")

                    content = b""
                    async for chunk in response.content.iter_chunked(8192):
                        content += chunk
                        if len(content) > self.settings.max_http_response_bytes:
                            raise ValueError(f"Response exceeded size limit: {len(content)}")

                    try:
                        text = content.decode("utf-8")
                    except UnicodeDecodeError:
                        raise ValueError("Binary response not supported")

                    return {
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": text
                    }
        except aiohttp.ClientError as e:
            raise RuntimeError(f"HTTP request failed: {e}")
