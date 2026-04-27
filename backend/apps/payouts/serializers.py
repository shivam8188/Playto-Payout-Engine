from rest_framework import serializers
from .models import Merchant, LedgerEntry, Payout


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ['id', 'amount_paise', 'entry_type', 'description', 'created_at']


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            'id', 'amount_paise', 'bank_account_id', 'status',
            'attempt_count', 'max_attempts', 'failure_reason',
            'created_at', 'updated_at', 'processing_started_at', 'completed_at',
        ]
        read_only_fields = fields


class PayoutCreateSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.CharField(max_length=100)

    def validate_amount_paise(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class MerchantSerializer(serializers.ModelSerializer):
    available_balance_paise = serializers.SerializerMethodField()
    held_balance_paise = serializers.SerializerMethodField()
    total_balance_paise = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = [
            'id', 'name', 'email', 'bank_account_number', 'bank_ifsc',
            'available_balance_paise', 'held_balance_paise', 'total_balance_paise',
            'created_at',
        ]

    def get_available_balance_paise(self, obj):
        return obj.get_available_balance()

    def get_held_balance_paise(self, obj):
        return obj.get_held_balance()

    def get_total_balance_paise(self, obj):
        return obj.get_balance()


class MerchantDetailSerializer(MerchantSerializer):
    recent_ledger = serializers.SerializerMethodField()
    recent_payouts = serializers.SerializerMethodField()

    class Meta(MerchantSerializer.Meta):
        fields = MerchantSerializer.Meta.fields + ['recent_ledger', 'recent_payouts']

    def get_recent_ledger(self, obj):
        entries = obj.ledger_entries.all()[:20]
        return LedgerEntrySerializer(entries, many=True).data

    def get_recent_payouts(self, obj):
        payouts = obj.payouts.all()[:20]
        return PayoutSerializer(payouts, many=True).data
