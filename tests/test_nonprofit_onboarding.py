from typing import Any, Mapping

from src.nonprofit_onboarding import (
    CampaignReport,
    DonorReceipt,
    NonprofitOnboarding,
    NonprofitOnboardingRequest,
    VolunteerReminder,
)


class RecordedGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def domain_get(self, domain: str) -> Mapping[str, Any]:
        self.calls.append(("domain_get", (domain,)))
        return {"zone_id": "zone_community_42"}

    def record_upsert(self, zone_id: str, name: str, content: str) -> Mapping[str, Any]:
        self.calls.append(("record_upsert", (zone_id, name, content)))
        return {}

    def domain_verify(self, domain: str) -> Mapping[str, Any]:
        self.calls.append(("domain_verify", (domain,)))
        return {}

    def user_get_by_email(self, email: str) -> Mapping[str, Any]:
        self.calls.append(("user_get_by_email", (email,)))
        return {"id": "user_42"}


def test_onboarding_releases_receipt_reminder_and_report_after_txt_verification() -> None:
    gateway = RecordedGateway()
    request = NonprofitOnboardingRequest(
        domain="kindness.org",
        administrator_email="founder@kindness.org",
        ownership_token="txt-token-42",
        receipt=DonorReceipt("Ada", 2500, "R-42"),
        reminder=VolunteerReminder("Bo", "Meal packing", "2026-10-15"),
        campaign=CampaignReport("Harvest", 2500, 8),
    )

    result = NonprofitOnboarding(gateway).complete(request)

    assert result.status == "onboarded"
    assert result.donor_receipt.receipt_number == "R-42"
    assert result.volunteer_reminder.event_name == "Meal packing"
    assert result.campaign_report.volunteer_hours == 8
    assert gateway.calls == [
        ("domain_get", ("kindness.org",)),
        ("record_upsert", ("zone_community_42", "_nonprofit-ownership", "txt-token-42")),
        ("domain_verify", ("kindness.org",)),
        ("user_get_by_email", ("founder@kindness.org",)),
    ]
