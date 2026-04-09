import uuid
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import User
from customers.models import Customer
from deals.models import Deal, SalesStage
from deals.forms import DealForm, DealAssignForm, SalesStageForm
from deals.services import DealService, SalesStageService


@pytest.fixture
def admin_user(db):
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
    return User.objects.create_user(
        email="sales@example.com",
        password="testpass123",
        first_name="Sales",
        last_name="Rep",
        role=User.Role.SALES,
    )


@pytest.fixture
def sales_user_2(db):
    return User.objects.create_user(
        email="sales2@example.com",
        password="testpass123",
        first_name="Sales",
        last_name="Rep2",
        role=User.Role.SALES,
    )


@pytest.fixture
def support_user(db):
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
def sample_customer_2(db, admin_user):
    return Customer.objects.create(
        name="Globex Industries",
        email="info@globex.com",
        phone="+1-555-0200",
        industry="Manufacturing",
        company="Globex Industries",
        created_by=admin_user,
    )


@pytest.fixture
def sample_stages(db):
    stages_data = [
        {"name": "Lead", "order": 1, "is_active": True},
        {"name": "Qualified", "order": 2, "is_active": True},
        {"name": "Proposal", "order": 3, "is_active": True},
        {"name": "Negotiation", "order": 4, "is_active": True},
        {"name": "Closed Won", "order": 5, "is_active": True},
        {"name": "Closed Lost", "order": 6, "is_active": True},
    ]
    stages = {}
    for stage_data in stages_data:
        stage, _ = SalesStage.objects.get_or_create(
            name=stage_data["name"],
            defaults={
                "order": stage_data["order"],
                "is_active": stage_data["is_active"],
            },
        )
        stages[stage.name] = stage
    return stages


@pytest.fixture
def inactive_stage(db):
    return SalesStage.objects.create(
        name="Archived",
        order=99,
        is_active=False,
    )


@pytest.fixture
def sample_deal(db, sample_customer, sales_user, sample_stages):
    return Deal.objects.create(
        name="Acme Enterprise License",
        value=Decimal("150000.00"),
        customer=sample_customer,
        owner=sales_user,
        stage=sample_stages["Lead"],
        expected_close_date="2025-06-30",
        description="Enterprise license deal for Acme Corporation.",
    )


@pytest.fixture
def sample_deal_2(db, sample_customer_2, sales_user, sample_stages):
    return Deal.objects.create(
        name="Globex CRM Integration",
        value=Decimal("75000.00"),
        customer=sample_customer_2,
        owner=sales_user,
        stage=sample_stages["Proposal"],
        expected_close_date="2025-08-15",
        description="CRM integration project for Globex.",
    )


@pytest.fixture
def multiple_deals(db, sample_customer, sample_customer_2, sales_user, sales_user_2, sample_stages):
    deals = []
    deal_data = [
        {"name": "Deal Alpha", "value": Decimal("10000.00"), "customer": sample_customer, "owner": sales_user, "stage": sample_stages["Lead"]},
        {"name": "Deal Beta", "value": Decimal("25000.00"), "customer": sample_customer_2, "owner": sales_user, "stage": sample_stages["Qualified"]},
        {"name": "Deal Gamma", "value": Decimal("50000.00"), "customer": sample_customer, "owner": sales_user_2, "stage": sample_stages["Proposal"]},
        {"name": "Deal Delta", "value": Decimal("100000.00"), "customer": sample_customer_2, "owner": sales_user_2, "stage": sample_stages["Negotiation"]},
        {"name": "Deal Epsilon", "value": Decimal("200000.00"), "customer": sample_customer, "owner": sales_user, "stage": sample_stages["Closed Won"]},
    ]
    for d in deal_data:
        deal = Deal.objects.create(
            name=d["name"],
            value=d["value"],
            customer=d["customer"],
            owner=d["owner"],
            stage=d["stage"],
        )
        deals.append(deal)
    return deals


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
# SalesStage Model Tests
# =============================================================================


