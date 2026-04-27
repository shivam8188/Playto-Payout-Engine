import random
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum

from .models import Payout, LedgerEntry, PayoutStatus
from .state_machine import assert_transition_legal

logger = logging.getLogger(__name__)


def simulate_bank_response() -> str:
    rand = random.random()
    if rand < 0.70:
        return 'success'
    elif rand < 0.90:
        return 'failure'
    else:
        return 'processing'


def _get_backoff_delay(attempt_count: int) -> int:
    return 2 ** attempt_count


@shared_task(bind=True, max_retries=0, name='apps.payouts.tasks.process_payout')
def process_payout(self, payout_id: str):
    logger.info(f"Processing payout {payout_id}")

    try:
        with transaction.atomic():
            try:
                payout = Payout.objects.select_for_update(nowait=True).get(pk=payout_id)
            except Payout.DoesNotExist:
                logger.error(f"Payout {payout_id} not found")
                return
            except Exception:
                logger.warning(f"Payout {payout_id} is locked by another worker, skipping")
                return

            if payout.status != PayoutStatus.PENDING:
                logger.info(f"Payout {payout_id} is {payout.status}, skipping")
                return

            assert_transition_legal(payout.status, PayoutStatus.PROCESSING)
            payout.transition_to(PayoutStatus.PROCESSING)
            payout.attempt_count += 1
            payout.save(update_fields=['status', 'processing_started_at', 'attempt_count'])

    except Exception as exc:
        logger.error(f"Error transitioning payout {payout_id} to processing: {exc}")
        return

    bank_result = simulate_bank_response()
    logger.info(f"Bank result for payout {payout_id}: {bank_result}")

    if bank_result == 'processing':
        logger.info(f"Payout {payout_id} is hanging in processing - will be retried")
        return

    _finalize_payout(payout_id, bank_result)


def _finalize_payout(payout_id: str, bank_result: str):
    with transaction.atomic():
        try:
            payout = Payout.objects.select_for_update().get(pk=payout_id)
        except Payout.DoesNotExist:
            logger.error(f"Payout {payout_id} not found in finalize")
            return

        if payout.status != PayoutStatus.PROCESSING:
            logger.warning(f"Payout {payout_id} is {payout.status} in finalize, skipping")
            return

        if bank_result == 'success':
            assert_transition_legal(payout.status, PayoutStatus.COMPLETED)
            payout.transition_to(PayoutStatus.COMPLETED)
            payout.save(update_fields=['status', 'completed_at'])
            logger.info(f"Payout {payout_id} completed successfully")

        elif bank_result == 'failure':
            assert_transition_legal(payout.status, PayoutStatus.FAILED)
            payout.transition_to(PayoutStatus.FAILED, failure_reason='Bank rejected the transfer')
            payout.save(update_fields=['status', 'completed_at', 'failure_reason'])

            LedgerEntry.objects.create(
                merchant=payout.merchant,
                amount_paise=payout.amount_paise,
                entry_type='credit',
                description=f'Refund for failed payout {payout.id}',
                payout=payout,
            )
            logger.info(f"Payout {payout_id} failed - funds returned to merchant")


@shared_task(name='apps.payouts.tasks.retry_stuck_payouts')
def retry_stuck_payouts():
    cutoff = timezone.now() - timedelta(seconds=30)
    stuck_payouts = Payout.objects.filter(
        status=PayoutStatus.PROCESSING,
        processing_started_at__lt=cutoff,
    )

    for payout in stuck_payouts:
        logger.info(f"Found stuck payout {payout.id}, attempt {payout.attempt_count}/{payout.max_attempts}")

        if payout.attempt_count >= payout.max_attempts:
            logger.warning(f"Payout {payout.id} exceeded max retries, marking as failed")
            with transaction.atomic():
                try:
                    p = Payout.objects.select_for_update().get(pk=payout.id)
                    if p.status != PayoutStatus.PROCESSING:
                        continue
                    assert_transition_legal(p.status, PayoutStatus.FAILED)
                    p.transition_to(PayoutStatus.FAILED, failure_reason='Max retry attempts exceeded')
                    p.save(update_fields=['status', 'completed_at', 'failure_reason'])
                    LedgerEntry.objects.create(
                        merchant=p.merchant,
                        amount_paise=p.amount_paise,
                        entry_type='credit',
                        description=f'Refund for timed-out payout {p.id}',
                        payout=p,
                    )
                except Exception as exc:
                    logger.error(f"Error failing stuck payout {payout.id}: {exc}")
        else:
            delay = _get_backoff_delay(payout.attempt_count)
            with transaction.atomic():
                try:
                    p = Payout.objects.select_for_update().get(pk=payout.id)
                    if p.status != PayoutStatus.PROCESSING:
                        continue
                    p.status = PayoutStatus.PENDING
                    p.processing_started_at = None
                    p.save(update_fields=['status', 'processing_started_at'])
                except Exception as exc:
                    logger.error(f"Error resetting stuck payout {payout.id}: {exc}")
                    continue

            process_payout.apply_async(args=[str(payout.id)], countdown=delay)
            logger.info(f"Scheduled retry for payout {payout.id} in {delay}s")
