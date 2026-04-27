from django.db import transaction, connection
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
import uuid as _uuid
import logging

from .models import Merchant, Payout, LedgerEntry, IdempotencyKey, PayoutStatus
from .serializers import (
    MerchantSerializer, MerchantDetailSerializer,
    PayoutSerializer, PayoutCreateSerializer,
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
def merchant_list(request):
    merchants = Merchant.objects.all()
    return Response(MerchantSerializer(merchants, many=True).data)


@api_view(['GET'])
def merchant_detail(request, merchant_id):
    try:
        merchant = Merchant.objects.get(pk=merchant_id)
    except Merchant.DoesNotExist:
        return Response({'error': 'Merchant not found'}, status=404)
    return Response(MerchantDetailSerializer(merchant).data)


@api_view(['GET'])
def payout_list(request, merchant_id):
    try:
        merchant = Merchant.objects.get(pk=merchant_id)
    except Merchant.DoesNotExist:
        return Response({'error': 'Merchant not found'}, status=404)
    return Response(PayoutSerializer(merchant.payouts.all(), many=True).data)


@api_view(['GET'])
def payout_detail(request, payout_id):
    try:
        payout = Payout.objects.get(pk=payout_id)
    except Payout.DoesNotExist:
        return Response({'error': 'Payout not found'}, status=404)
    return Response(PayoutSerializer(payout).data)


def _get_merchant_lock_id(merchant_id) -> int:
    return hash(str(merchant_id)) & 0x7FFFFFFFFFFFFFFF


def _dispatch_payout_task(payout_id: str):
    """
    Try to dispatch via Celery. If Celery/Redis is unavailable,
    fall back to direct synchronous processing so the API never 500s.
    """
    try:
        from .tasks import process_payout
        process_payout.apply_async(args=[payout_id], countdown=1)
        logger.info(f"Dispatched payout {payout_id} to Celery")
    except Exception as exc:
        logger.warning(f"Celery unavailable ({exc}), processing payout {payout_id} synchronously")
        try:
            from .tasks import process_payout
            process_payout(payout_id)
        except Exception as sync_exc:
            logger.error(f"Sync processing also failed for {payout_id}: {sync_exc}")


@api_view(['POST'])
def create_payout(request, merchant_id):
    
    idempotency_key_value = request.headers.get('Idempotency-Key', '').strip()
    if not idempotency_key_value:
        return Response(
            {'error': 'Idempotency-Key header is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        _uuid.UUID(idempotency_key_value)
    except ValueError:
        return Response(
            {'error': 'Idempotency-Key must be a valid UUID'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        merchant = Merchant.objects.get(pk=merchant_id)
    except Merchant.DoesNotExist:
        return Response({'error': 'Merchant not found'}, status=404)

    
    try:
        existing_key = IdempotencyKey.objects.get(
            merchant=merchant,
            key=idempotency_key_value,
        )
        if not existing_key.is_expired():
            if existing_key.response_body is not None:
                return Response(
                    existing_key.response_body,
                    status=existing_key.response_status
                )
            else:
                return Response(
                    {'error': 'Request already in progress. Retry shortly.'},
                    status=status.HTTP_409_CONFLICT
                )
        else:
            existing_key.delete()
    except IdempotencyKey.DoesNotExist:
        pass

    
    serializer = PayoutCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount_paise = serializer.validated_data['amount_paise']
    bank_account_id = serializer.validated_data['bank_account_id']

    
    idem_key, created = IdempotencyKey.objects.get_or_create(
        merchant=merchant,
        key=idempotency_key_value,
        defaults={
            'response_body': None,
            'response_status': None,
            'expires_at': timezone.now() + timedelta(hours=24),
        }
    )
    if not created:
        if idem_key.response_body is not None and not idem_key.is_expired():
            return Response(idem_key.response_body, status=idem_key.response_status)
        return Response(
            {'error': 'Request already in progress. Retry shortly.'},
            status=status.HTTP_409_CONFLICT
        )

    
    payout = None
    response_data = None
    response_status_code = None
    insufficient = False
    error_detail = None

    try:
        with transaction.atomic():
            lock_id = _get_merchant_lock_id(merchant_id)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])

            result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
                total_credits=Sum('amount_paise', filter=Q(entry_type='credit')),
                total_debits=Sum('amount_paise', filter=Q(entry_type='debit')),
            )
            available = (result['total_credits'] or 0) - (result['total_debits'] or 0)

            if available < amount_paise:
                insufficient = True
                error_detail = {
                    'error': 'Insufficient funds',
                    'available_paise': available,
                    'requested_paise': amount_paise,
                }
            else:
                payout = Payout.objects.create(
                    merchant=merchant,
                    amount_paise=amount_paise,
                    bank_account_id=bank_account_id,
                    status=PayoutStatus.PENDING,
                )
                LedgerEntry.objects.create(
                    merchant=merchant,
                    amount_paise=amount_paise,
                    entry_type='debit',
                    description=f'Payout hold for payout {payout.id}',
                    payout=payout,
                )
                response_data = PayoutSerializer(payout).data
                response_status_code = status.HTTP_201_CREATED
                idem_key.payout = payout
                idem_key.response_body = response_data
                idem_key.response_status = response_status_code
                idem_key.save(update_fields=['payout', 'response_body', 'response_status'])

    except Exception as exc:
        idem_key.delete()
        raise exc

    if insufficient:
        idem_key.delete()
        return Response(error_detail, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    
    _dispatch_payout_task(str(payout.id))

    return Response(response_data, status=response_status_code)