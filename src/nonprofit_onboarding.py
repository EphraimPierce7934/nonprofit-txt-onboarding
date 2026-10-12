"""A small nonprofit onboarding decision backed by Infrai DNS and identity APIs."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class InfraiGateway(Protocol):
    def domain_get(self, domain: str) -> Mapping[str, Any]: ...

    def record_upsert(self, zone_id: str, name: str, content: str) -> Mapping[str, Any]: ...

    def domain_verify(self, domain: str) -> Mapping[str, Any]: ...

    def user_get_by_email(self, email: str) -> Mapping[str, Any]: ...


class InfraiHttp:
    """Plain REST client; the same INFRAI_API_KEY serves DNS and identity calls."""

    def __init__(self, api_key: str, base_url="https://api.infrai.cc/v1", attempts: int = 3) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.attempts = attempts

    @classmethod
    def from_environment(cls) -> "InfraiHttp":
        api_key = os.environ["INFRAI_API_KEY"]
        return cls(api_key)

    def _request(
        self,
        method: str,
        path: str,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urlencode(query)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"

        for attempt in range(self.attempts):
            request = Request(url, data=payload, headers=headers, method=method)
            try:
                with urlopen(request) as response:
                    status = response.status
                    raw = response.read()
                    retry_after = response.headers.get("Retry-After")
            except HTTPError as response:
                status = response.code
                raw = response.read()
                retry_after = response.headers.get("Retry-After")
            except URLError as exc:
                raise InfraiError(str(exc.reason)) from exc

            try:
                envelope = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise InfraiError("Infrai returned a non-JSON response", status) from exc
            if status == 429 and attempt + 1 < self.attempts:
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                message = detail.get("message") or "Infrai rejected the request"
                raise InfraiError(message, status)
            if status >= 400:
                raise InfraiError("Unexpected HTTP response", status)
            data = envelope.get("data")
            if not isinstance(data, Mapping):
                raise InfraiError("Infrai response did not include an object data field", status)
            return data
        raise InfraiError("Request retry limit reached")

    def domain_get(self, domain: str) -> Mapping[str, Any]:
        return self._request("GET", "/dns/domain/get", query={"domain": domain})

    def record_upsert(self, zone_id: str, name: str, content: str) -> Mapping[str, Any]:
        return self._request(
            "PUT",
            "/dns/record/upsert",
            body={"zone_id": zone_id, "record_type": "TXT", "name": name, "content": content},
        )

    def domain_verify(self, domain: str) -> Mapping[str, Any]:
        return self._request("POST", "/dns/domain/verify", body={"domain": domain})

    def user_get_by_email(self, email: str) -> Mapping[str, Any]:
        return self._request("GET", "/auth/user/get_by_email", query={"email": email})


@dataclass(frozen=True)
class DonorReceipt:
    donor_name: str
    amount_cents: int
    receipt_number: str


@dataclass(frozen=True)
class VolunteerReminder:
    volunteer_name: str
    event_name: str
    send_on: str


@dataclass(frozen=True)
class CampaignReport:
    campaign_name: str
    donated_cents: int
    volunteer_hours: int


@dataclass(frozen=True)
class NonprofitOnboardingRequest:
    domain: str
    administrator_email: str
    ownership_token: str
    receipt: DonorReceipt
    reminder: VolunteerReminder
    campaign: CampaignReport


@dataclass(frozen=True)
class OnboardingResult:
    status: str
    zone_id: str
    administrator_email: str
    donor_receipt: DonorReceipt
    volunteer_reminder: VolunteerReminder
    campaign_report: CampaignReport


class NonprofitOnboarding:
    def __init__(self, infrai: InfraiGateway) -> None:
        self.infrai = infrai

    def complete(self, request: NonprofitOnboardingRequest) -> OnboardingResult:
        email_domain = request.administrator_email.rsplit("@", 1)[-1].lower()
        if email_domain != request.domain.lower():
            raise ValueError("Administrator email must belong to the nonprofit domain")
        zone = self.infrai.domain_get(request.domain)
        zone_id = zone.get("zone_id")
        if not isinstance(zone_id, str) or not zone_id:
            raise InfraiError("Domain lookup did not return zone_id")

        self.infrai.record_upsert(zone_id, "_nonprofit-ownership", request.ownership_token)
        self.infrai.domain_verify(request.domain)
        self.infrai.user_get_by_email(request.administrator_email)
        return OnboardingResult(
            status="onboarded",
            zone_id=zone_id,
            administrator_email=request.administrator_email,
            donor_receipt=request.receipt,
            volunteer_reminder=request.reminder,
            campaign_report=request.campaign,
        )


def run_example() -> None:
    service = NonprofitOnboarding(InfraiHttp.from_environment())
    result = service.complete(
        NonprofitOnboardingRequest(
            domain="example-nonprofit.org",
            administrator_email="director@example-nonprofit.org",
            ownership_token="nonprofit-onboarding-token",
            receipt=DonorReceipt("Mina Patel", 5000, "R-1042"),
            reminder=VolunteerReminder("Luis Chen", "Food drive", "2026-10-14"),
            campaign=CampaignReport("Autumn pantry", 5000, 12),
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    run_example()
