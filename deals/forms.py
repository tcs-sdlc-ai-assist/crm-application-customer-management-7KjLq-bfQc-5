from django import forms

from deals.models import Deal, SalesStage
from customers.models import Customer
from accounts.models import User


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = [
            "name",
            "value",
            "customer",
            "stage",
            "expected_close_date",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter deal name",
            }),
            "value": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0",
            }),
            "customer": forms.Select(attrs={
                "class": "form-select",
            }),
            "stage": forms.Select(attrs={
                "class": "form-select",
            }),
            "expected_close_date": forms.DateInput(attrs={
                "class": "form-input",
                "type": "date",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-textarea",
                "placeholder": "Enter deal description",
                "rows": 4,
            }),
        }
        labels = {
            "name": "Deal Name",
            "value": "Deal Value ($)",
            "customer": "Customer",
            "stage": "Stage",
            "expected_close_date": "Expected Close Date",
            "description": "Description",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True
        self.fields["value"].required = True
        self.fields["customer"].required = True
        self.fields["stage"].required = True
        self.fields["expected_close_date"].required = False
        self.fields["description"].required = False

        self.fields["customer"].queryset = Customer.objects.all().order_by("name")
        self.fields["stage"].queryset = SalesStage.objects.filter(
            is_active=True
        ).order_by("order")

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Deal name is required.")
        if len(name) > 128:
            raise forms.ValidationError(
                "Deal name must be 128 characters or fewer."
            )
        return name

    def clean_value(self):
        value = self.cleaned_data.get("value")
        if value is None:
            raise forms.ValidationError("Deal value is required.")
        if value <= 0:
            raise forms.ValidationError(
                "Deal value must be greater than zero."
            )
        return value

    def clean_expected_close_date(self):
        from django.utils import timezone

        expected_close_date = self.cleaned_data.get("expected_close_date")
        if expected_close_date is None:
            return expected_close_date

        today = timezone.now().date()
        if expected_close_date < today:
            if self.instance and self.instance.pk:
                if (
                    self.instance.expected_close_date
                    and self.instance.expected_close_date == expected_close_date
                ):
                    return expected_close_date
            raise forms.ValidationError(
                "Expected close date cannot be in the past."
            )
        return expected_close_date

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


class DealAssignForm(forms.Form):
    owner = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by(
            "first_name", "last_name"
        ),
        required=True,
        widget=forms.Select(attrs={
            "class": "form-select",
        }),
        label="Deal Owner",
        empty_label="— Select Owner —",
    )

    def __init__(self, *args, **kwargs):
        self.deal = kwargs.pop("deal", None)
        super().__init__(*args, **kwargs)

    def save(self):
        if self.deal is not None:
            self.deal.owner = self.cleaned_data["owner"]
            self.deal.save(update_fields=["owner", "updated_at"])
        return self.deal


class SalesStageForm(forms.ModelForm):
    class Meta:
        model = SalesStage
        fields = [
            "name",
            "order",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter stage name",
            }),
            "order": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "Display order (e.g. 1, 2, 3)",
                "min": "0",
                "step": "1",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-checkbox",
            }),
        }
        labels = {
            "name": "Stage Name",
            "order": "Display Order",
            "is_active": "Active",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True
        self.fields["order"].required = True

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Stage name is required.")
        if len(name) > 64:
            raise forms.ValidationError(
                "Stage name must be 64 characters or fewer."
            )
        queryset = SalesStage.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError(
                "A sales stage with this name already exists."
            )
        return name

    def clean_order(self):
        order = self.cleaned_data.get("order")
        if order is None:
            raise forms.ValidationError("Display order is required.")
        if order < 0:
            raise forms.ValidationError(
                "Display order must be a non-negative integer."
            )
        return order