@pytest.mark.django_db
class TestSalesStageModel:
    def test_sales_stage_creation(self, sample_stages):
        stage = sample_stages["Lead"]
        assert stage.pk is not None
        assert isinstance(stage.pk, uuid.UUID)
        assert stage.name == "Lead"
        assert stage.order == 1
        assert stage.is_active is True

    def test_sales_stage_str(self, sample_stages):
        stage = sample_stages["Lead"]
        assert "Lead" in str(stage)
        assert "Order: 1" in str(stage)

    def test_sales_stage_ordering(self, sample_stages):
        stages = list(SalesStage.objects.all())
        for i in range(len(stages) - 1):
            assert stages[i].order <= stages[i + 1].order

    def test_sales_stage_unique_name(self, sample_stages):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            SalesStage.objects.create(name="Lead", order=99, is_active=True)

    def test_sales_stage_default_is_active(self, db):
        stage = SalesStage.objects.create(name="Test Stage", order=10)
        assert stage.is_active is True


# =============================================================================
# Deal Model Tests
# =============================================================================


@pytest.mark.django_db
class TestDealModel:
    def test_deal_creation_with_valid_data(self, sample_deal):
        assert sample_deal.pk is not None
        assert isinstance(sample_deal.pk, uuid.UUID)
        assert sample_deal.name == "Acme Enterprise License"
        assert sample_deal.value == Decimal("150000.00")
        assert sample_deal.customer.name == "Acme Corp"
        assert sample_deal.owner.email == "sales@example.com"
        assert sample_deal.stage.name == "Lead"

    def test_deal_str(self, sample_deal):
        result = str(sample_deal)
        assert "Acme Enterprise License" in result
        assert "150000" in result

    def test_deal_ordering_by_created_at_desc(self, multiple_deals):
        deals = list(Deal.objects.all())
        for i in range(len(deals) - 1):
            assert deals[i].created_at >= deals[i + 1].created_at

    def test_deal_auto_timestamps(self, sample_deal):
        assert sample_deal.created_at is not None
        assert sample_deal.updated_at is not None

    def test_deal_owner_set_null_on_delete(self, sample_deal, sales_user):
        sales_user.delete()
        sample_deal.refresh_from_db()
        assert sample_deal.owner is None

    def test_deal_customer_cascade_on_delete(self, sample_deal, sample_customer):
        pk = sample_deal.pk
        sample_customer.delete()
        assert not Deal.objects.filter(pk=pk).exists()

    def test_deal_stage_protect_on_delete(self, sample_deal, sample_stages):
        from django.db import models

        with pytest.raises(models.ProtectedError):
            sample_stages["Lead"].delete()

    def test_deal_blank_optional_fields(self, sample_customer, sales_user, sample_stages):
        deal = Deal.objects.create(
            name="Minimal Deal",
            value=Decimal("1000.00"),
            customer=sample_customer,
            stage=sample_stages["Lead"],
        )
        assert deal.description == ""
        assert deal.expected_close_date is None
        assert deal.owner is None


# =============================================================================
# DealForm Tests
# =============================================================================


@pytest.mark.django_db
class TestDealForm:
    def test_valid_form_with_all_fields(self, sample_customer, sample_stages):
        data = {
            "name": "New Deal",
            "value": "50000.00",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
            "expected_close_date": "2025-12-31",
            "description": "A new deal",
        }
        form = DealForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_valid_form_with_required_fields_only(self, sample_customer, sample_stages):
        data = {
            "name": "Minimal Deal",
            "value": "1000.00",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
        }
        form = DealForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_invalid_form_missing_name(self, sample_customer, sample_stages):
        data = {
            "name": "",
            "value": "1000.00",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
        }
        form = DealForm(data=data)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_invalid_form_missing_value(self, sample_customer, sample_stages):
        data = {
            "name": "No Value Deal",
            "value": "",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
        }
        form = DealForm(data=data)
        assert not form.is_valid()
        assert "value" in form.errors

    def test_invalid_form_missing_customer(self, sample_stages):
        data = {
            "name": "No Customer Deal",
            "value": "1000.00",
            "customer": "",
            "stage": sample_stages["Lead"].pk,
        }
        form = DealForm(data=data)
        assert not form.is_valid()
        assert "customer" in form.errors

    def test_invalid_form_missing_stage(self, sample_customer):
        data = {
            "name": "No Stage Deal",
            "value": "1000.00",
            "customer": sample_customer.pk,
            "stage": "",
        }
        form = DealForm(data=data)
        assert not form.is_valid()
        assert "stage" in form.errors

    def test_invalid_form_zero_value(self, sample_customer, sample_stages):
        data = {
            "name": "Zero Value Deal",
            "value": "0",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
        }
        form = DealForm(data=data)
        assert not form.is_valid()
        assert "value" in form.errors

    def test_invalid_form_negative_value(self, sample_customer, sample_stages):
        data = {
            "name": "Negative Value Deal",
            "value": "-1000.00",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
        }
        form = DealForm(data=data)
        assert not form.is_valid()
        assert "value" in form.errors

    def test_form_name_max_length_validation(self, sample_customer, sample_stages):
        data = {
            "name": "A" * 129,
            "value": "1000.00",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
        }
        form = DealForm(data=data)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_form_only_shows_active_stages(self, sample_stages, inactive_stage, sample_customer):
        form = DealForm()
        stage_queryset = form.fields["stage"].queryset
        assert inactive_stage not in stage_queryset
        for stage in sample_stages.values():
            assert stage in stage_queryset


