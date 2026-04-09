import pytest
from decimal import Decimal

from django.test import Client

from accounts.models import User
from customers.models import Customer
from deals.models import Deal, SalesStage


@pytest.fixture
def create_user(db):
    """
    Factory fixture to create User instances with a given role.

    Usage:
        user = create_user(email="test@example.com", role="admin")
        user = create_user()  # defaults to sales role
    """
    created_users = []
    counter = [0]

    def _create_user(
        email=None,
        password="testpassword123",
        first_name="Test",
        last_name="User",
        role=User.Role.SALES,
        is_active=True,
        is_staff=False,
        is_superuser=False,
        phone_number="",
        job_title="",
        department="",
        **kwargs,
    ):
        counter[0] += 1
        if email is None:
            email = f"testuser{counter[0]}@example.com"

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_active=is_active,
            is_staff=is_staff,
            is_superuser=is_superuser,
            phone_number=phone_number,
            job_title=job_title,
            department=department,
            **kwargs,
        )
        created_users.append(user)
        return user

    return _create_user


@pytest.fixture
def create_customer(db, create_user):
    """
    Factory fixture to create Customer instances.

    Usage:
        customer = create_customer(name="Acme Corp", email="acme@example.com")
        customer = create_customer()  # uses defaults
    """
    counter = [0]

    def _create_customer(
        name=None,
        email=None,
        phone="",
        industry="Technology",
        company="",
        address="",
        notes="",
        created_by=None,
        **kwargs,
    ):
        counter[0] += 1
        if name is None:
            name = f"Test Customer {counter[0]}"
        if email is None:
            email = f"customer{counter[0]}@example.com"
        if created_by is None:
            created_by = create_user(
                email=f"customer_creator_{counter[0]}@example.com",
                role=User.Role.SALES,
            )

        customer = Customer.objects.create(
            name=name,
            email=email,
            phone=phone,
            industry=industry,
            company=company,
            address=address,
            notes=notes,
            created_by=created_by,
            **kwargs,
        )
        return customer

    return _create_customer


@pytest.fixture
def sample_sales_stages(db):
    """
    Creates a default set of sales stages for pipeline testing.

    Returns:
        dict: A dictionary mapping stage name to SalesStage instance.
    """
    stages_data = [
        {"name": "Prospecting", "order": 1, "is_active": True},
        {"name": "Qualification", "order": 2, "is_active": True},
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
def create_deal(db, create_customer, sample_sales_stages, create_user):
    """
    Factory fixture to create Deal instances with a specified stage.

    Usage:
        deal = create_deal(name="Big Deal", value=50000, stage_name="Proposal")
        deal = create_deal()  # uses defaults
    """
    counter = [0]

    def _create_deal(
        name=None,
        value=None,
        customer=None,
        owner=None,
        stage=None,
        stage_name="Prospecting",
        expected_close_date=None,
        description="",
        **kwargs,
    ):
        counter[0] += 1
        if name is None:
            name = f"Test Deal {counter[0]}"
        if value is None:
            value = Decimal("10000.00")
        if customer is None:
            customer = create_customer(
                name=f"Deal Customer {counter[0]}",
                email=f"deal_customer_{counter[0]}@example.com",
            )
        if owner is None:
            owner = create_user(
                email=f"deal_owner_{counter[0]}@example.com",
                role=User.Role.SALES,
            )
        if stage is None:
            stage = sample_sales_stages.get(stage_name)
            if stage is None:
                stage = SalesStage.objects.create(
                    name=stage_name,
                    order=99,
                    is_active=True,
                )

        deal = Deal.objects.create(
            name=name,
            value=value,
            customer=customer,
            owner=owner,
            stage=stage,
            expected_close_date=expected_close_date,
            description=description,
            **kwargs,
        )
        return deal

    return _create_deal


@pytest.fixture
def authenticated_client(db, create_user):
    """
    Factory fixture that returns a Django test Client logged in as a user
    with the specified role.

    Usage:
        client = authenticated_client(role="admin")
        client = authenticated_client(role="sales", email="sales@example.com")
        client = authenticated_client()  # defaults to sales role
    """
    counter = [0]

    def _authenticated_client(
        role=User.Role.SALES,
        email=None,
        password="testpassword123",
        is_staff=False,
        is_superuser=False,
        **kwargs,
    ):
        counter[0] += 1
        if email is None:
            email = f"authclient{counter[0]}@example.com"

        if role == User.Role.ADMIN:
            is_staff = True

        user = create_user(
            email=email,
            password=password,
            role=role,
            is_staff=is_staff,
            is_superuser=is_superuser,
            **kwargs,
        )

        client = Client()
        logged_in = client.login(email=email, password=password)
        if not logged_in:
            raise RuntimeError(
                f"Failed to log in user {email}. "
                "Ensure the authentication backend supports email-based login."
            )

        client.user = user
        return client

    return _authenticated_client