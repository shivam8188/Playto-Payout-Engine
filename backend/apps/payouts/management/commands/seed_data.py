from django.core.management.base import BaseCommand
from apps.payouts.models import Merchant, LedgerEntry
import uuid


class Command(BaseCommand):
    help = 'Seeds the database with test merchants and credit history'

    def handle(self, *args, **options):
        self.stdout.write('Seeding merchants...')

        merchants_data = [
            {
                'id': uuid.UUID('11111111-1111-1111-1111-111111111111'),
                'name': 'Priya Design Studio',
                'email': 'priya@designstudio.in',
                'bank_account_number': '012345678901',
                'bank_ifsc': 'HDFC0001234',
            },
            {
                'id': uuid.UUID('22222222-2222-2222-2222-222222222222'),
                'name': 'Arjun Freelance Dev',
                'email': 'arjun@freelancedev.in',
                'bank_account_number': '987654321098',
                'bank_ifsc': 'ICIC0005678',
            },
            {
                'id': uuid.UUID('33333333-3333-3333-3333-333333333333'),
                'name': 'Mumbai Digital Agency',
                'email': 'hello@mumbaidigital.in',
                'bank_account_number': '111222333444',
                'bank_ifsc': 'SBIN0009876',
            },
        ]

        credits_data = {
            '11111111-1111-1111-1111-111111111111': [
                (500000, 'Client payment - Logo design project'),
                (1500000, 'Client payment - Website redesign'),
                (300000, 'Client payment - Social media graphics'),
            ],
            '22222222-2222-2222-2222-222222222222': [
                (2000000, 'Client payment - React app development'),
                (800000, 'Client payment - API integration'),
                (1200000, 'Client payment - Mobile app module'),
            ],
            '33333333-3333-3333-3333-333333333333': [
                (5000000, 'Client payment - SEO campaign Q1'),
                (3000000, 'Client payment - PPC management'),
                (2500000, 'Client payment - Content strategy'),
            ],
        }

        for data in merchants_data:
            merchant, created = Merchant.objects.update_or_create(
                id=data['id'],
                defaults={
                    'name': data['name'],
                    'email': data['email'],
                    'bank_account_number': data['bank_account_number'],
                    'bank_ifsc': data['bank_ifsc'],
                }
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action} merchant: {merchant.name}')

            LedgerEntry.objects.filter(
                merchant=merchant,
                entry_type='credit',
                description__startswith='Client payment',
            ).delete()

            for amount_paise, description in credits_data[str(data['id'])]:
                LedgerEntry.objects.create(
                    merchant=merchant,
                    amount_paise=amount_paise,
                    entry_type='credit',
                    description=description,
                )
            self.stdout.write(f'    Added {len(credits_data[str(data["id"])])} credit entries')

        self.stdout.write(self.style.SUCCESS('\nSeed complete! Merchant balances:'))
        for m in Merchant.objects.all():
            balance_inr = m.get_balance() / 100
            self.stdout.write(f'  {m.name}: Rs.{balance_inr:,.2f}')