# =============================================================================
# SalesStageForm Tests
# =============================================================================


@pytest.mark.django_db
class TestSalesStageForm:
    def test_valid_form(self):
        data = {
            "name": "New Stage",
            "order": 10,
            "is_active": True,
        }
        form = SalesStageForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_invalid_form_missing_name(self):
        data = {
            "name": "",
            "order": 10,
            "is_active": True,
        }
        form = SalesStageForm(data=data)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_invalid_form_missing_order(self):
        data = {
            "name": "No Order Stage",
            "order": "",
            "is_active": True,
        }
        form = SalesStageForm(data=data)
        assert not form.is_valid()
        assert "order" in form.errors

    def test_invalid_form_negative_order(self):
        data = {
            "name": "Negative Order",
            "order": -1,
            "is_active": True,
        }
        form = SalesStageForm(data=data)
        assert not form.is_valid()
        assert "order" in form.errors

    def test_invalid_form_duplicate_name(self, sample_stages):
        data = {
            "name": "Lead",
            "order": 99,
            "is_active": True,
        }
        form = SalesStageForm(data=data)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_form_name_max_length(self):
        data = {
            "name": "A" * 65,
            "order": 10,
            "is_active": True,
        }
        form = SalesStageForm(data=data)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_edit_form_allows_same_name_for_same_instance(self, sample_stages):
        stage = sample_stages["Lead"]
        data = {
            "name": "Lead",
            "order": stage.order,
            "is_active": stage.is_active,
        }
        form = SalesStageForm(data=data, instance=stage)
        assert form.is_valid(), f"Form errors: {form.errors}"


# =============================================================================
# DealAssignForm Tests
# =============================================================================


@pytest.mark.django_db
class TestDealAssignForm:
    def test_valid_assign_form(self, sample_deal, sales_user_2):
        form = DealAssignForm(data={"owner": sales_user_2.pk}, deal=sample_deal)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_assign_form_saves_owner(self, sample_deal, sales_user_2):
        form = DealAssignForm(data={"owner": sales_user_2.pk}, deal=sample_deal)
        assert form.is_valid()
        deal = form.save()
        deal.refresh_from_db()
        assert deal.owner == sales_user_2

    def test_invalid_assign_form_missing_owner(self, sample_deal):
        form = DealAssignForm(data={"owner": ""}, deal=sample_deal)
        assert not form.is_valid()
        assert "owner" in form.errors

    def test_assign_form_only_shows_active_users(self, sample_deal):
        form = DealAssignForm(deal=sample_deal)
        queryset = form.fields["owner"].queryset
        for user in queryset:
            assert user.is_active is True


# =============================================================================
# SalesStageService Tests
# =============================================================================


