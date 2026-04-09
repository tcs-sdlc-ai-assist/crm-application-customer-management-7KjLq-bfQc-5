from django import forms
from django.contrib.auth import authenticate

from accounts.models import User


class LoginForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter your email",
                "autofocus": True,
            }
        ),
        label="Email",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter your password",
            }
        ),
        label="Password",
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            self.user_cache = authenticate(
                self.request,
                email=email,
                password=password,
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    "Invalid email or password. Please try again.",
                    code="invalid_login",
                )
            if not self.user_cache.is_active:
                raise forms.ValidationError(
                    "This account is inactive.",
                    code="inactive",
                )

        return cleaned_data

    def get_user(self):
        return self.user_cache


class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter a password",
            }
        ),
        label="Password",
        min_length=8,
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Confirm your password",
            }
        ),
        label="Confirm Password",
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "role",
            "phone_number",
            "job_title",
            "department",
        ]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter your email",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "First name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Last name",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Phone number",
                }
            ),
            "job_title": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Job title",
                }
            ),
            "department": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Department",
                }
            ),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "A user with this email address already exists.",
                code="duplicate_email",
            )
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error(
                "password_confirm",
                forms.ValidationError(
                    "Passwords do not match.",
                    code="password_mismatch",
                ),
            )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone_number",
            "job_title",
            "department",
            "bio",
            "profile_picture",
            "date_of_birth",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "First name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Last name",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Phone number",
                }
            ),
            "job_title": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Job title",
                }
            ),
            "department": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Department",
                }
            ),
            "bio": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "placeholder": "Tell us about yourself",
                    "rows": 4,
                }
            ),
            "profile_picture": forms.ClearableFileInput(
                attrs={
                    "class": "form-input",
                }
            ),
            "date_of_birth": forms.DateInput(
                attrs={
                    "class": "form-input",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_of_birth"].input_formats = ["%Y-%m-%d"]