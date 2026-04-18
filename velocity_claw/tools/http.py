import requests
from typing import Dict, Optional


class HTTPTool:
    def get(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None, timeout: int = 30) -> Dict:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        return {"status_code": response.status_code, "body": response.text}

    def post(self, url: str, json_payload: Dict, headers: Optional[Dict] = None, timeout: int = 30) -> Dict:
        response = requests.post(url, json=json_payload, headers=headers, timeout=timeout)
        return {"status_code": response.status_code, "body": response.text}