@pytest.mark.django_db
class TestSalesStageService:
    def setup_method(self):
        self.service = SalesStageService()

    def test_create_stage(self, admin_user):
        stage = self.service.create_stage(
            {"name": "Discovery", "order": 0, "is_active": True},
            user=admin_user,
        )
        assert stage.pk is not None
        assert stage.name == "Discovery"
        assert stage.order == 0

    def test_create_stage_missing_name_raises_value_error(self, admin_user):
        with pytest.raises(ValueError, match="Missing required field"):
            self.service.create_stage({"name": "", "order": 0}, user=admin_user)

    def test_create_stage_duplicate_name_raises_integrity_error(self, sample_stages, admin_user):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            self.service.create_stage(
                {"name": "Lead", "order": 99},
                user=admin_user,
            )

    def test_get_stage_existing(self, sample_stages):
        stage = self.service.get_stage(sample_stages["Lead"].pk)
        assert stage is not None
        assert stage.name == "Lead"

    def test_get_stage_nonexistent(self):
        stage = self.service.get_stage(uuid.uuid4())
        assert stage is None

    def test_list_stages_active_only(self, sample_stages, inactive_stage):
        stages = self.service.list_stages(include_inactive=False)
        assert inactive_stage not in stages
        assert stages.count() == 6

    def test_list_stages_include_inactive(self, sample_stages, inactive_stage):
        stages = self.service.list_stages(include_inactive=True)
        assert inactive_stage in stages
        assert stages.count() == 7

    def test_update_stage(self, sample_stages, admin_user):
        stage = self.service.update_stage(
            sample_stages["Lead"].pk,
            {"name": "New Lead", "order": 0},
            user=admin_user,
        )
        assert stage is not None
        assert stage.name == "New Lead"
        assert stage.order == 0

    def test_update_stage_nonexistent(self, admin_user):
        result = self.service.update_stage(
            uuid.uuid4(),
            {"name": "Ghost"},
            user=admin_user,
        )
        assert result is None

    def test_update_stage_no_changes(self, sample_stages, admin_user):
        stage = sample_stages["Lead"]
        updated = self.service.update_stage(
            stage.pk,
            {"name": stage.name, "order": stage.order},
            user=admin_user,
        )
        assert updated is not None
        assert updated.name == stage.name

    def test_delete_stage_no_deals(self, db, admin_user):
        stage = SalesStage.objects.create(name="Temp Stage", order=50, is_active=True)
        result = self.service.delete_stage(stage.pk, user=admin_user)
        assert result is True
        assert not SalesStage.objects.filter(pk=stage.pk).exists()

    def test_delete_stage_with_deals_raises_value_error(self, sample_deal, sample_stages, admin_user):
        with pytest.raises(ValueError, match="Cannot delete"):
            self.service.delete_stage(sample_stages["Lead"].pk, user=admin_user)

    def test_delete_stage_nonexistent(self, admin_user):
        result = self.service.delete_stage(uuid.uuid4(), user=admin_user)
        assert result is False


# =============================================================================
# DealService Tests
# =============================================================================


