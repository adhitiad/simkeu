from __future__ import annotations

from django import forms

from .models import BudgetPlanType


class FiscalYearForm(forms.Form):
    code = forms.CharField(label="Kode tahun buku", max_length=16)
    name = forms.CharField(label="Nama tahun buku", max_length=100)
    starts_on = forms.DateField(
        label="Tanggal mulai",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    ends_on = forms.DateField(
        label="Tanggal akhir",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self) -> dict[str, object]:
        cleaned = super().clean()
        starts_on = cleaned.get("starts_on")
        ends_on = cleaned.get("ends_on")
        if starts_on is not None and ends_on is not None and ends_on < starts_on:
            self.add_error("ends_on", "Tanggal akhir tidak boleh sebelum tanggal mulai.")
        return cleaned


class BudgetPlanForm(forms.Form):
    fiscal_year_id = forms.UUIDField(label="Tahun buku")
    plan_type = forms.ChoiceField(
        label="Jenis dokumen",
        choices=((BudgetPlanType.RKAT, BudgetPlanType.RKAT.label),),
    )
    title = forms.CharField(label="Judul dokumen", max_length=160)
    unit_id = forms.IntegerField(label="Unit penanggung jawab", min_value=1, required=False)
    notes = forms.CharField(label="Catatan", widget=forms.Textarea, required=False)

    def clean(self) -> dict[str, object]:
        cleaned = super().clean()
        plan_type = cleaned.get("plan_type")
        unit_id = cleaned.get("unit_id")
        if plan_type == BudgetPlanType.RKAT and unit_id is None:
            self.add_error("unit_id", "RKAT wajib memilih unit penanggung jawab.")
        return cleaned


class BudgetLineForm(forms.Form):
    unit_id = forms.IntegerField(label="Unit anggaran", min_value=1)
    account_id = forms.UUIDField(label="Akun COA")
    funding_source = forms.CharField(label="Sumber dana", max_length=40)
    description = forms.CharField(label="Uraian kegiatan", max_length=500)
    program_code = forms.CharField(label="Kode program", max_length=40, required=False)
    objective = forms.CharField(label="Tujuan", max_length=500, required=False)
    output = forms.CharField(label="Output", max_length=500, required=False)
    indicator = forms.CharField(label="Indikator", max_length=255, required=False)
    amount = forms.IntegerField(label="Nominal (Rupiah)", min_value=1)
    schedule_start = forms.DateField(
        label="Mulai kegiatan",
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )
    schedule_end = forms.DateField(
        label="Selesai kegiatan",
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )
    is_restricted = forms.BooleanField(label="Dana terikat", required=False)
    restriction_note = forms.CharField(
        label="Ketentuan penggunaan dana",
        max_length=500,
        required=False,
    )

    def clean(self) -> dict[str, object]:
        cleaned = super().clean()
        start = cleaned.get("schedule_start")
        end = cleaned.get("schedule_end")
        if start is not None and end is not None and end < start:
            self.add_error("schedule_end", "Tanggal selesai tidak boleh sebelum tanggal mulai.")
        if cleaned.get("is_restricted") and not str(cleaned.get("restriction_note", "")).strip():
            self.add_error("restriction_note", "Tujuan dan syarat dana terikat wajib diisi.")
        return cleaned


class RevisionForm(forms.Form):
    fiscal_year_id = forms.UUIDField(label="Tahun buku")
    reason = forms.CharField(
        label="Alasan revisi",
        min_length=8,
        widget=forms.Textarea,
    )
    effective_date = forms.DateField(
        label="Tanggal efektif",
        widget=forms.DateInput(attrs={"type": "date"}),
    )


class CommitmentForm(forms.Form):
    allocation_id = forms.UUIDField(label="Pos pagu")
    source_type = forms.CharField(label="Jenis dokumen sumber", max_length=64)
    source_id = forms.CharField(label="Nomor dokumen sumber", max_length=128)
    description = forms.CharField(label="Uraian komitmen", max_length=500)
    amount = forms.IntegerField(label="Nominal komitmen (Rupiah)", min_value=1)
