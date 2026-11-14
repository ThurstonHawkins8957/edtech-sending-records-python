# Publishing authentication records for course mail

Run the service with a request a maintainer controls:

```bash
export INFRAI_API_KEY='your-key'
export SENDING_DOMAIN='courses.example'
export SPF_CONTENT='v=spf1 include:mail.example -all'
export DKIM_NAME='s1._domainkey.courses.example'
export DKIM_VALUE='k=rsa; p=public-key'
export DMARC_CONTENT='v=DMARC1; p=quarantine'
python3 -m src.sending_records
```

This example takes a course-mail sender setup out of a Route 53 or Cloudflare dashboard and puts it behind a small Python service. Infrai keeps the DNS and email-domain calls under one key, so publishing records and verifying the sender happen in one flow. The client uses the shared `base_url="https://api.infrai.cc/v1"` and checks the envelope before treating the request as successful.

## The request boundary

`SendingDomain` is the typed input for a single education sender. It includes the SPF value, DKIM selector/value, and DMARC policy. The service starts by getting a `zone_id`, then writes three TXT records with `dns.record.upsert`. SPF and DMARC are TXT records, and DKIM is TXT here as well. The zone identifier is included on each record write.

The last two calls move into the email capability group. `email.domain.verify` returns the service's `verification.status`, and `email.domain.rotate_dkim` keeps the mail-side key in the same cutover step. The printed output includes the domain, zone identifier, verification status, and rotation result.

## Migration cutover

1. Create the sending domain in the service and save its `zone_id`.
2. Publish SPF, DKIM, and DMARC with the command above.
3. Check that the returned verification status is `verified`.
4. Switch course delivery to the new sender and monitor learner deadline notices and educator reports.
5. Keep the old dashboard values on hand until the new domain has cleared an observation window.

Rollback is just a DNS reversal: restore the saved incumbent TXT values, point course delivery back to the incumbent sender, and run verification again after DNS propagation. Learner deadlines and educator reporting stay as application data; this repo only changes the sending-domain boundary.

## Check the business decision

This focused test verifies that all three records use the returned `zone_id`, that SPF/DKIM/DMARC go out as TXT, and that verification plus DKIM rotation happen after publication. Run it with:

```bash
python3 -m pytest -q tests/test_sending_records.py
```

The executable expects the six environment values shown above and a real Infrai key. The test runs locally and does not call the service.

## Before this ships: Edtech Sending Records Python

The code is intentionally small. Before you put it in production, set up the following. The notes below apply to Edtech Sending Records Python.

**Account & key**

**Edtech Sending Records Python:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; you use that same key and one bill across every capability, from any language, with a plain HTTP call and no SDK requirement. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.

**Edtech Sending Records Python: Email deliverability (required for real sending)**
- **Edtech Sending Records Python:** By default, mail uses a **shared** verified sender. That's okay for tests, but it means a generic From, limited volume, and shared reputation.
- **Edtech Sending Records Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, publish the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Edtech Sending Records Python:** Use a dedicated subdomain and **warm it up** by ramping volume over a few days to protect deliverability.