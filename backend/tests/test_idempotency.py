import uuid
from django.test import TestCase, Client
from apps.payouts.models import Merchant, LedgerEntry, Payout


def _make_merchant() -> Merchant:
    m = Merchant.objects.create(
        name='Idem Test Merchant',
        email=f'idem_{uuid.uuid4()}@test.com',
        bank_account_number='9999999999',
        bank_ifsc='IDEM0001234',
    )
    LedgerEntry.objects.create(
        merchant=m,
        amount_paise=100_000,
        entry_type='credit',
        description='Test balance',
    )
    return m


class IdempotencyTest(TestCase):
    def test_duplicate_request_returns_same_response(self):
        merchant = _make_merchant()
        client = Client()
        idem_key = str(uuid.uuid4())
        payload = {'amount_paise': 5_000, 'bank_account_id': 'ACCIDEM1'}

        r1 = client.post(
            f'/api/v1/merchants/{merchant.id}/payouts/',
            data=payload,
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )
        r2 = client.post(
            f'/api/v1/merchants/{merchant.id}/payouts/',
            data=payload,
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r1.json()['id'], r2.json()['id'])
        self.assertEqual(Payout.objects.filter(merchant=merchant).count(), 1)

    def test_different_keys_create_different_payouts(self):
        merchant = _make_merchant()
        client = Client()

        for _ in range(2):
            key = str(uuid.uuid4())
            r = client.post(
                f'/api/v1/merchants/{merchant.id}/payouts/',
                data={'amount_paise': 5_000, 'bank_account_id': 'ACC'},
                content_type='application/json',
                HTTP_IDEMPOTENCY_KEY=key,
            )
            self.assertEqual(r.status_code, 201)

        self.assertEqual(Payout.objects.filter(merchant=merchant).count(), 2)

    def test_key_scoped_per_merchant(self):
        m1 = _make_merchant()
        m2 = _make_merchant()
        client = Client()
        shared_key = str(uuid.uuid4())

        r1 = client.post(
            f'/api/v1/merchants/{m1.id}/payouts/',
            data={'amount_paise': 3_000, 'bank_account_id': 'ACC1'},
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )
        r2 = client.post(
            f'/api/v1/merchants/{m2.id}/payouts/',
            data={'amount_paise': 3_000, 'bank_account_id': 'ACC2'},
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()['id'], r2.json()['id'])

    def test_missing_idempotency_key_returns_400(self):
        merchant = _make_merchant()
        client = Client()
        r = client.post(
            f'/api/v1/merchants/{merchant.id}/payouts/',
            data={'amount_paise': 1_000, 'bank_account_id': 'ACC'},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)
