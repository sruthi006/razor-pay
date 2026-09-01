"""Decline/error taxonomy grounded in Razorpay public documentation.

Razorpay error objects include ``code``, ``description``, ``source``, ``step``,
and ``reason`` (see https://razorpay.com/docs/errors/).

This module keys off the documented ``reason`` strings. Names are copied from:

- https://razorpay.com/docs/errors/reasons/
- https://razorpay.com/docs/errors/payments/cards/

We do **not** invent Razorpay-specific reason strings.

Retry categories (SOFT_RETRY / HARD_FAILURE / DO_NOT_RETRY) and synthetic
retry behaviour are **prototype policy**, except where public docs explicitly
tell the customer to retry after some time. See each catalog entry's
``classification_note``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# Public Razorpay docs used as the source of truth for reason *names* and
# human-readable descriptions. Retry policy is mostly this project's.
RAZORPAY_ERROR_DOCS = "https://razorpay.com/docs/errors/"
RAZORPAY_REASON_DOCS = "https://razorpay.com/docs/errors/reasons/"
RAZORPAY_CARDS_ERROR_DOCS = "https://razorpay.com/docs/errors/payments/cards/"
RAZORPAY_SOURCE_STEP_DOCS = (
    "https://razorpay.com/docs/errors/payments/payment-methods-error-parameters/"
)


class RetryCategory(str, Enum):
    """Prototype retry bucket. Not a Razorpay API field."""

    SOFT_RETRY = "SOFT_RETRY"
    HARD_FAILURE = "HARD_FAILURE"
    DO_NOT_RETRY = "DO_NOT_RETRY"


class Retryability(str, Enum):
    """Whether the prototype may automatically retry this reason."""

    ELIGIBLE = "eligible"  # SOFT_RETRY: timing optimization is in scope
    LIMITED = "limited"  # HARD_FAILURE: at most a small cap, no timing hunt
    EXCLUDED = "excluded"  # DO_NOT_RETRY: no automatic retry


# Documented card ``source`` values: customer, business, internal, gateway, issuer_bank.
# Per-reason source below is inferred from public explanations when Razorpay
# does not publish a 1:1 reason→source table. Marked on each row.
class SourceCategory(str, Enum):
    CUSTOMER = "customer"
    BUSINESS = "business"
    INTERNAL = "internal"
    GATEWAY = "gateway"
    ISSUER_BANK = "issuer_bank"
    MIXED = "mixed"  # docs say source can be Razorpay, gateway, or issuer


@dataclass(frozen=True)
class DeclineReason:
    """One documented payment failure reason plus prototype retry policy."""

    reason: str
    human_readable_description: str
    source_category: SourceCategory
    retry_category: RetryCategory
    retryability: Retryability
    synthetic_retry_behavior: str
    classification_note: str
    source_inference_note: str


def _entry(
    reason: str,
    description: str,
    source_category: SourceCategory,
    retry_category: RetryCategory,
    synthetic_retry_behavior: str,
    classification_note: str,
    source_inference_note: str,
) -> DeclineReason:
    retryability = {
        RetryCategory.SOFT_RETRY: Retryability.ELIGIBLE,
        RetryCategory.HARD_FAILURE: Retryability.LIMITED,
        RetryCategory.DO_NOT_RETRY: Retryability.EXCLUDED,
    }[retry_category]
    return DeclineReason(
        reason=reason,
        human_readable_description=description,
        source_category=source_category,
        retry_category=retry_category,
        retryability=retryability,
        synthetic_retry_behavior=synthetic_retry_behavior,
        classification_note=classification_note,
        source_inference_note=source_inference_note,
    )


# ---------------------------------------------------------------------------
# Catalog: reason *names* and descriptions from public docs.
# Retry categories: prototype unless classification_note says otherwise.
# ---------------------------------------------------------------------------

DECLINE_REASONS: tuple[DeclineReason, ...] = (
    _entry(
        reason="insufficient_funds",
        description=(
            "The customer does not have sufficient funds in the account to "
            "complete the payment."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "Same-instrument retry may succeed after plausible balance "
            "replenishment (later the same day, next morning, or around "
            "typical salary/credit windows). Higher amounts recover less often. "
            "Noise around those peaks so the label is not a step function."
        ),
        classification_note=(
            "DOCUMENTATION: reason name and description from Razorpay error "
            "reasons / cards error pages. Docs next step is retry with a "
            "different card or method, not 'retry the same card later'. "
            "SYNTHETIC BUSINESS RULE: treat as SOFT_RETRY because balance can "
            "change over time; timing optimization is a project assumption."
        ),
        source_inference_note=(
            "INFERRED: issuer/account balance check. Razorpay does not publish "
            "a fixed source for this reason in the cards source list."
        ),
    ),
    _entry(
        reason="card_declined",
        description=(
            "The issuer declined the card; the exact check is not shared with "
            "Razorpay. Customer is advised to contact the issuing bank."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "Opaque mix of temporary and permanent issuer checks. Modest, "
            "weakly time-dependent recovery; most retries still fail. Do not "
            "encode a sharp 'best hour'."
        ),
        classification_note=(
            "DOCUMENTATION: opaque issuer decline; try another card / contact "
            "bank. SYNTHETIC BUSINESS RULE: SOFT_RETRY with low recovery so "
            "the model can learn that this reason is weakly informative, not "
            "that Razorpay recommends delayed same-card retries."
        ),
        source_inference_note="INFERRED from docs: issuer bank declined.",
    ),
    _entry(
        reason="payment_timed_out",
        description=(
            "The customer did not complete the transaction within the specified "
            "time (cards docs: typically ~10 minutes). Docs also note this may "
            "occur when no response is received from the gateway."
        ),
        source_category=SourceCategory.MIXED,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "If the latent cause is gateway non-response, a relatively soon "
            "retry can succeed. If the latent cause is customer abandonment, "
            "merchant-initiated retry of the same attempt rarely succeeds. "
            "Generator should mix both latent causes."
        ),
        classification_note=(
            "DOCUMENTATION: customer must retry / complete within the time; "
            "gateway non-response is also mentioned. SYNTHETIC BUSINESS RULE: "
            "SOFT_RETRY for a merchant smart-retry engine; docs describe a "
            "customer retry, not a timed merchant policy."
        ),
        source_inference_note=(
            "INFERRED MIXED: customer timeout vs gateway silence, per docs."
        ),
    ),
    _entry(
        reason="gateway_technical_error",
        description=(
            "Payment failed due to a technical error at the gateway "
            "(cards docs also describe partner-bank/gateway downtime)."
        ),
        source_category=SourceCategory.GATEWAY,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "Recovery probability highest on a short delay (minutes to a few "
            "hours) and decays as the outage is either cleared or still down. "
            "Long waits (48–72h) are not systematically better than 1–6h."
        ),
        classification_note=(
            "DOCUMENTATION: error reasons page says retry with a different "
            "method or retry after some time. Closest public-doc support for "
            "time-based retry. SYNTHETIC: the exact delay curve is ours."
        ),
        source_inference_note="Aligned with documented source 'gateway'.",
    ),
    _entry(
        reason="bank_technical_error",
        description=(
            "Issuing bank technical problems (e.g. core banking) at the moment "
            "the payment was attempted. Cards docs: customer bank downtime."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "Similar to gateway technical errors: better soon after failure "
            "than at a fixed T+3d, with noise. Slightly slower recovery than "
            "gateway errors (issuer CBS)."
        ),
        classification_note=(
            "DOCUMENTATION: description and 'try another bank/method'. "
            "SYNTHETIC BUSINESS RULE: SOFT_RETRY via waiting for downtime to "
            "clear; docs do not specify an optimal delay."
        ),
        source_inference_note="INFERRED: issuer_bank from 'issuing bank' wording.",
    ),
    _entry(
        reason="issuer_technical_error",
        description=(
            "Payment failed due to a technical error at the issuer; docs advise "
            "retry with a different method or retry after some time."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "Treat like bank_technical_error: elevated short-horizon recovery, "
            "decaying with time, plus noise."
        ),
        classification_note=(
            "DOCUMENTATION: 'retry after some time' on the error reasons page. "
            "SYNTHETIC: delay distribution is a project assumption."
        ),
        source_inference_note="INFERRED: issuer_bank from reason name and docs.",
    ),
    _entry(
        reason="payment_declined_due_to_high_traffic",
        description=(
            "Bank unable to serve requests in high-TPS scenarios; customer "
            "must retry."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "Load sheds; retries in the next 15 minutes–2 hours work more "
            "often than 48–72h (when the spike is over, waiting longer adds "
            "little). Keep recovery only moderately high."
        ),
        classification_note=(
            "DOCUMENTATION: customer must retry. SYNTHETIC: which delay is "
            "best is a project assumption, not a Razorpay SLA."
        ),
        source_inference_note="INFERRED: issuer/bank capacity from docs.",
    ),
    _entry(
        reason="transaction_limit_exceeded",
        description=(
            "Customer exceeded the credit or debit limit set on the card; "
            "often seen on high-value transactions."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "Same-card retry after a long wait only rarely helps (limit may "
            "be a hard credit cap, not a daily reset). Slightly better at "
            "+24h/+48h than +15m. Lower success for larger amount_inr."
        ),
        classification_note=(
            "DOCUMENTATION: use a different bank card or method. "
            "SYNTHETIC BUSINESS RULE: still SOFT_RETRY with low, weakly "
            "time-dependent recovery. Distinct from "
            "transaction_daily_limit_exceeded, which docs mention waiting 24h."
        ),
        source_inference_note="INFERRED: issuer-enforced card limit.",
    ),
    _entry(
        reason="transaction_daily_limit_exceeded",
        description=(
            "Customer exceeded the daily transaction limit on the card "
            "(customer-set or default)."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "Recovery rises sharply once hours_since_failure crosses ~24h "
            "(and is low before that), matching the public 'wait 24 hours' "
            "next step. Still add noise; not every +24h retry succeeds."
        ),
        classification_note=(
            "DOCUMENTATION: retry using a different instrument OR wait 24 "
            "hours. Partial public-doc support for a ~24h delay. SYNTHETIC: "
            "the success curve around 24h is generated by us."
        ),
        source_inference_note="INFERRED: issuer_bank card controls.",
    ),
    _entry(
        reason="server_error",
        description="Technical error at Razorpay's server.",
        source_category=SourceCategory.INTERNAL,
        retry_category=RetryCategory.SOFT_RETRY,
        synthetic_retry_behavior=(
            "Short-delay retries recover more often; long delays are not "
            "better. Keep this a small share of rows."
        ),
        classification_note=(
            "DOCUMENTATION: retry after some time or contact Razorpay. "
            "SYNTHETIC: delay curve is ours."
        ),
        source_inference_note="Docs: Razorpay server → source internal.",
    ),
    _entry(
        reason="card_expired",
        description="The customer is making the payment with an expired card.",
        source_category=SourceCategory.CUSTOMER,
        retry_category=RetryCategory.HARD_FAILURE,
        synthetic_retry_behavior=(
            "Timing does not un-expire a card. Retry success ≈ near-zero "
            "regardless of candidate_retry_hours. Residual successes only as "
            "rare noise (e.g. mislabelled reason)."
        ),
        classification_note=(
            "DOCUMENTATION: use a different / active card. Timing cannot fix "
            "expiry → HARD_FAILURE. Not DO_NOT_RETRY: docs do not forbid a "
            "retry; they require a different instrument, which this engine "
            "does not switch. SYNTHETIC: we cap retries instead of excluding."
        ),
        source_inference_note=(
            "INFERRED: customer instrument state (could also be issuer). "
            "Using documented source value 'customer'."
        ),
    ),
    _entry(
        reason="incorrect_cvv",
        description="The customer entered an incorrect CVV.",
        source_category=SourceCategory.CUSTOMER,
        retry_category=RetryCategory.HARD_FAILURE,
        synthetic_retry_behavior=(
            "Same stored CVV will fail again. Timing does not help. Near-zero "
            "retry_success except rare noise."
        ),
        classification_note=(
            "DOCUMENTATION: retry with the correct CVV. HARD_FAILURE for "
            "unattended same-credential retry. SYNTHETIC: automatic retry "
            "policy; docs assume the customer types a new CVV."
        ),
        source_inference_note="Docs imply customer-entered data → customer.",
    ),
    _entry(
        reason="incorrect_card_details",
        description=(
            "Generic incorrect card details (name, expiry, CVV, etc.)."
        ),
        source_category=SourceCategory.CUSTOMER,
        retry_category=RetryCategory.HARD_FAILURE,
        synthetic_retry_behavior=(
            "Same as incorrect_cvv: near-zero recovery from delay alone."
        ),
        classification_note=(
            "DOCUMENTATION: customer must use correct details. HARD_FAILURE "
            "for unattended retries. SYNTHETIC policy, not a Razorpay "
            "do-not-retry flag."
        ),
        source_inference_note="Docs: customer-entered details → customer.",
    ),
    _entry(
        reason="debit_instrument_inactive",
        description=(
            "Inactive or frozen card; issuer or customer may have marked it "
            "inactive. Cards docs also cover cards not enabled for online use."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.HARD_FAILURE,
        synthetic_retry_behavior=(
            "Activation is a customer/bank action, not a function of our "
            "retry clock. Very low recovery across the candidate grid."
        ),
        classification_note=(
            "DOCUMENTATION: different card/method or activate the card. "
            "HARD_FAILURE because waiting on our grid does not activate the "
            "card. Not DO_NOT_RETRY: docs do not say never retry."
        ),
        source_inference_note="INFERRED: issuer or customer; using issuer_bank.",
    ),
    _entry(
        reason="card_not_enrolled",
        description=(
            "Card not enrolled for 3-D Secure, or issuer does not support 3DS."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.HARD_FAILURE,
        synthetic_retry_behavior=(
            "Enrollment is off-clock. Near-zero recovery vs candidate time."
        ),
        classification_note=(
            "DOCUMENTATION: enroll then retry, or use another card. "
            "HARD_FAILURE for timing-only retries. SYNTHETIC cap, not a "
            "Razorpay never-retry rule."
        ),
        source_inference_note="INFERRED: issuer enrollment / 3DS support.",
    ),
    _entry(
        reason="debit_instrument_blocked",
        description=(
            "Blocked card (issuer or customer). Docs: retry with a different "
            "card or method; contact bank to unblock."
        ),
        source_category=SourceCategory.ISSUER_BANK,
        retry_category=RetryCategory.HARD_FAILURE,
        synthetic_retry_behavior=(
            "Unblock is not driven by our candidate hours. Near-zero recovery. "
            "Do not treat as fraud by default."
        ),
        classification_note=(
            "DOCUMENTATION: blocked instrument; use another card. "
            "HARD_FAILURE, not DO_NOT_RETRY: public docs do not say the "
            "payment must never be retried, and a block is not automatically "
            "a fraud decision. SYNTHETIC: limited retries, no timing hunt."
        ),
        source_inference_note="INFERRED: issuer or customer block → issuer_bank.",
    ),
    _entry(
        reason="payment_cancelled",
        description=(
            "Customer explicitly cancelled the payment (or used back) so "
            "authentication did not complete."
        ),
        source_category=SourceCategory.CUSTOMER,
        retry_category=RetryCategory.HARD_FAILURE,
        synthetic_retry_behavior=(
            "Merchant auto-retry without a new customer intent rarely "
            "succeeds. Near-zero vs time."
        ),
        classification_note=(
            "DOCUMENTATION: customer cancelled; customer must retry. "
            "HARD_FAILURE for unattended merchant retry. Not DO_NOT_RETRY: "
            "docs invite a customer retry, they do not forbid one. SYNTHETIC: "
            "we do not hunt for a 'best hour' after cancel."
        ),
        source_inference_note="Docs: customer cancelled → customer.",
    ),
    _entry(
        reason="payment_risk_check_failed",
        description=(
            "Payment declined due to risk checks performed by Razorpay, the "
            "gateway, and/or the issuer. Cards docs: issuer cited the payment "
            "as fraudulent. The error ``source`` field indicates where the "
            "check failed."
        ),
        source_category=SourceCategory.MIXED,
        retry_category=RetryCategory.DO_NOT_RETRY,
        synthetic_retry_behavior=(
            "Do not generate automatic retry candidates. If a row is created "
            "for completeness, retry_success should stay ~0 and the policy "
            "must not recommend a retry."
        ),
        classification_note=(
            "DOCUMENTATION: risk checks at Razorpay/gateway/issuer; next step "
            "is often a different card/method, not 'never retry'. "
            "SYNTHETIC BUSINESS RULE: DO_NOT_RETRY for automatic "
            "same-instrument retries in this prototype. This is not a "
            "documented Razorpay 'do not retry' API flag."
        ),
        source_inference_note=(
            "Docs: source can be Razorpay, gateway, or issuer → MIXED."
        ),
    ),
)

DECLINE_CATALOG: dict[str, DeclineReason] = {row.reason: row for row in DECLINE_REASONS}

# Backward-compatible alias used in Phase 0 placeholders.
DeclineBucket = RetryCategory


def get_reason(reason: str) -> DeclineReason:
    """Look up a documented reason or raise KeyError."""
    try:
        return DECLINE_CATALOG[reason]
    except KeyError as exc:
        known = ", ".join(sorted(DECLINE_CATALOG))
        raise KeyError(f"Unknown decline reason {reason!r}. Known: {known}") from exc


def retry_category_for(reason: str) -> RetryCategory:
    """Prototype retry category for a documented reason."""
    return get_reason(reason).retry_category


def bucket_for_code(decline_code: str) -> RetryCategory:
    """Alias for retry_category_for (Phase 0 name)."""
    return retry_category_for(decline_code)


def is_retry_eligible(decline_code: str) -> bool:
    """True unless the prototype marks the reason DO_NOT_RETRY / excluded.

    HARD_FAILURE is eligible only for a capped retry (see docs/business_rules.md),
    not for full candidate-time search.
    """
    return get_reason(decline_code).retryability != Retryability.EXCLUDED


def allows_timing_optimization(reason: str) -> bool:
    """Whether the smart-retry model should score a candidate time grid."""
    return get_reason(reason).retry_category == RetryCategory.SOFT_RETRY


def listed_reasons() -> list[str]:
    """Stable list of reason strings included in this prototype."""
    return [row.reason for row in DECLINE_REASONS]