@pytest.mark.django_db
class TestDealService:
    def setup_method(self):
        self.service = DealService()

    def test_create_deal_with_valid_data(self, sample_customer, sample_stages, sales_user):
        data = {
            "name": "Service Deal",
            "value": Decimal("50000.00"),
            "customer": sample_customer,
            "stage": sample_stages["Lead"],
            "description": "Created via service",
        }
        deal = self.service.create_deal(data, user=sales_user)
        assert deal.pk is not None
        assert deal.name == "Service Deal"
        assert deal.value == Decimal("50000.00")
        assert deal.owner == sales_user

    def test_create_deal_missing_required_field_raises_value_error(self, sample_customer, sample_stages, sales_user):
        data = {
            "name": "",
            "value": Decimal("1000.00"),
            "customer": sample_customer,
            "stage": sample_stages["Lead"],
        }
        with pytest.raises(ValueError, match="Missing required field"):
            self.service.create_deal(data, user=sales_user)

    def test_create_deal_negative_value_raises_value_error(self, sample_customer, sample_stages, sales_user):
        data = {
            "name": "Bad Deal",
            "value": Decimal("-100.00"),
            "customer": sample_customer,
            "stage": sample_stages["Lead"],
        }
        with pytest.raises(ValueError, match="positive number"):
            self.service.create_deal(data, user=sales_user)

    def test_get_deal_existing(self, sample_deal):
        deal = self.service.get_deal(sample_deal.pk)
        assert deal is not None
        assert deal.pk == sample_deal.pk

    def test_get_deal_nonexistent(self):
        deal = self.service.get_deal(uuid.uuid4())
        assert deal is None

    def test_list_deals_no_filters(self, multiple_deals):
        queryset = self.service.list_deals()
        assert queryset.count() == 5

    def test_list_deals_filter_by_customer(self, multiple_deals, sample_customer):
        queryset = self.service.list_deals(filters={"customer": sample_customer.pk})
        assert queryset.count() == 3

    def test_list_deals_filter_by_owner(self, multiple_deals, sales_user):
        queryset = self.service.list_deals(filters={"owner": sales_user.pk})
        assert queryset.count() == 3

    def test_list_deals_filter_by_stage(self, multiple_deals, sample_stages):
        queryset = self.service.list_deals(filters={"stage": sample_stages["Lead"].pk})
        assert queryset.count() == 1

    def test_list_deals_filter_by_search(self, multiple_deals):
        queryset = self.service.list_deals(filters={"search": "Alpha"})
        assert queryset.count() == 1

    def test_list_deals_filter_by_min_value(self, multiple_deals):
        queryset = self.service.list_deals(filters={"min_value": "50000"})
        assert queryset.count() == 3

    def test_list_deals_filter_by_max_value(self, multiple_deals):
        queryset = self.service.list_deals(filters={"max_value": "25000"})
        assert queryset.count() == 2

    def test_search_deals(self, multiple_deals):
        queryset = self.service.search_deals("Gamma")
        assert queryset.count() == 1

    def test_search_deals_empty_query(self, multiple_deals):
        queryset = self.service.search_deals("")
        assert queryset.count() == 5

    def test_update_deal_valid_data(self, sample_deal, admin_user):
        updated = self.service.update_deal(
            sample_deal.pk,
            {"name": "Updated Deal Name"},
            user=admin_user,
        )
        assert updated is not None
        assert updated.name == "Updated Deal Name"

    def test_update_deal_value(self, sample_deal, admin_user):
        updated = self.service.update_deal(
            sample_deal.pk,
            {"value": Decimal("200000.00")},
            user=admin_user,
        )
        assert updated is not None
        assert updated.value == Decimal("200000.00")

    def test_update_deal_stage_progression(self, sample_deal, sample_stages, admin_user):
        updated = self.service.update_deal(
            sample_deal.pk,
            {"stage": sample_stages["Qualified"]},
            user=admin_user,
        )
        assert updated is not None
        assert updated.stage == sample_stages["Qualified"]

    def test_update_deal_nonexistent(self, admin_user):
        result = self.service.update_deal(
            uuid.uuid4(),
            {"name": "Ghost"},
            user=admin_user,
        )
        assert result is None

    def test_update_deal_no_changes(self, sample_deal, admin_user):
        updated = self.service.update_deal(
            sample_deal.pk,
            {"name": sample_deal.name},
            user=admin_user,
        )
        assert updated is not None
        assert updated.name == sample_deal.name

    def test_delete_deal_existing(self, sample_deal, admin_user):
        pk = sample_deal.pk
        result = self.service.delete_deal(pk, user=admin_user)
        assert result is True
        assert not Deal.objects.filter(pk=pk).exists()

    def test_delete_deal_nonexistent(self, admin_user):
        result = self.service.delete_deal(uuid.uuid4(), user=admin_user)
        assert result is False

    def test_assign_deal_owner(self, sample_deal, sales_user_2, admin_user):
        deal = self.service.assign_deal_owner(
            sample_deal.pk,
            sales_user_2.pk,
            user=admin_user,
        )
        assert deal is not None
        assert deal.owner == sales_user_2

    def test_assign_deal_owner_same_owner(self, sample_deal, sales_user, admin_user):
        deal = self.service.assign_deal_owner(
            sample_deal.pk,
            sales_user.pk,
            user=admin_user,
        )
        assert deal is not None
        assert deal.owner == sales_user

    def test_assign_deal_owner_nonexistent_deal(self, sales_user, admin_user):
        result = self.service.assign_deal_owner(
            uuid.uuid4(),
            sales_user.pk,
            user=admin_user,
        )
        assert result is None

    def test_assign_deal_owner_nonexistent_user(self, sample_deal, admin_user):
        with pytest.raises(ValueError, match="not found"):
            self.service.assign_deal_owner(
                sample_deal.pk,
                uuid.uuid4(),
                user=admin_user,
            )

    def test_get_deals_by_customer(self, multiple_deals, sample_customer):
        queryset = self.service.get_deals_by_customer(sample_customer.pk)
        assert queryset.count() == 3

    def test_get_deals_by_owner(self, multiple_deals, sales_user):
        queryset = self.service.get_deals_by_owner(sales_user.pk)
        assert queryset.count() == 3

    def test_get_deals_by_stage(self, multiple_deals, sample_stages):
        queryset = self.service.get_deals_by_stage(sample_stages["Proposal"].pk)
        assert queryset.count() == 1

    def test_deal_stage_progression_full_cycle(self, sample_deal, sample_stages, admin_user):
        stage_order = ["Lead", "Qualified", "Proposal", "Negotiation", "Closed Won"]
        for stage_name in stage_order:
            updated = self.service.update_deal(
                sample_deal.pk,
                {"stage": sample_stages[stage_name]},
                user=admin_user,
            )
            assert updated is not None
            assert updated.stage.name == stage_name

    def test_deal_value_validation_exceeds_max(self, sample_customer, sample_stages, sales_user):
        data = {
            "name": "Huge Deal",
            "value": Decimal("99999999999.00"),
            "customer": sample_customer,
            "stage": sample_stages["Lead"],
        }
        with pytest.raises(ValueError, match="exceeds maximum"):
            self.service.create_deal(data, user=sales_user)


