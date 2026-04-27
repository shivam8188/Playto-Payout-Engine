
# 1. The Ledger

```python
result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
    total_credits=Sum('amount_paise', filter=Q(entry_type='credit')),
    total_debits=Sum('amount_paise', filter=Q(entry_type='debit')),
)
balance = (result['total_credits'] or 0) - (result['total_debits'] or 0)
```

SQL equivalent:
```sql
SELECT
  SUM(amount_paise) FILTER (WHERE entry_type = 'credit') AS total_credits,
  SUM(amount_paise) FILTER (WHERE entry_type = 'debit')  AS total_debits
FROM payouts_ledgerentry
WHERE merchant_id = %s;
```

**Why this model?** Balance is never a stored column — it is always derived from the ledger. This makes the invariant `balance = credits - debits` structurally impossible to violate. Every paisa movement is an immutable record. Amounts are BigIntegerField in paise — integer arithmetic is exact, floats are not.

---

# 2. The Lock

```python
with transaction.atomic():
    list(LedgerEntry.objects.select_for_update().filter(merchant=merchant))

    result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
        total_credits=Sum('amount_paise', filter=Q(entry_type='credit')),
        total_debits=Sum('amount_paise', filter=Q(entry_type='debit')),
    )
    total_balance = (result['total_credits'] or 0) - (result['total_debits'] or 0)

    held = Payout.objects.select_for_update().filter(
        merchant=merchant, status__in=['pending', 'processing']
    ).aggregate(total=Sum('amount_paise'))['total'] or 0

    available = total_balance - held
    if available < amount_paise:
        return 422
```

**Database primitive: SELECT FOR UPDATE.** Acquires an exclusive row lock on all LedgerEntry rows for this merchant. Any concurrent transaction trying to read/modify those rows blocks until this transaction commits. Thread B cannot read stale balance data while Thread A is still writing.

---

# 3. The Idempotency

The system uses an IdempotencyKey model with unique_together on (merchant, key).

Flow:
1. Check if key exists for this merchant
2. If found and response stored -> replay exact response
3. If found but response is null -> return 409 (in flight)
4. If not found -> get_or_create with response_body=None (marks in flight)
5. Run business logic
6. Store response in idempotency key record

If the first request is in flight when the second arrives, the second hits step 3 and gets 409. The get_or_create uses PostgreSQL's unique constraint as an atomic mutex — only one concurrent request wins the insert.

---

# 4. The State Machine

```python
ALLOWED_TRANSITIONS = {
    PayoutStatus.PENDING:     [PayoutStatus.PROCESSING],
    PayoutStatus.PROCESSING:  [PayoutStatus.COMPLETED, PayoutStatus.FAILED],
    PayoutStatus.COMPLETED:   [],   # terminal
    PayoutStatus.FAILED:      [],   # terminal
}

def transition_to(self, new_status, failure_reason=''):
    allowed = ALLOWED_TRANSITIONS.get(self.status, [])
    if new_status not in allowed:
        raise ValueError(f"Illegal transition: {self.status} -> {new_status}")
```

ALLOWED_TRANSITIONS[FAILED] = [] so any call to transition_to(COMPLETED) on a failed payout raises ValueError before any DB write. transition_to is the ONLY path that mutates status.

---

# 5. The AI Audit

**What AI gave me (wrong):**

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(pk=merchant_id)
    balance = merchant.get_balance()  # WRONG
    if balance < amount_paise:
        return 422
    Payout.objects.create(...)
```

**What was wrong:**
1. It locked the Merchant row, not the LedgerEntry rows. A concurrent transaction inserting a new LedgerEntry does not need the Merchant row lock — it proceeds unblocked.
2. merchant.get_balance() runs a second query that is NOT inside the SELECT FOR UPDATE scope.

**What I replaced it with:**

```python
with transaction.atomic():
    list(LedgerEntry.objects.select_for_update().filter(merchant=merchant))
    result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
        total_credits=Sum('amount_paise', filter=Q(entry_type='credit')),
        total_debits=Sum('amount_paise', filter=Q(entry_type='debit')),
    )
    held = Payout.objects.select_for_update().filter(
        merchant=merchant, status__in=['pending', 'processing']
    ).aggregate(total=Sum('amount_paise'))['total'] or 0
    available = ((result['total_credits'] or 0) - (result['total_debits'] or 0)) - held
```

Lock is on the rows whose aggregate we depend on. Aggregation happens in the same transaction after the lock is held.
