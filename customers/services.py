import uuid
from typing import Any, Dict, List, Optional

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet

from audit_logs.models import AuditLog
from customers.models import Customer


class CustomerService:
    """
    Business logic service for Customer CRUD operations.
    Wraps repository operations with validation and audit logging.
    """

    def get_customer(self, customer_id: uuid.UUID) -> Optional[Customer]:
        """
        Retrieve a single customer by ID.

        Args:
            customer_id: The UUID of the customer to retrieve.

        Returns:
            The Customer instance or None if not found.
        """
        try:
            return Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return None

    def list_customers(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        List customers with optional filtering.

        Args:
            filters: Optional dictionary of ORM-compatible filter parameters.
                Supported keys: industry, created_by, company.

        Returns:
            A QuerySet of Customer instances.
        """
        queryset = Customer.objects.all()

        if not filters:
            return queryset

        allowed_filters = {
            "industry": "industry",
            "created_by": "created_by",
            "company": "company__icontains",
            "name": "name__icontains",
            "email": "email__icontains",
        }

        orm_filters = {}
        for param_name, orm_lookup in allowed_filters.items():
            value = filters.get(param_name)
            if value is not None and str(value).strip() != "":
                orm_filters[orm_lookup] = value

        if orm_filters:
            queryset = queryset.filter(**orm_filters)

        return queryset

    def search_customers(self, query: str) -> QuerySet:
        """
        Search customers by name, email, company, or phone.

        Args:
            query: The search string.

        Returns:
            A QuerySet of matching Customer instances.
        """
        if not query or not query.strip():
            return Customer.objects.all()

        query = query.strip()
        return Customer.objects.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(company__icontains=query)
            | Q(phone__icontains=query)
        )

    def create_customer(
        self,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Customer:
        """
        Create a new customer with validation and audit logging.

        Args:
            data: Dictionary containing customer fields (name, email, phone,
                  industry, company, address, notes).
            user: The user performing the action (for audit logging and created_by).
            ip_address: Optional IP address for audit logging.

        Returns:
            The newly created Customer instance.

        Raises:
            ValueError: If required fields are missing or validation fails.
            IntegrityError: If a customer with the same email already exists.
        """
        self._validate_required_fields(data, ["name", "email", "industry"])
        self._validate_field_lengths(data)

        with transaction.atomic():
            customer_data = {
                "name": data["name"].strip(),
                "email": data["email"].strip(),
                "industry": data["industry"].strip(),
                "phone": data.get("phone", "").strip(),
                "company": data.get("company", "").strip(),
                "address": data.get("address", "").strip(),
                "notes": data.get("notes", "").strip(),
            }

            if user is not None and hasattr(user, "pk"):
                customer_data["created_by"] = user

            try:
                customer = Customer.objects.create(**customer_data)
            except IntegrityError as e:
                raise IntegrityError(
                    f"A customer with email '{customer_data['email']}' already exists."
                ) from e

            self._log_audit(
                entity_type="Customer",
                entity_id=customer.pk,
                action=AuditLog.Action.CREATE,
                user=user,
                changes={"created": customer_data},
                ip_address=ip_address,
            )

        return customer

    def update_customer(
        self,
        customer_id: uuid.UUID,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[Customer]:
        """
        Update an existing customer with validation and audit logging.

        Args:
            customer_id: The UUID of the customer to update.
            data: Dictionary containing fields to update.
            user: The user performing the action (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            The updated Customer instance, or None if not found.

        Raises:
            ValueError: If validation fails.
            IntegrityError: If the updated email conflicts with an existing customer.
        """
        customer = self.get_customer(customer_id)
        if customer is None:
            return None

        self._validate_field_lengths(data)

        updatable_fields = [
            "name",
            "email",
            "phone",
            "industry",
            "company",
            "address",
            "notes",
        ]

        changes = {}

        with transaction.atomic():
            for field in updatable_fields:
                if field in data:
                    new_value = data[field]
                    if isinstance(new_value, str):
                        new_value = new_value.strip()
                    old_value = getattr(customer, field, None)
                    if old_value != new_value:
                        changes[field] = {
                            "old": old_value,
                            "new": new_value,
                        }
                        setattr(customer, field, new_value)

            if not changes:
                return customer

            try:
                customer.save()
            except IntegrityError as e:
                raise IntegrityError(
                    f"A customer with email '{data.get('email', '')}' already exists."
                ) from e

            self._log_audit(
                entity_type="Customer",
                entity_id=customer.pk,
                action=AuditLog.Action.UPDATE,
                user=user,
                changes=changes,
                ip_address=ip_address,
            )

        return customer

    def delete_customer(
        self,
        customer_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Delete a customer by ID with audit logging.

        Args:
            customer_id: The UUID of the customer to delete.
            user: The user performing the action (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            True if the customer was deleted, False if not found.
        """
        customer = self.get_customer(customer_id)
        if customer is None:
            return False

        customer_name = str(customer)
        customer_pk = customer.pk

        with transaction.atomic():
            customer.delete()

            self._log_audit(
                entity_type="Customer",
                entity_id=customer_pk,
                action=AuditLog.Action.DELETE,
                user=user,
                changes={"deleted": customer_name},
                ip_address=ip_address,
            )

        return True

    def _validate_required_fields(
        self, data: Dict[str, Any], required_fields: List[str]
    ) -> None:
        """
        Validate that all required fields are present and non-empty.

        Raises:
            ValueError: If a required field is missing or empty.
        """
        for field in required_fields:
            value = data.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                raise ValueError(f"Missing required field: {field}")

    def _validate_field_lengths(self, data: Dict[str, Any]) -> None:
        """
        Validate field lengths against model constraints.

        Raises:
            ValueError: If a field exceeds its maximum length.
        """
        length_constraints = {
            "name": 128,
            "email": 128,
            "phone": 32,
            "industry": 64,
            "company": 128,
        }

        for field, max_length in length_constraints.items():
            value = data.get(field)
            if value is not None and isinstance(value, str) and len(value.strip()) > max_length:
                raise ValueError(
                    f"Field '{field}' exceeds maximum length of {max_length} characters."
                )

    def _log_audit(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        user=None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Create an audit log entry. Failures are silently ignored to avoid
        disrupting the primary operation.
        """
        try:
            audit_user = user if user is not None and hasattr(user, "pk") else None
            AuditLog.create_entry(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                user=audit_user,
                changes=changes or {},
                ip_address=ip_address,
            )
        except Exception:
            pass