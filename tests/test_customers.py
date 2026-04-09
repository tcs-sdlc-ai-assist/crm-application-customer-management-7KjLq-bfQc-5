import uuid

import pytest
from django.test import Client, TestCase
from django.urls import reverse

from customers.models import Customer
from customers.forms import CustomerForm
from customers.services import CustomerService


@pytest.fixture
def admin_user(db):
    from accounts.models import User
    return User.objects.create_user(
        email="admin@example.com",
        password="testpass123",
        first_name="Admin",
        last_name="User",
        role=User.Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def sales_user(db):
    from accounts.models import User
    return User.objects.create_user(
        email="sales@example.com",
        password="testpass123",
        first_name="Sales",
        last_name="Rep",
        role=User.Role.SALES,
    )


@pytest.fixture
def support_user(db):
    from accounts.models import User
    return User.objects.create_user(
        email="support@example.com",
        password="testpass123",
        first_name="Support",
        last_name="Agent",
        role=User.Role.SUPPORT,
    )


@pytest.fixture
def sample_customer(db, admin_user):
    return Customer.objects.create(
        name="Acme Corp",
        email="contact@acme.com",
        phone="+1-555-0100",
        industry="Technology",
        company="Acme Corporation",
        address="123 Main St, Springfield",
        notes="Important client",
        created_by=admin_user,
    )


@pytest.fixture
def sample_customer_data():
    return {
        "name": "Test Customer",
        "email": "test@customer.com",
        "phone": "+1-555-0200",
        "industry": "Finance",
        "company": "Test Inc",
        "address": "456 Oak Ave",
        "notes": "New customer",
    }


@pytest.fixture
def multiple_customers(db, admin_user):
    customers = []
    industries = ["Technology", "Finance", "Healthcare", "Technology", "Finance"]
    for i in range(5):
        customer = Customer.objects.create(
            name=f"Customer {i}",
            email=f"customer{i}@example.com",
            phone=f"+1-555-010{i}",
            industry=industries[i],
            company=f"Company {i}",
            created_by=admin_user,
        )
        customers.append(customer)
    return customers


@pytest.fixture
def authenticated_client(admin_user):
    client = Client()
    client.login(email="admin@example.com", password="testpass123")
    return client


@pytest.fixture
def sales_client(sales_user):
    client = Client()
    client.login(email="sales@example.com", password="testpass123")
    return client


@pytest.fixture
def support_client(support_user):
    client = Client()
    client.login(email="support@example.com", password="testpass123")
    return client


@pytest.fixture
def anonymous_client():
    return Client()


# =============================================================================
# Model Tests
# =============================================================================


@pytest.mark.django_db
class TestCustomerModel:
    def test_customer_creation_with_valid_data(self, admin_user):
        customer = Customer.objects.create(
            name="New Customer",
            email="new@customer.com",
            industry="Retail",
            created_by=admin_user,
        )
        assert customer.pk is not None
        assert isinstance(customer.pk, uuid.UUID)
        assert customer.name == "New Customer"
        assert customer.email == "new@customer.com"
        assert customer.industry == "Retail"
        assert customer.created_by == admin_user

    def test_customer_str_returns_name(self, sample_customer):
        assert str(sample_customer) == "Acme Corp"

    def test_customer_email_unique_constraint(self, sample_customer, admin_user):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Customer.objects.create(
                name="Duplicate Email",
                email="contact@acme.com",
                industry="Finance",
                created_by=admin_user,
            )

    def test_customer_ordering_by_created_at_desc(self, multiple_customers):
        customers = list(Customer.objects.all())
        for i in range(len(customers) - 1):
            assert customers[i].created_at >= customers[i + 1].created_at

    def test_customer_blank_optional_fields(self, admin_user):
        customer = Customer.objects.create(
            name="Minimal Customer",
            email="minimal@customer.com",
            industry="Other",
            created_by=admin_user,
        )
        assert customer.phone == ""
        assert customer.company == ""
        assert customer.address == ""
        assert customer.notes == ""

    def test_customer_created_by_set_null_on_delete(self, sample_customer, admin_user):
        admin_user.delete()
        sample_customer.refresh_from_db()
        assert sample_customer.created_by is None

    def test_customer_auto_timestamps(self, sample_customer):
        assert sample_customer.created_at is not None
        assert sample_customer.updated_at is not None


# =============================================================================
# Form Tests
# =============================================================================


@pytest.mark.django_db
class TestCustomerForm:
    def test_valid_form_with_all_fields(self, sample_customer_data):
        form = CustomerForm(data=sample_customer_data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_valid_form_with_required_fields_only(self):
        data = {
            "name": "Minimal Customer",
            "email": "minimal@test.com",
            "industry": "Tech",
        }
        form = CustomerForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_invalid_form_missing_name(self, sample_customer_data):
        sample_customer_data["name"] = ""
        form = CustomerForm(data=sample_customer_data)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_invalid_form_missing_email(self, sample_customer_data):
        sample_customer_data["email"] = ""
        form = CustomerForm(data=sample_customer_data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_invalid_form_missing_industry(self, sample_customer_data):
        sample_customer_data["industry"] = ""
        form = CustomerForm(data=sample_customer_data)
        assert not form.is_valid()
        assert "industry" in form.errors

    def test_invalid_form_duplicate_email(self, sample_customer, sample_customer_data):
        sample_customer_data["email"] = "contact@acme.com"
        form = CustomerForm(data=sample_customer_data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_form_email_normalized_to_lowercase(self, sample_customer_data):
        sample_customer_data["email"] = "TEST@CUSTOMER.COM"
        form = CustomerForm(data=sample_customer_data)
        assert form.is_valid()
        assert form.cleaned_data["email"] == "test@customer.com"

    def test_invalid_phone_number_format(self, sample_customer_data):
        sample_customer_data["phone"] = "not-a-phone"
        form = CustomerForm(data=sample_customer_data)
        assert not form.is_valid()
        assert "phone" in form.errors

    def test_valid_phone_number_formats(self, sample_customer_data):
        valid_phones = ["+1-555-0100", "(555) 123-4567", "+44 20 7946 0958", "5551234567"]
        for phone in valid_phones:
            sample_customer_data["phone"] = phone
            sample_customer_data["email"] = f"test{phone[-4:]}@example.com"
            form = CustomerForm(data=sample_customer_data)
            assert form.is_valid(), f"Phone '{phone}' should be valid. Errors: {form.errors}"

    def test_form_name_max_length_validation(self, sample_customer_data):
        sample_customer_data["name"] = "A" * 129
        form = CustomerForm(data=sample_customer_data)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_form_industry_max_length_validation(self, sample_customer_data):
        sample_customer_data["industry"] = "A" * 65
        form = CustomerForm(data=sample_customer_data)
        assert not form.is_valid()
        assert "industry" in form.errors

    def test_edit_form_allows_same_email_for_same_instance(self, sample_customer):
        data = {
            "name": sample_customer.name,
            "email": sample_customer.email,
            "industry": sample_customer.industry,
            "phone": sample_customer.phone,
            "company": sample_customer.company,
            "address": sample_customer.address,
            "notes": sample_customer.notes,
        }
        form = CustomerForm(data=data, instance=sample_customer)
        assert form.is_valid(), f"Form errors: {form.errors}"


# =============================================================================
# Service Tests
# =============================================================================


@pytest.mark.django_db
class TestCustomerService:
    def setup_method(self):
        self.service = CustomerService()

    def test_create_customer_with_valid_data(self, admin_user):
        data = {
            "name": "Service Customer",
            "email": "service@customer.com",
            "industry": "Healthcare",
            "phone": "+1-555-0300",
            "company": "Service Corp",
        }
        customer = self.service.create_customer(data, user=admin_user)
        assert customer.pk is not None
        assert customer.name == "Service Customer"
        assert customer.email == "service@customer.com"
        assert customer.created_by == admin_user

    def test_create_customer_missing_required_field_raises_value_error(self, admin_user):
        data = {
            "name": "",
            "email": "test@test.com",
            "industry": "Tech",
        }
        with pytest.raises(ValueError, match="Missing required field"):
            self.service.create_customer(data, user=admin_user)

    def test_create_customer_duplicate_email_raises_integrity_error(self, sample_customer, admin_user):
        from django.db import IntegrityError

        data = {
            "name": "Another Customer",
            "email": "contact@acme.com",
            "industry": "Finance",
        }
        with pytest.raises(IntegrityError):
            self.service.create_customer(data, user=admin_user)

    def test_get_customer_existing(self, sample_customer):
        customer = self.service.get_customer(sample_customer.pk)
        assert customer is not None
        assert customer.pk == sample_customer.pk

    def test_get_customer_nonexistent(self):
        customer = self.service.get_customer(uuid.uuid4())
        assert customer is None

    def test_list_customers_no_filters(self, multiple_customers):
        queryset = self.service.list_customers()
        assert queryset.count() == 5

    def test_list_customers_filter_by_industry(self, multiple_customers):
        queryset = self.service.list_customers(filters={"industry": "Technology"})
        assert queryset.count() == 2

    def test_list_customers_filter_by_name(self, multiple_customers):
        queryset = self.service.list_customers(filters={"name": "Customer 0"})
        assert queryset.count() == 1

    def test_search_customers(self, multiple_customers):
        queryset = self.service.search_customers("Customer 1")
        assert queryset.count() == 1

    def test_search_customers_empty_query(self, multiple_customers):
        queryset = self.service.search_customers("")
        assert queryset.count() == 5

    def test_update_customer_valid_data(self, sample_customer, admin_user):
        updated = self.service.update_customer(
            sample_customer.pk,
            {"name": "Updated Acme"},
            user=admin_user,
        )
        assert updated is not None
        assert updated.name == "Updated Acme"

    def test_update_customer_nonexistent(self, admin_user):
        result = self.service.update_customer(
            uuid.uuid4(),
            {"name": "Ghost"},
            user=admin_user,
        )
        assert result is None

    def test_update_customer_no_changes(self, sample_customer, admin_user):
        updated = self.service.update_customer(
            sample_customer.pk,
            {"name": sample_customer.name},
            user=admin_user,
        )
        assert updated is not None
        assert updated.name == sample_customer.name

    def test_delete_customer_existing(self, sample_customer, admin_user):
        pk = sample_customer.pk
        result = self.service.delete_customer(pk, user=admin_user)
        assert result is True
        assert Customer.objects.filter(pk=pk).count() == 0

    def test_delete_customer_nonexistent(self, admin_user):
        result = self.service.delete_customer(uuid.uuid4(), user=admin_user)
        assert result is False

    def test_field_length_validation(self, admin_user):
        data = {
            "name": "A" * 200,
            "email": "test@test.com",
            "industry": "Tech",
        }
        with pytest.raises(ValueError, match="exceeds maximum length"):
            self.service.create_customer(data, user=admin_user)


# =============================================================================
# View Tests (using Django test client)
# =============================================================================


@pytest.mark.django_db
class TestCustomerListView:
    def test_customer_list_authenticated(self, authenticated_client, multiple_customers):
        response = authenticated_client.get(reverse("customer-list"))
        assert response.status_code == 200

    def test_customer_list_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("customer-list"))
        assert response.status_code in (302, 403)

    def test_customer_list_contains_customers(self, authenticated_client, multiple_customers):
        response = authenticated_client.get(reverse("customer-list"))
        assert response.status_code == 200
        content = response.content.decode()
        for customer in multiple_customers:
            assert customer.name in content

    def test_customer_list_filter_by_industry(self, authenticated_client, multiple_customers):
        response = authenticated_client.get(
            reverse("customer-list"), {"industry": "Technology"}
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Customer 0" in content
        assert "Customer 3" in content

    def test_customer_list_search(self, authenticated_client, multiple_customers):
        response = authenticated_client.get(
            reverse("customer-list"), {"search": "Customer 2"}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestCustomerDetailView:
    def test_customer_detail_authenticated(self, authenticated_client, sample_customer):
        response = authenticated_client.get(
            reverse("customer-detail", kwargs={"pk": sample_customer.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert sample_customer.name in content

    def test_customer_detail_unauthenticated_redirects(self, anonymous_client, sample_customer):
        response = anonymous_client.get(
            reverse("customer-detail", kwargs={"pk": sample_customer.pk})
        )
        assert response.status_code in (302, 403)

    def test_customer_detail_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("customer-detail", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestCustomerCreateView:
    def test_customer_create_get_form(self, authenticated_client):
        response = authenticated_client.get(reverse("customer-create"))
        assert response.status_code == 200

    def test_customer_create_post_valid_data(self, authenticated_client):
        data = {
            "name": "New Via View",
            "email": "newview@customer.com",
            "industry": "Retail",
            "phone": "+1-555-9999",
            "company": "View Corp",
            "address": "789 Elm St",
            "notes": "Created via view",
        }
        response = authenticated_client.post(reverse("customer-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Customer.objects.filter(email="newview@customer.com").exists()

    def test_customer_create_post_invalid_data(self, authenticated_client):
        data = {
            "name": "",
            "email": "",
            "industry": "",
        }
        response = authenticated_client.post(reverse("customer-create"), data)
        assert response.status_code == 200
        assert Customer.objects.count() == 0

    def test_customer_create_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("customer-create"))
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestCustomerEditView:
    def test_customer_edit_get_form(self, authenticated_client, sample_customer):
        response = authenticated_client.get(
            reverse("customer-edit", kwargs={"pk": sample_customer.pk})
        )
        assert response.status_code == 200

    def test_customer_edit_post_valid_data(self, authenticated_client, sample_customer):
        data = {
            "name": "Updated Acme Corp",
            "email": sample_customer.email,
            "industry": sample_customer.industry,
            "phone": sample_customer.phone,
            "company": sample_customer.company,
            "address": sample_customer.address,
            "notes": "Updated notes",
        }
        response = authenticated_client.post(
            reverse("customer-edit", kwargs={"pk": sample_customer.pk}), data
        )
        assert response.status_code in (200, 301, 302)
        sample_customer.refresh_from_db()
        assert sample_customer.name == "Updated Acme Corp"

    def test_customer_edit_post_invalid_data(self, authenticated_client, sample_customer):
        data = {
            "name": "",
            "email": sample_customer.email,
            "industry": sample_customer.industry,
        }
        response = authenticated_client.post(
            reverse("customer-edit", kwargs={"pk": sample_customer.pk}), data
        )
        assert response.status_code == 200
        sample_customer.refresh_from_db()
        assert sample_customer.name == "Acme Corp"

    def test_customer_edit_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("customer-edit", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestCustomerDeleteView:
    def test_customer_delete_authenticated(self, authenticated_client, sample_customer):
        pk = sample_customer.pk
        response = authenticated_client.post(
            reverse("customer-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not Customer.objects.filter(pk=pk).exists()

    def test_customer_delete_unauthenticated_redirects(self, anonymous_client, sample_customer):
        response = anonymous_client.post(
            reverse("customer-delete", kwargs={"pk": sample_customer.pk})
        )
        assert response.status_code in (302, 403)
        assert Customer.objects.filter(pk=sample_customer.pk).exists()


# =============================================================================
# RBAC Tests
# =============================================================================


@pytest.mark.django_db
class TestCustomerRBAC:
    def test_admin_can_access_customer_list(self, authenticated_client, multiple_customers):
        response = authenticated_client.get(reverse("customer-list"))
        assert response.status_code == 200

    def test_sales_can_access_customer_list(self, sales_client, multiple_customers):
        response = sales_client.get(reverse("customer-list"))
        assert response.status_code == 200

    def test_support_can_access_customer_list(self, support_client, multiple_customers):
        response = support_client.get(reverse("customer-list"))
        assert response.status_code == 200

    def test_admin_can_create_customer(self, authenticated_client):
        data = {
            "name": "Admin Created",
            "email": "admincreated@test.com",
            "industry": "Tech",
        }
        response = authenticated_client.post(reverse("customer-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Customer.objects.filter(email="admincreated@test.com").exists()

    def test_sales_can_create_customer(self, sales_client):
        data = {
            "name": "Sales Created",
            "email": "salescreated@test.com",
            "industry": "Finance",
        }
        response = sales_client.post(reverse("customer-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Customer.objects.filter(email="salescreated@test.com").exists()

    def test_admin_can_delete_customer(self, authenticated_client, sample_customer):
        pk = sample_customer.pk
        response = authenticated_client.post(
            reverse("customer-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not Customer.objects.filter(pk=pk).exists()

    def test_admin_can_edit_customer(self, authenticated_client, sample_customer):
        data = {
            "name": "Admin Edited",
            "email": sample_customer.email,
            "industry": sample_customer.industry,
            "phone": sample_customer.phone,
            "company": sample_customer.company,
            "address": sample_customer.address,
            "notes": sample_customer.notes,
        }
        response = authenticated_client.post(
            reverse("customer-edit", kwargs={"pk": sample_customer.pk}), data
        )
        assert response.status_code in (200, 301, 302)
        sample_customer.refresh_from_db()
        assert sample_customer.name == "Admin Edited"

    def test_unauthenticated_cannot_create_customer(self, anonymous_client):
        data = {
            "name": "Anon Created",
            "email": "anon@test.com",
            "industry": "Tech",
        }
        response = anonymous_client.post(reverse("customer-create"), data)
        assert response.status_code in (302, 403)
        assert not Customer.objects.filter(email="anon@test.com").exists()

    def test_unauthenticated_cannot_delete_customer(self, anonymous_client, sample_customer):
        pk = sample_customer.pk
        response = anonymous_client.post(
            reverse("customer-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (302, 403)
        assert Customer.objects.filter(pk=pk).exists()

    def test_customer_detail_accessible_by_all_authenticated_roles(
        self, authenticated_client, sales_client, support_client, sample_customer
    ):
        url = reverse("customer-detail", kwargs={"pk": sample_customer.pk})
        for client in [authenticated_client, sales_client, support_client]:
            response = client.get(url)
            assert response.status_code == 200