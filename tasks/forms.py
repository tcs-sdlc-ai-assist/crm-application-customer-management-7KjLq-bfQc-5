from django import forms
from django.utils import timezone

from accounts.models import User
from customers.models import Customer
from deals.models import Deal
from tasks.models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "customer",
            "deal",
            "assigned_to",
            "status",
            "priority",
            "due_date",
            "reminder_date",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter task title",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-textarea",
                "placeholder": "Enter task description",
                "rows": 4,
            }),
            "customer": forms.Select(attrs={
                "class": "form-select",
            }),
            "deal": forms.Select(attrs={
                "class": "form-select",
            }),
            "assigned_to": forms.Select(attrs={
                "class": "form-select",
            }),
            "status": forms.Select(attrs={
                "class": "form-select",
            }),
            "priority": forms.Select(attrs={
                "class": "form-select",
            }),
            "due_date": forms.DateInput(attrs={
                "class": "form-input",
                "type": "date",
            }),
            "reminder_date": forms.DateTimeInput(attrs={
                "class": "form-input",
                "type": "datetime-local",
            }),
        }
        labels = {
            "title": "Title",
            "description": "Description",
            "customer": "Customer",
            "deal": "Deal",
            "assigned_to": "Assignee",
            "status": "Status",
            "priority": "Priority",
            "due_date": "Due Date",
            "reminder_date": "Reminder Date",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = True
        self.fields["description"].required = False
        self.fields["customer"].required = False
        self.fields["deal"].required = False
        self.fields["assigned_to"].required = False
        self.fields["status"].required = True
        self.fields["priority"].required = True
        self.fields["due_date"].required = False
        self.fields["reminder_date"].required = False

        self.fields["customer"].queryset = Customer.objects.all().order_by("name")
        self.fields["deal"].queryset = Deal.objects.select_related(
            "customer", "stage"
        ).all().order_by("name")
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True
        ).order_by("first_name", "last_name", "email")

        self.fields["customer"].empty_label = "— Select Customer —"
        self.fields["deal"].empty_label = "— Select Deal —"
        self.fields["assigned_to"].empty_label = "— Select Assignee —"

        if self.instance and self.instance.pk:
            if self.instance.reminder_date:
                self.initial["reminder_date"] = self.instance.reminder_date.strftime(
                    "%Y-%m-%dT%H:%M"
                )

    def clean_title(self):
        title = self.cleaned_data.get("title", "").strip()
        if not title:
            raise forms.ValidationError("Task title is required.")
        if len(title) > 255:
            raise forms.ValidationError(
                "Task title must be 255 characters or fewer."
            )
        return title

    def clean_due_date(self):
        due_date = self.cleaned_data.get("due_date")
        if due_date is None:
            return due_date

        today = timezone.now().date()
        if due_date < today:
            if self.instance and self.instance.pk:
                if (
                    self.instance.due_date
                    and self.instance.due_date == due_date
                ):
                    return due_date
            raise forms.ValidationError(
                "Due date cannot be in the past."
            )
        return due_date

    def clean_reminder_date(self):
        reminder_date = self.cleaned_data.get("reminder_date")
        if reminder_date is None:
            return reminder_date
        return reminder_date

    def clean(self):
        cleaned_data = super().clean()
        due_date = cleaned_data.get("due_date")
        reminder_date = cleaned_data.get("reminder_date")

        if reminder_date and due_date:
            reminder_date_only = reminder_date.date() if hasattr(reminder_date, "date") else reminder_date
            if reminder_date_only > due_date:
                self.add_error(
                    "reminder_date",
                    forms.ValidationError(
                        "Reminder date must be on or before the due date.",
                        code="invalid_reminder_date",
                    ),
                )

        return cleaned_data