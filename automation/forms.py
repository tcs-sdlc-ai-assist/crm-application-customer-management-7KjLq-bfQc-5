import json

from django import forms

from automation.models import AutomationRule


class AutomationRuleForm(forms.ModelForm):
    config = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': '{"key": "value"}',
            'class': 'form-textarea',
        }),
        required=False,
        help_text='Rule parameters and criteria configuration in JSON format.',
    )

    class Meta:
        model = AutomationRule
        fields = ['name', 'trigger_type', 'action_type', 'config', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter rule name',
            }),
            'trigger_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'action_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
        }
        labels = {
            'name': 'Rule Name',
            'trigger_type': 'Trigger Type',
            'action_type': 'Action Type',
            'config': 'Configuration (JSON)',
            'is_active': 'Active',
        }

    def clean_config(self):
        config_value = self.cleaned_data.get('config', '')

        if not config_value or config_value.strip() == '':
            return {}

        try:
            parsed = json.loads(config_value)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise forms.ValidationError(
                'Invalid JSON format. Please enter valid JSON. Error: %(error)s',
                code='invalid_json',
                params={'error': str(e)},
            )

        if not isinstance(parsed, dict):
            raise forms.ValidationError(
                'Configuration must be a JSON object (dictionary), not %(type)s.',
                code='invalid_json_type',
                params={'type': type(parsed).__name__},
            )

        return parsed

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            config_data = self.instance.config
            if config_data and isinstance(config_data, dict):
                self.initial['config'] = json.dumps(config_data, indent=2)
            else:
                self.initial['config'] = '{}'