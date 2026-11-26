"""Integer calculations for the D-07 FUNCTIONAL_TEST referral policy."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureFunding:
    promotional: int
    referral: int
    paid: int
    unknown_legacy: int

    def __post_init__(self):
        if any(type(amount) is not int or amount < 0 for amount in self.amounts):
            raise ValueError("funding amounts must be nonnegative integers")

    @property
    def amounts(self) -> tuple[int, int, int, int]:
        return self.promotional, self.referral, self.paid, self.unknown_legacy


def cumulative_refund(capture: CaptureFunding, returned: int) -> CaptureFunding:
    """Allocate a cumulative refund using highest averages and stable category order.

    Each category contributes a sequence with priorities weight/1, weight/2,
    and so on, stopping at its original capture. A larger refund takes a
    longer prefix of the same merged sequence. All entries at or above
    total/returned can be counted in bulk using integer division.
    """
    weights = capture.amounts
    total = sum(weights)
    if type(returned) is not int or not 0 <= returned <= total:
        raise ValueError("cumulative refund exceeds capture or is invalid")
    if not returned:
        return CaptureFunding(0, 0, 0, 0)

    allocated = [returned * weight // total for weight in weights]
    for _ in range(returned - sum(allocated)):
        best = None
        for index, weight in enumerate(weights):
            if allocated[index] == weight:
                continue
            if best is None or weight * (allocated[best] + 1) > weights[best] * (allocated[index] + 1):
                best = index
        allocated[best] += 1
    return CaptureFunding(*allocated)


def reward_tokens(capture: CaptureFunding, returned: int, rate_bps: int) -> int:
    """Recalculate the allowed reward from the original eligible paid amount."""
    if type(rate_bps) is not int or not 0 <= rate_bps <= 10_000:
        raise ValueError("invalid basis point rate")
    refunded = cumulative_refund(capture, returned)
    return (capture.paid - refunded.paid) * rate_bps // 10_000


def allocate_reserve(available: CaptureFunding, amount: int) -> CaptureFunding:
    """Select sources in approved spend order from a locked balance snapshot."""
    if type(amount) is not int or not 0 <= amount <= sum(available.amounts):
        raise ValueError("reserve exceeds available funds or is invalid")
    allocations = []
    for balance in available.amounts:
        used = min(balance, amount)
        allocations.append(used)
        amount -= used
    return CaptureFunding(*allocations)
