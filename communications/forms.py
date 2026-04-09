from django import forms
from django.utils import timezone

from communications.models import CommunicationLog, Meeting
from customers.models import Customer


class CommunicationLogForm(forms.ModelForm):
    class Meta:
        model = CommunicationLog
        fields = [
            "customer",
            "communication_type",
            "subject",
            "body",
            "direction",
        ]
        widgets = {
            "customer": forms.Select(attrs={
                "class": "form-select",
            }),
            "communication_type": forms.Select(attrs={
                "class": "form-select",
            }),
            "subject": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter subject",
            }),
            "body": forms.Textarea(attrs={
                "class": "form-textarea",
                "placeholder": "Enter communication details...",
                "rows": 6,
            }),
            "direction": forms.Select(attrs={
                "class": "form-select",
            }),
        }
        labels = {
            "customer": "Customer",
            "communication_type": "Type",
            "subject": "Subject",
            "body": "Body",
            "direction": "Direction",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.all().order_by("name")
        self.fields["customer"].required = True
        self.fields["communication_type"].required = True
        self.fields["subject"].required = True
        self.fields["direction"].required = True
        self.fields["body"].required = False

    def clean_subject(self):
        subject = self.cleaned_data.get("subject", "").strip()
        if not subject:
            raise forms.ValidationError("Subject is required.")
        if len(subject) > 255:
            raise forms.ValidationError("Subject must be 255 characters or fewer.")
        return subject


class MeetingForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            "class": "form-input",
            "type": "datetime-local",
        }),
        label="Start Date & Time",
        input_formats=[
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
        ],
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            "class": "form-input",
            "type": "datetime-local",
        }),
        label="End Date & Time",
        input_formats=[
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
        ],
    )

    class Meta:
        model = Meeting
        fields = [
            "customer",
            "title",
            "description",
            "start_time",
            "end_time",
            "location",
        ]
        widgets = {
            "customer": forms.Select(attrs={
                "class": "form-select",
            }),
            "title": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "e.g. Quarterly Review Meeting",
                "maxlength": "255",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-textarea",
                "placeholder": "Meeting agenda, topics to discuss, preparation notes...",
                "rows": 4,
            }),
            "location": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "e.g. Conference Room A, Zoom link, etc.",
                "maxlength": "255",
            }),
        }
        labels = {
            "customer": "Customer",
            "title": "Title",
            "description": "Description",
            "start_time": "Start Date & Time",
            "end_time": "End Date & Time",
            "location": "Location",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.all().order_by("name")
        self.fields["customer"].required = True
        self.fields["title"].required = True
        self.fields["start_time"].required = True
        self.fields["end_time"].required = True
        self.fields["description"].required = False
        self.fields["location"].required = False

    def clean_title(self):
        title = self.cleaned_data.get("title", "").strip()
        if not title:
            raise forms.ValidationError("Meeting title is required.")
        if len(title) > 255:
            raise forms.ValidationError("Title must be 255 characters or fewer.")
        return title

    def clean_start_time(self):
        start_time = self.cleaned_data.get("start_time")
        if start_time is None:
            raise forms.ValidationError("Start time is required.")
        return start_time

    def clean_end_time(self):
        end_time = self.cleaned_data.get("end_time")
        if end_time is None:
            raise forms.ValidationError("End time is required.")
        return end_time

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if start_time and end_time:
            if end_time <= start_time:
                self.add_error(
                    "end_time",
                    forms.ValidationError(
                        "End time must be after start time.",
                        code="invalid_end_time",
                    ),
                )

            if start_time == end_time:
                self.add_error(
                    "end_time",
                    forms.ValidationError(
                        "End time cannot be the same as start time.",
                        code="same_time",
                    ),
                )

        return cleaned_data