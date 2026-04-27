import threading
import uuid
import json
from django.test import TransactionTestCase, Client
from django.db import connection, connections
from apps.payouts.models import Merchant, LedgerEntry, Payout
from django.db.models import Sum, Q


def _make_merchant(balance_paise: int) -> Merchant:
    merchant = Merchant.objects.create(
        name='Test Merchant',
        email=f'test_{uuid.uuid4()}@test.com',
        bank_account_number='1234567890',
        bank_ifsc='TEST0001234',
    )
    LedgerEntry.objects.create(
        merchant=merchant,
        amount_paise=balance_paise,
        entry_type='credit',
        description='Initial test balance',
    )
    return merchant


class ConcurrencyTest(TransactionTestCase):
    """
    Uses TransactionTestCase so threads can see committed data.
    Each thread closes its DB connection after finishing so Django
    can destroy the test database cleanly at the end.
    """

    def _make_request(self, url, amount_paise, idem_key, results, errors):
        """
        Runs in a thread. Creates its own Client, makes the request,
        then closes the DB connection so PostgreSQL doesn't block
        test database teardown with open sessions.
        """
        try:
            c = Client()
            resp = c.post(
                url,
                data=json.dumps({'amount_paise': amount_paise, 'bank_account_id': 'ACC'}),
                content_type='application/json',
                HTTP_IDEMPOTENCY_KEY=idem_key,
            )
            results.append(resp.status_code)
        except Exception as e:
            errors.append(str(e))
        finally:
           
            connections.close_all()

    def test_two_concurrent_60_inr_payouts_against_100_inr_balance(self):
        """
        Classic overdraft test:
        Balance: 10,000 paise (Rs.100)
        Two simultaneous 6,000 paise (Rs.60) requests.
        Exactly one must succeed (201), one must fail (422).
        The SELECT FOR UPDATE lock in views.py prevents both succeeding.
        """
        merchant = _make_merchant(10_000)
        url = f'/api/v1/merchants/{merchant.id}/payouts/'

        results = []
        errors = []

        t1 = threading.Thread(
            target=self._make_request,
            args=(url, 6_000, str(uuid.uuid4()), results, errors)
        )
        t2 = threading.Thread(
            target=self._make_request,
            args=(url, 6_000, str(uuid.uuid4()), results, errors)
        )

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
        self.assertEqual(len(results), 2, f"Expected 2 results, got {results}")

        successes = results.count(201)
        failures = results.count(422)

        self.assertEqual(successes, 1,
            f"Expected exactly 1 success (201), got {successes}. Results: {results}")
        self.assertEqual(failures, 1,
            f"Expected exactly 1 failure (422), got {failures}. Results: {results}")

       
        merchant.refresh_from_db()
        payouts = Payout.objects.filter(merchant=merchant)
        self.assertEqual(payouts.count(), 1, "Exactly one payout must exist in DB")
        self.assertGreaterEqual(
            merchant.get_available_balance(), 0,
            f"Available balance went negative: {merchant.get_available_balance()}"
        )

    def test_balance_invariant_after_concurrent_payouts(self):
        """
        10 concurrent Rs.60 requests against Rs.500 balance.
        At most 8 can succeed (8 x 6000 = 48000 <= 50000).
        Verifies: sum(credits) - sum(debits) == displayed balance.
        Available balance must never go negative.
        """
        merchant = _make_merchant(50_000)
        url = f'/api/v1/merchants/{merchant.id}/payouts/'
        results = []
        errors = []

        threads = [
            threading.Thread(
                target=self._make_request,
                args=(url, 6_000, str(uuid.uuid4()), results, errors)
            )
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")

        
        result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
            total_credits=Sum('amount_paise', filter=Q(entry_type='credit')),
            total_debits=Sum('amount_paise', filter=Q(entry_type='debit')),
        )
        computed = (result['total_credits'] or 0) - (result['total_debits'] or 0)
        displayed = merchant.get_balance()

        self.assertEqual(computed, displayed,
            f"Invariant violated: computed={computed}, displayed={displayed}")
        self.assertGreaterEqual(merchant.get_available_balance(), 0,
            f"Overdraft: available={merchant.get_available_balance()}")