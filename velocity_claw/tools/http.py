import requests
from typing import Dict, Optional
from urllib.parse import urlparse
from velocity_claw.config.settings import Settings


class HTTPTool:
    def __init__(self, settings: Settings):
        self.settings = settings

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

    def get(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None, timeout: int = 30) -> Dict:
        validated_url = self._validate_url(url)
        try:
            response = requests.get(
                validated_url,
                headers=headers,
                params=params,
                timeout=min(timeout, 60),  # Cap at 60s
                stream=True
            )
            response.raise_for_status()

            # Check content length
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.settings.max_http_response_bytes:
                raise ValueError(f"Response too large: {content_length}")

            # Read with limit
            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > self.settings.max_http_response_bytes:
                    raise ValueError(f"Response exceeded size limit: {len(content)}")

            # Try to decode as text
            try:
                text = content.decode('utf-8')
            except UnicodeDecodeError:
                raise ValueError("Binary response not supported")

            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": text
            }
        except requests.RequestException as e:
            raise RuntimeError(f"HTTP request failed: {e}")

    def post(self, url: str, json_payload: Dict, headers: Optional[Dict] = None, timeout: int = 30) -> Dict:
        validated_url = self._validate_url(url)
        try:
            response = requests.post(
                validated_url,
                json=json_payload,
                headers=headers,
                timeout=min(timeout, 60),
                stream=True
            )
            response.raise_for_status()

            # Same size check as GET
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.settings.max_http_response_bytes:
                raise ValueError(f"Response too large: {content_length}")

            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > self.settings.max_http_response_bytes:
                    raise ValueError(f"Response exceeded size limit: {len(content)}")

            try:
                text = content.decode('utf-8')
            except UnicodeDecodeError:
                raise ValueError("Binary response not supported")

            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": text
            }
        except requests.RequestException as e:
            raise RuntimeError(f"HTTP request failed: {e}")
