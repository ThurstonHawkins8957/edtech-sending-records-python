import pytest

from src.sending_records import InfraiClient, SendingDomain, publish_sending_domain


class FakeClient(InfraiClient):
    def __init__(self):
        super().__init__("test-key", "https://example.test")
        self.calls = []

    def domain_get(self, domain):
        self.calls.append(("GET", domain))
        return {"zone_id": "zone-42"}

    def record_upsert(self, record):
        self.calls.append(("PUT", record))
        return {}

    def verify_domain(self, domain):
        self.calls.append(("POST verify", domain))
        return {"verification": {"status": "verified"}}

    def rotate_dkim(self, domain):
        self.calls.append(("POST rotate", domain))
        return {"status": "rotated"}


def test_publish_uses_zone_id_and_verifies_after_three_records():
    client = FakeClient()
    sending = SendingDomain("courses.example", "v=spf1 include:mail.example -all", "s1._domainkey.courses.example", "k=rsa; p=public", "v=DMARC1; p=quarantine")

    result = publish_sending_domain(client, sending)

    records = [call[1] for call in client.calls if call[0] == "PUT"]
    assert result["verification"] == "verified"
    assert [record["record_type"] for record in records] == ["TXT", "TXT", "TXT"]
    assert all(record["zone_id"] == "zone-42" for record in records)
    assert client.calls[-2:] == [("POST verify", "courses.example"), ("POST rotate", "courses.example")]
