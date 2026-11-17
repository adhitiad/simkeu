from __future__ import annotations

from rest_framework import serializers

from .models import JournalEntry, JournalLineRecord


class JournalLineInputSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    debit = serializers.IntegerField(min_value=0)
    credit = serializers.IntegerField(min_value=0)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate_debit(self, value: int) -> int:
        raw = self.initial_data.get("debit")
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise serializers.ValidationError("Nominal harus berupa integer Rupiah, tanpa desimal.")
        return value

    def validate_credit(self, value: int) -> int:
        raw = self.initial_data.get("credit")
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise serializers.ValidationError("Nominal harus berupa integer Rupiah, tanpa desimal.")
        return value


class JournalCreateSerializer(serializers.Serializer):
    entity_id = serializers.IntegerField(min_value=1)
    business_date = serializers.DateField()
    source_type = serializers.CharField(max_length=64)
    source_id = serializers.CharField(max_length=128)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    lines = JournalLineInputSerializer(many=True, allow_empty=False)

    def validate_entity_id(self, value: int) -> int:
        raw = self.initial_data.get("entity_id")
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise serializers.ValidationError("entity_id harus berupa integer.")
        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        lines = attrs.get("lines")
        if not isinstance(lines, list) or len(lines) < 2:
            raise serializers.ValidationError({"lines": "Jurnal minimal memiliki dua baris."})
        return attrs


class JournalLineReadSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalLineRecord
        fields = [
            "line_number",
            "account",
            "account_code",
            "account_name",
            "description",
            "debit",
            "credit",
        ]
        read_only_fields = fields


class JournalReadSerializer(serializers.ModelSerializer):
    period_name = serializers.CharField(source="period.name", read_only=True)
    created_by_id = serializers.IntegerField(read_only=True)
    lines = JournalLineReadSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "entity_id",
            "period",
            "period_name",
            "business_date",
            "source_type",
            "source_id",
            "description",
            "posted_at",
            "created_at",
            "created_by_id",
            "lines",
        ]
        read_only_fields = fields
