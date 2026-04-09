from django import forms

from deals.models import SalesStage
from reports.models import Report


class ReportFilterForm(forms.Form):
    report_type = forms.ChoiceField(
        choices=[('', '— Select Report Type —')] + Report.REPORT_TYPE_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Report Type',
        help_text='Select the type of report to generate.',
    )

    title = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter a descriptive title for this report',
        }),
        label='Report Title',
    )

    format = forms.ChoiceField(
        choices=[('', '— Select Format —')] + Report.FORMAT_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Output Format',
    )

    date_range_start = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
        }),
        label='Start Date',
        help_text='Filter report data from this date.',
    )

    date_range_end = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
        }),
        label='End Date',
        help_text='Filter report data up to this date.',
    )

    user = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='— All Users —',
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Filter by User',
        help_text='Optionally filter report data by a specific user.',
    )

    stage = forms.ModelChoiceField(
        queryset=SalesStage.objects.filter(is_active=True).order_by('order'),
        required=False,
        empty_label='— All Stages —',
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Filter by Stage',
        help_text='Optionally filter report data by pipeline stage.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.conf import settings
        from django.apps import apps

        UserModel = apps.get_model(settings.AUTH_USER_MODEL)
        self.fields['user'].queryset = UserModel.objects.filter(
            is_active=True,
        ).order_by('first_name', 'last_name', 'email')

        self.fields['stage'].queryset = SalesStage.objects.filter(
            is_active=True,
        ).order_by('order')

    def clean(self):
        cleaned_data = super().clean()
        date_range_start = cleaned_data.get('date_range_start')
        date_range_end = cleaned_data.get('date_range_end')

        if date_range_start and date_range_end:
            if date_range_end < date_range_start:
                self.add_error(
                    'date_range_end',
                    forms.ValidationError(
                        'End date must be on or after the start date.',
                        code='invalid_date_range',
                    ),
                )

        return cleaned_data

    def get_report_parameters(self):
        """
        Build a parameters dictionary from the cleaned form data,
        suitable for storing in Report.parameters JSONField.
        """
        if not self.is_valid():
            return {}

        params = {}

        date_range_start = self.cleaned_data.get('date_range_start')
        if date_range_start:
            params['date_range_start'] = date_range_start.isoformat()

        date_range_end = self.cleaned_data.get('date_range_end')
        if date_range_end:
            params['date_range_end'] = date_range_end.isoformat()

        user = self.cleaned_data.get('user')
        if user:
            params['user_id'] = str(user.pk)
            params['user_name'] = user.get_full_name() or str(user.email)

        stage = self.cleaned_data.get('stage')
        if stage:
            params['stage_id'] = str(stage.pk)
            params['stage_name'] = str(stage.name)

        return params