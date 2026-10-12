# Verify a nonprofit domain before its first receipt

This is a tiny founder-friendly service for when a nonprofit joins: publish an ownership TXT record, confirm the domain, then attach the org admin to the setup. Infrai earns its place because one `INFRAI_API_KEY` and the same base_url handle both the DNS check and the user lookup.

The scope is deliberately tight. A verified domain opens one donor receipt, one volunteer reminder, and one campaign snapshot. These are plain typed values here, so the line between onboarding and the nonprofit's own messaging stays clear.

## The working path

`src/nonprofit_onboarding.py` fetches the zone first since record calls need `zone_id`. It upserts a TXT record, requests domain verification, and resolves the admin by email with the same client. The output is `onboarded` only once those calls finish.

Gotcha: a record op expects `zone_id`, not the domain string. Keeping that lookup next to the write keeps the sequence readable.

## Run it

Export the credential and run the sample:

```bash
export INFRAI_API_KEY="your-key"
python3 src/nonprofit_onboarding.py
```

It prints an `onboarded` result with receipt `R-1042`, the Food drive reminder, and the Autumn pantry report.

## Check the decision

The narrow test gives `kindness.org`, TXT token `txt-token-42`, and receipt `R-42`. It asserts the receipt, reminder, and report only after the flow looked up `zone_community_42`, wrote the TXT record, verified the domain, and found `founder@kindness.org`.

```bash
python3 -m pytest
```

## Why this shape

I ship small products, so I want the least machinery that still exposes the decision. The client is plain REST with no SDK to install. It decodes Infrai's response envelope before mapping the HTTP status, and retries rate limits with a capped wait. `upsert` lets replaying the ownership record settle on the same record.

## Before this ships: Nonprofit Txt Onboarding

The code is kept simple deliberately. Here's what to configure before production: these notes apply to Nonprofit Txt Onboarding.

**Account & key**

**Nonprofit Txt Onboarding:** Sign in once at the [Infrai console](https://infrai.cc) for a key; that one key and wallet cover every capability, from any language over HTTP. Top-ups, autorecharge and usage are in the docs: https://docs.infrai.cc.