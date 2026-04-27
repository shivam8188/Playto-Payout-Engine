from django.db import models
from django.db.models import Sum, Q
from django.utils import timezone
import uuid


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    bank_account_number = models.CharField(max_length=50)
    bank_ifsc = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_balance(self):
        """
        Total balance = credits - debits from ledger.
        Debit entries are created when a payout is initiated (hold),
        so this already accounts for pending payouts.
        """
        result = self.ledger_entries.aggregate(
            total_credits=Sum('amount_paise', filter=Q(entry_type='credit')),
            total_debits=Sum('amount_paise', filter=Q(entry_type='debit')),
        )
        credits = result['total_credits'] or 0
        debits = result['total_debits'] or 0
        return credits - debits

    def get_held_balance(self):
        """
        Amount currently held in pending/processing payouts.
        NOTE: This is for DISPLAY only (the 'HELD' card in UI).
        Do NOT subtract this from get_balance() — that would double-count,
        since debit ledger entries already represent these holds.
        """
        result = self.payouts.filter(
            status__in=['pending', 'processing']
        ).aggregate(total=Sum('amount_paise'))
        return result['total'] or 0

    def get_available_balance(self):
        """
        Available = Total ledger balance (credits - debits).
        Debit entries already capture payout holds, so no extra subtraction needed.
        """
        return self.get_balance()  # FIX: removed - get_held_balance()

    def __str__(self):
        return f"{self.name} ({self.email})"


class LedgerEntry(models.Model):
    ENTRY_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name='ledger_entries'
    )
    amount_paise = models.BigIntegerField()
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    description = models.CharField(max_length=500)
    payout = models.ForeignKey(
        'Payout', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.entry_type} {self.amount_paise} paise for {self.merchant.name}"


class PayoutStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


ALLOWED_TRANSITIONS = {
    PayoutStatus.PENDING: [PayoutStatus.PROCESSING],
    PayoutStatus.PROCESSING: [PayoutStatus.COMPLETED, PayoutStatus.FAILED],
    PayoutStatus.COMPLETED: [],
    PayoutStatus.FAILED: [],
}


class Payout(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name='payouts'
    )
    amount_paise = models.BigIntegerField()
    bank_account_id = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING,
        db_index=True,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def transition_to(self, new_status, failure_reason=''):
        allowed = ALLOWED_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Illegal transition: {self.status} -> {new_status}. "
                f"Allowed from {self.status}: {allowed}"
            )
        self.status = new_status
        if new_status == PayoutStatus.PROCESSING:
            self.processing_started_at = timezone.now()
        if new_status in (PayoutStatus.COMPLETED, PayoutStatus.FAILED):
            self.completed_at = timezone.now()
        if failure_reason:
            self.failure_reason = failure_reason

    def is_stuck(self):
        if self.status != PayoutStatus.PROCESSING:
            return False
        if self.processing_started_at is None:
            return False
        elapsed = (timezone.now() - self.processing_started_at).total_seconds()
        return elapsed > 30

    def __str__(self):
        return f"Payout {self.id} - {self.amount_paise} paise - {self.status}"


class IdempotencyKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name='idempotency_keys'
    )
    key = models.CharField(max_length=255, db_index=True)
    response_body = models.JSONField(null=True, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    payout = models.OneToOneField(
        Payout, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='idempotency_key'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = [('merchant', 'key')]

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"IdempotencyKey {self.key} for {self.merchant.name}"