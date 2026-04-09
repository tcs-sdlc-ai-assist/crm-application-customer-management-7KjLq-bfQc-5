from django import forms

from customers.models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "email",
            "phone",
            "industry",
            "company",
            "address",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter customer name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-input",
                "placeholder": "Enter email address",
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter phone number",
            }),
            "industry": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter industry",
            }),
            "company": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter company name",
            }),
            "address": forms.Textarea(attrs={
                "class": "form-textarea",
                "placeholder": "Enter address",
                "rows": 3,
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-textarea",
                "placeholder": "Enter notes",
                "rows": 4,
            }),
        }
        labels = {
            "name": "Customer Name",
            "email": "Email Address",
            "phone": "Phone Number",
            "industry": "Industry",
            "company": "Company",
            "address": "Address",
            "notes": "Notes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True
        self.fields["email"].required = True
        self.fields["industry"].required = True

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Customer name is required.")
        if len(name) > 128:
            raise forms.ValidationError("Customer name must be 128 characters or fewer.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if not email:
            raise forms.ValidationError("Email address is required.")
        queryset = Customer.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("A customer with this email address already exists.")
        return email.lower()

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if phone:
            import re
            phone_pattern = re.compile(r'^[+]?[\d\s\-().]{7,32}$')
            if not phone_pattern.match(phone):
                raise forms.ValidationError("Please enter a valid phone number.")
        return phone

    def clean_industry(self):
        industry = self.cleaned_data.get("industry", "").strip()
        if not industry:
            raise forms.ValidationError("Industry is required.")
        if len(industry) > 64:
            raise forms.ValidationError("Industry must be 64 characters or fewer.")
        return industry