# =============================================================================
# Deal List View Tests
# =============================================================================


@pytest.mark.django_db
class TestDealListView:
    def test_deal_list_authenticated(self, authenticated_client, multiple_deals):
        response = authenticated_client.get(reverse("deal-list"))
        assert response.status_code == 200

    def test_deal_list_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("deal-list"))
        assert response.status_code in (302, 403)

    def test_deal_list_contains_deals(self, authenticated_client, multiple_deals):
        response = authenticated_client.get(reverse("deal-list"))
        assert response.status_code == 200
        content = response.content.decode()
        for deal in multiple_deals:
            assert deal.name in content

    def test_deal_list_filter_by_search(self, authenticated_client, multiple_deals):
        response = authenticated_client.get(
            reverse("deal-list"), {"search": "Alpha"}
        )
        assert response.status_code == 200


# =============================================================================
# Deal Detail View Tests
# =============================================================================


@pytest.mark.django_db
class TestDealDetailView:
    def test_deal_detail_authenticated(self, authenticated_client, sample_deal):
        response = authenticated_client.get(
            reverse("deal-detail", kwargs={"pk": sample_deal.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert sample_deal.name in content

    def test_deal_detail_unauthenticated_redirects(self, anonymous_client, sample_deal):
        response = anonymous_client.get(
            reverse("deal-detail", kwargs={"pk": sample_deal.pk})
        )
        assert response.status_code in (302, 403)

    def test_deal_detail_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("deal-detail", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


# =============================================================================
# Deal Create View Tests
# =============================================================================


@pytest.mark.django_db
class TestDealCreateView:
    def test_deal_create_get_form(self, authenticated_client, sample_stages):
        response = authenticated_client.get(reverse("deal-create"))
        assert response.status_code == 200

    def test_deal_create_post_valid_data(self, authenticated_client, sample_customer, sample_stages):
        data = {
            "name": "New Deal Via View",
            "value": "75000.00",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
            "description": "Created via view",
        }
        response = authenticated_client.post(reverse("deal-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Deal.objects.filter(name="New Deal Via View").exists()

    def test_deal_create_post_invalid_data(self, authenticated_client, sample_stages):
        data = {
            "name": "",
            "value": "",
            "customer": "",
            "stage": "",
        }
        response = authenticated_client.post(reverse("deal-create"), data)
        assert response.status_code == 200

    def test_deal_create_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("deal-create"))
        assert response.status_code in (302, 403)


# =============================================================================
# Deal Update View Tests
# =============================================================================


@pytest.mark.django_db
class TestDealUpdateView:
    def test_deal_update_get_form(self, authenticated_client, sample_deal):
        response = authenticated_client.get(
            reverse("deal-update", kwargs={"pk": sample_deal.pk})
        )
        assert response.status_code == 200

    def test_deal_update_post_valid_data(self, authenticated_client, sample_deal, sample_stages):
        data = {
            "name": "Updated Deal Name",
            "value": "200000.00",
            "customer": sample_deal.customer.pk,
            "stage": sample_stages["Qualified"].pk,
            "description": "Updated description",
        }
        response = authenticated_client.post(
            reverse("deal-update", kwargs={"pk": sample_deal.pk}), data
        )
        assert response.status_code in (200, 301, 302)
        sample_deal.refresh_from_db()
        assert sample_deal.name == "Updated Deal Name"

    def test_deal_update_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("deal-update", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


# =============================================================================
# Deal Delete View Tests
# =============================================================================


@pytest.mark.django_db
class TestDealDeleteView:
    def test_deal_delete_authenticated(self, authenticated_client, sample_deal):
        pk = sample_deal.pk
        response = authenticated_client.post(
            reverse("deal-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not Deal.objects.filter(pk=pk).exists()

    def test_deal_delete_unauthenticated_redirects(self, anonymous_client, sample_deal):
        response = anonymous_client.post(
            reverse("deal-delete", kwargs={"pk": sample_deal.pk})
        )
        assert response.status_code in (302, 403)
        assert Deal.objects.filter(pk=sample_deal.pk).exists()


# =============================================================================
# Pipeline View Tests
# =============================================================================


@pytest.mark.django_db
class TestPipelineView:
    def test_pipeline_list_authenticated(self, authenticated_client, sample_stages, multiple_deals):
        response = authenticated_client.get(reverse("pipeline-list"))
        assert response.status_code == 200

    def test_pipeline_list_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("pipeline-list"))
        assert response.status_code in (302, 403)

    def test_pipeline_list_contains_stage_names(self, authenticated_client, sample_stages, multiple_deals):
        response = authenticated_client.get(reverse("pipeline-list"))
        assert response.status_code == 200
        content = response.content.decode()
        for stage_name in sample_stages:
            assert stage_name in content

    def test_pipeline_list_contains_deal_names(self, authenticated_client, sample_stages, multiple_deals):
        response = authenticated_client.get(reverse("pipeline-list"))
        assert response.status_code == 200
        content = response.content.decode()
        for deal in multiple_deals:
            assert deal.name in content


# =============================================================================
# Deal Stage Progression View Tests
# =============================================================================


@pytest.mark.django_db
class TestDealStageProgression:
    def test_deal_stage_update_via_service(self, sample_deal, sample_stages, admin_user):
        service = DealService()
        updated = service.update_deal(
            sample_deal.pk,
            {"stage": sample_stages["Qualified"]},
            user=admin_user,
        )
        assert updated.stage.name == "Qualified"

        updated = service.update_deal(
            sample_deal.pk,
            {"stage": sample_stages["Proposal"]},
            user=admin_user,
        )
        assert updated.stage.name == "Proposal"

    def test_deal_can_move_to_closed_won(self, sample_deal, sample_stages, admin_user):
        service = DealService()
        updated = service.update_deal(
            sample_deal.pk,
            {"stage": sample_stages["Closed Won"]},
            user=admin_user,
        )
        assert updated.stage.name == "Closed Won"

    def test_deal_can_move_to_closed_lost(self, sample_deal, sample_stages, admin_user):
        service = DealService()
        updated = service.update_deal(
            sample_deal.pk,
            {"stage": sample_stages["Closed Lost"]},
            user=admin_user,
        )
        assert updated.stage.name == "Closed Lost"

    def test_deal_can_move_backwards(self, sample_deal, sample_stages, admin_user):
        service = DealService()
        service.update_deal(
            sample_deal.pk,
            {"stage": sample_stages["Negotiation"]},
            user=admin_user,
        )
        updated = service.update_deal(
            sample_deal.pk,
            {"stage": sample_stages["Lead"]},
            user=admin_user,
        )
        assert updated.stage.name == "Lead"


# =============================================================================
# Deal Assignment Tests
# =============================================================================


@pytest.mark.django_db
class TestDealAssignment:
    def test_assign_deal_to_different_owner(self, sample_deal, sales_user_2, admin_user):
        service = DealService()
        deal = service.assign_deal_owner(
            sample_deal.pk,
            sales_user_2.pk,
            user=admin_user,
        )
        assert deal.owner == sales_user_2

    def test_reassign_deal_back_to_original_owner(self, sample_deal, sales_user, sales_user_2, admin_user):
        service = DealService()
        service.assign_deal_owner(sample_deal.pk, sales_user_2.pk, user=admin_user)
        deal = service.assign_deal_owner(sample_deal.pk, sales_user.pk, user=admin_user)
        assert deal.owner == sales_user

    def test_assign_deal_preserves_other_fields(self, sample_deal, sales_user_2, admin_user):
        original_name = sample_deal.name
        original_value = sample_deal.value
        original_stage = sample_deal.stage

        service = DealService()
        deal = service.assign_deal_owner(
            sample_deal.pk,
            sales_user_2.pk,
            user=admin_user,
        )
        assert deal.name == original_name
        assert deal.value == original_value
        assert deal.stage == original_stage


# =============================================================================
# RBAC Tests
# =============================================================================


@pytest.mark.django_db
class TestDealRBAC:
    def test_admin_can_access_deal_list(self, authenticated_client, multiple_deals):
        response = authenticated_client.get(reverse("deal-list"))
        assert response.status_code == 200

    def test_sales_can_access_deal_list(self, sales_client, multiple_deals):
        response = sales_client.get(reverse("deal-list"))
        assert response.status_code == 200

    def test_support_can_access_deal_list(self, support_client, multiple_deals):
        response = support_client.get(reverse("deal-list"))
        assert response.status_code == 200

    def test_admin_can_create_deal(self, authenticated_client, sample_customer, sample_stages):
        data = {
            "name": "Admin Created Deal",
            "value": "10000.00",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
        }
        response = authenticated_client.post(reverse("deal-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Deal.objects.filter(name="Admin Created Deal").exists()

    def test_sales_can_create_deal(self, sales_client, sample_customer, sample_stages):
        data = {
            "name": "Sales Created Deal",
            "value": "20000.00",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
        }
        response = sales_client.post(reverse("deal-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Deal.objects.filter(name="Sales Created Deal").exists()

    def test_admin_can_delete_deal(self, authenticated_client, sample_deal):
        pk = sample_deal.pk
        response = authenticated_client.post(
            reverse("deal-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not Deal.objects.filter(pk=pk).exists()

    def test_admin_can_update_deal(self, authenticated_client, sample_deal, sample_stages):
        data = {
            "name": "Admin Updated Deal",
            "value": "300000.00",
            "customer": sample_deal.customer.pk,
            "stage": sample_stages["Qualified"].pk,
            "description": "Updated by admin",
        }
        response = authenticated_client.post(
            reverse("deal-update", kwargs={"pk": sample_deal.pk}), data
        )
        assert response.status_code in (200, 301, 302)
        sample_deal.refresh_from_db()
        assert sample_deal.name == "Admin Updated Deal"

    def test_unauthenticated_cannot_create_deal(self, anonymous_client, sample_customer, sample_stages):
        data = {
            "name": "Anon Deal",
            "value": "1000.00",
            "customer": sample_customer.pk,
            "stage": sample_stages["Lead"].pk,
        }
        response = anonymous_client.post(reverse("deal-create"), data)
        assert response.status_code in (302, 403)
        assert not Deal.objects.filter(name="Anon Deal").exists()

    def test_unauthenticated_cannot_delete_deal(self, anonymous_client, sample_deal):
        pk = sample_deal.pk
        response = anonymous_client.post(
            reverse("deal-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (302, 403)
        assert Deal.objects.filter(pk=pk).exists()

    def test_deal_detail_accessible_by_all_authenticated_roles(
        self, authenticated_client, sales_client, support_client, sample_deal
    ):
        url = reverse("deal-detail", kwargs={"pk": sample_deal.pk})
        for client in [authenticated_client, sales_client, support_client]:
            response = client.get(url)
            assert response.status_code == 200

    def test_pipeline_accessible_by_all_authenticated_roles(
        self, authenticated_client, sales_client, support_client, sample_stages, multiple_deals
    ):
        url = reverse("pipeline-list")
        for client in [authenticated_client, sales_client, support_client]:
            response = client.get(url)
            assert response.status_code == 200

    def test_unauthenticated_cannot_access_pipeline(self, anonymous_client):
        response = anonymous_client.get(reverse("pipeline-list"))
        assert response.status_code in (302, 403)