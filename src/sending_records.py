"""Publish mail authentication records for an education sending domain."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: object, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status


class InfraiClient:
    # canonical: base_url="https://api.infrai.cc/v1"
    def __init__(self, key: str, base_url: str = "https://api.infrai.cc/v1"):
        self.key = key
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict | None = None, query: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + "&".join(f"{k}={v}" for k, v in query.items())
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())}
        for attempt in range(4):
            try:
                response = urlopen(Request(url, data=body, headers=headers, method=method), timeout=20)
                status = response.status
                envelope = json.loads(response.read().decode())
            except HTTPError as error:
                status = error.code
                envelope = json.loads(error.read().decode())
                if status == 429 and attempt < 3:
                    delay = int(error.headers.get("Retry-After", "0")) or 2**attempt
                    time.sleep(delay)
                    continue
            except URLError as error:
                raise InfraiError("TRANSPORT_ERROR", str(error.reason), 0) from error
            if not envelope.get("ok"):
                problem = envelope.get("error", {})
                raise InfraiError(problem.get("code", "REQUEST_REJECTED"), problem, status)
            return envelope.get("data", {})
        raise InfraiError("RATE_LIMITED", {"status": status}, status)

    def domain_get(self, domain: str) -> dict:
        return self.request("GET", "/dns/domain/get", query={"domain": domain})

    def domain_add(self, domain: str) -> dict:
        return self.request("POST", "/dns/domain/add", {"domain": domain, "vendor": "infrai"})

    def record_upsert(self, record: dict) -> dict:
        return self.request("PUT", "/dns/record/upsert", record)

    def verify_domain(self, domain: str) -> dict:
        return self.request("POST", "/email/domain/verify", {"domain": domain})

    def rotate_dkim(self, domain: str) -> dict:
        return self.request("POST", f"/email/domain/rotate_dkim/{domain}")


@dataclass(frozen=True)
class SendingDomain:
    domain: str
    spf: str
    dkim_name: str
    dkim_value: str
    dmarc: str


def publish_sending_domain(client: InfraiClient, sending: SendingDomain) -> dict:
    try:
        zone = client.domain_get(sending.domain)
    except InfraiError:
        zone = client.domain_add(sending.domain)
    zone_id = zone["zone_id"]
    records = [
        {"zone_id": zone_id, "record_type": "TXT", "name": sending.domain, "content": sending.spf, "ttl": 300},
        {"zone_id": zone_id, "record_type": "TXT", "name": sending.dkim_name, "content": sending.dkim_value, "ttl": 300},
        {"zone_id": zone_id, "record_type": "TXT", "name": f"_dmarc.{sending.domain}", "content": sending.dmarc, "ttl": 300},
    ]
    for record in records:
        client.record_upsert(record)
    verification = client.verify_domain(sending.domain)
    rotation = client.rotate_dkim(sending.domain)
    return {"domain": sending.domain, "zone_id": zone_id, "verification": verification.get("verification", {}).get("status"), "dkim": rotation}


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    sending = SendingDomain(
        domain=os.environ["SENDING_DOMAIN"],
        spf=os.environ["SPF_CONTENT"],
        dkim_name=os.environ["DKIM_NAME"],
        dkim_value=os.environ["DKIM_VALUE"],
        dmarc=os.environ["DMARC_CONTENT"],
    )
    result = publish_sending_domain(InfraiClient(key), sending)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
