import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet

from audit_logs.models import AuditLog
from deals.models import Deal, SalesStage


class SalesStageService:
    """
    Business logic service for SalesStage CRUD operations.
    """

    def get_stage(self, stage_id: uuid.UUID) -> Optional[SalesStage]:
        """
        Retrieve a single sales stage by ID.

        Args:
            stage_id: The UUID of the sales stage to retrieve.

        Returns:
            The SalesStage instance or None if not found.
        """
        try:
            return SalesStage.objects.get(pk=stage_id)
        except SalesStage.DoesNotExist:
            return None

    def list_stages(self, include_inactive: bool = False) -> QuerySet:
        """
        List all sales stages, ordered by their order field.

        Args:
            include_inactive: If True, include inactive stages.

        Returns:
            A QuerySet of SalesStage instances.
        """
        queryset = SalesStage.objects.all()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by("order")

    def create_stage(
        self,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> SalesStage:
        """
        Create a new sales stage with validation and audit logging.

        Args:
            data: Dictionary containing stage fields (name, order, is_active).
            user: The user performing the action (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            The newly created SalesStage instance.

        Raises:
            ValueError: If required fields are missing or validation fails.
            IntegrityError: If a stage with the same name already exists.
        """
        self._validate_stage_required_fields(data)
        self._validate_stage_field_lengths(data)

        with transaction.atomic():
            stage_data = {
                "name": data["name"].strip(),
                "order": int(data.get("order", 0)),
                "is_active": data.get("is_active", True),
            }

            try:
                stage = SalesStage.objects.create(**stage_data)
            except IntegrityError as e:
                raise IntegrityError(
                    f"A sales stage with name '{stage_data['name']}' already exists."
                ) from e

            self._log_audit(
                entity_type="SalesStage",
                entity_id=stage.pk,
                action=AuditLog.Action.CREATE,
                user=user,
                changes={"created": stage_data},
                ip_address=ip_address,
            )

        return stage

    def update_stage(
        self,
        stage_id: uuid.UUID,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[SalesStage]:
        """
        Update an existing sales stage with validation and audit logging.

        Args:
            stage_id: The UUID of the sales stage to update.
            data: Dictionary containing fields to update.
            user: The user performing the action (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            The updated SalesStage instance, or None if not found.

        Raises:
            ValueError: If validation fails.
            IntegrityError: If the updated name conflicts with an existing stage.
        """
        stage = self.get_stage(stage_id)
        if stage is None:
            return None

        self._validate_stage_field_lengths(data)

        updatable_fields = ["name", "order", "is_active"]
        changes = {}

        with transaction.atomic():
            for field in updatable_fields:
                if field in data:
                    new_value = data[field]
                    if field == "name" and isinstance(new_value, str):
                        new_value = new_value.strip()
                    if field == "order":
                        new_value = int(new_value)
                    if field == "is_active":
                        new_value = bool(new_value)

                    old_value = getattr(stage, field, None)
                    if old_value != new_value:
                        changes[field] = {
                            "old": old_value,
                            "new": new_value,
                        }
                        setattr(stage, field, new_value)

            if not changes:
                return stage

            try:
                stage.save()
            except IntegrityError as e:
                raise IntegrityError(
                    f"A sales stage with name '{data.get('name', '')}' already exists."
                ) from e

            self._log_audit(
                entity_type="SalesStage",
                entity_id=stage.pk,
                action=AuditLog.Action.UPDATE,
                user=user,
                changes=changes,
                ip_address=ip_address,
            )

        return stage

    def delete_stage(
        self,
        stage_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Delete a sales stage by ID with audit logging.

        Args:
            stage_id: The UUID of the sales stage to delete.
            user: The user performing the action (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            True if the stage was deleted, False if not found.

        Raises:
            ValueError: If the stage has associated deals.
        """
        stage = self.get_stage(stage_id)
        if stage is None:
            return False

        deal_count = Deal.objects.filter(stage=stage).count()
        if deal_count > 0:
            raise ValueError(
                f"Cannot delete sales stage '{stage.name}' because it has "
                f"{deal_count} associated deal(s). Reassign or delete them first."
            )

        stage_name = str(stage)
        stage_pk = stage.pk

        with transaction.atomic():
            stage.delete()

            self._log_audit(
                entity_type="SalesStage",
                entity_id=stage_pk,
                action=AuditLog.Action.DELETE,
                user=user,
                changes={"deleted": stage_name},
                ip_address=ip_address,
            )

        return True

    def _validate_stage_required_fields(self, data: Dict[str, Any]) -> None:
        """
        Validate that all required fields are present and non-empty.

        Raises:
            ValueError: If a required field is missing or empty.
        """
        name = data.get("name")
        if name is None or (isinstance(name, str) and name.strip() == ""):
            raise ValueError("Missing required field: name")

    def _validate_stage_field_lengths(self, data: Dict[str, Any]) -> None:
        """
        Validate field lengths against model constraints.

        Raises:
            ValueError: If a field exceeds its maximum length.
        """
        name = data.get("name")
        if name is not None and isinstance(name, str) and len(name.strip()) > 64:
            raise ValueError(
                "Field 'name' exceeds maximum length of 64 characters."
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
        Create an audit log entry. Failures are silently ignored.
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


class DealService:
    """
    Business logic service for Deal CRUD operations and deal assignment.
    Wraps repository operations with validation and audit logging.
    """

    def get_deal(self, deal_id: uuid.UUID) -> Optional[Deal]:
        """
        Retrieve a single deal by ID with related objects.

        Args:
            deal_id: The UUID of the deal to retrieve.

        Returns:
            The Deal instance or None if not found.
        """
        try:
            return Deal.objects.select_related(
                "customer", "owner", "stage"
            ).get(pk=deal_id)
        except Deal.DoesNotExist:
            return None

    def list_deals(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        List deals with optional filtering.

        Args:
            filters: Optional dictionary of filter parameters.
                Supported keys: customer, owner, stage, search,
                min_value, max_value.

        Returns:
            A QuerySet of Deal instances.
        """
        queryset = Deal.objects.select_related(
            "customer", "owner", "stage"
        ).all()

        if not filters:
            return queryset

        customer = filters.get("customer")
        if customer is not None and str(customer).strip() != "":
            queryset = queryset.filter(customer_id=customer)

        owner = filters.get("owner")
        if owner is not None and str(owner).strip() != "":
            queryset = queryset.filter(owner_id=owner)

        stage = filters.get("stage")
        if stage is not None and str(stage).strip() != "":
            queryset = queryset.filter(stage_id=stage)

        search = filters.get("search")
        if search is not None and isinstance(search, str) and search.strip() != "":
            search = search.strip()
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(customer__name__icontains=search)
                | Q(description__icontains=search)
            )

        min_value = filters.get("min_value")
        if min_value is not None:
            try:
                min_val = Decimal(str(min_value))
                queryset = queryset.filter(value__gte=min_val)
            except (InvalidOperation, ValueError, TypeError):
                pass

        max_value = filters.get("max_value")
        if max_value is not None:
            try:
                max_val = Decimal(str(max_value))
                queryset = queryset.filter(value__lte=max_val)
            except (InvalidOperation, ValueError, TypeError):
                pass

        return queryset

    def search_deals(self, query: str) -> QuerySet:
        """
        Search deals by name, customer name, or description.

        Args:
            query: The search string.

        Returns:
            A QuerySet of matching Deal instances.
        """
        if not query or not query.strip():
            return Deal.objects.select_related(
                "customer", "owner", "stage"
            ).all()

        query = query.strip()
        return Deal.objects.select_related(
            "customer", "owner", "stage"
        ).filter(
            Q(name__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(description__icontains=query)
        )

    def create_deal(
        self,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Deal:
        """
        Create a new deal with validation and audit logging.

        Args:
            data: Dictionary containing deal fields (name, value, customer,
                  stage, owner, expected_close_date, description).
            user: The user performing the action (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            The newly created Deal instance.

        Raises:
            ValueError: If required fields are missing or validation fails.
        """
        self._validate_required_fields(data, ["name", "value", "customer", "stage"])
        self._validate_field_lengths(data)
        self._validate_deal_value(data)

        customer = self._resolve_foreign_key(data, "customer", "customers.Customer")
        stage = self._resolve_foreign_key(data, "stage", "deals.SalesStage")
        owner = self._resolve_optional_foreign_key(data, "owner")

        with transaction.atomic():
            deal_data = {
                "name": data["name"].strip(),
                "value": Decimal(str(data["value"])),
                "customer": customer,
                "stage": stage,
                "description": data.get("description", "").strip() if data.get("description") else "",
            }

            if owner is not None:
                deal_data["owner"] = owner
            elif user is not None and hasattr(user, "pk"):
                deal_data["owner"] = user

            expected_close_date = data.get("expected_close_date")
            if expected_close_date:
                deal_data["expected_close_date"] = expected_close_date

            deal = Deal.objects.create(**deal_data)

            audit_changes = {
                "name": deal.name,
                "value": str(deal.value),
                "customer_id": str(deal.customer_id),
                "stage_id": str(deal.stage_id),
            }
            if deal.owner_id:
                audit_changes["owner_id"] = str(deal.owner_id)

            self._log_audit(
                entity_type="Deal",
                entity_id=deal.pk,
                action=AuditLog.Action.CREATE,
                user=user,
                changes={"created": audit_changes},
                ip_address=ip_address,
            )

        return deal

    def update_deal(
        self,
        deal_id: uuid.UUID,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[Deal]:
        """
        Update an existing deal with validation and audit logging.

        Args:
            deal_id: The UUID of the deal to update.
            data: Dictionary containing fields to update.
            user: The user performing the action (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            The updated Deal instance, or None if not found.

        Raises:
            ValueError: If validation fails.
        """
        deal = self.get_deal(deal_id)
        if deal is None:
            return None

        self._validate_field_lengths(data)

        if "value" in data:
            self._validate_deal_value(data)

        changes = {}

        with transaction.atomic():
            if "name" in data:
                new_name = data["name"].strip() if isinstance(data["name"], str) else data["name"]
                if deal.name != new_name:
                    changes["name"] = {"old": deal.name, "new": new_name}
                    deal.name = new_name

            if "value" in data:
                new_value = Decimal(str(data["value"]))
                if deal.value != new_value:
                    changes["value"] = {"old": str(deal.value), "new": str(new_value)}
                    deal.value = new_value

            if "description" in data:
                new_desc = data["description"].strip() if isinstance(data["description"], str) else data["description"] or ""
                if deal.description != new_desc:
                    changes["description"] = {"old": deal.description, "new": new_desc}
                    deal.description = new_desc

            if "expected_close_date" in data:
                new_date = data["expected_close_date"]
                if deal.expected_close_date != new_date:
                    changes["expected_close_date"] = {
                        "old": str(deal.expected_close_date) if deal.expected_close_date else None,
                        "new": str(new_date) if new_date else None,
                    }
                    deal.expected_close_date = new_date

            if "stage" in data:
                new_stage = self._resolve_foreign_key(data, "stage", "deals.SalesStage")
                if deal.stage_id != new_stage.pk:
                    changes["stage"] = {
                        "old": str(deal.stage_id),
                        "new": str(new_stage.pk),
                    }
                    deal.stage = new_stage

            if "customer" in data:
                new_customer = self._resolve_foreign_key(data, "customer", "customers.Customer")
                if deal.customer_id != new_customer.pk:
                    changes["customer"] = {
                        "old": str(deal.customer_id),
                        "new": str(new_customer.pk),
                    }
                    deal.customer = new_customer

            if "owner" in data:
                new_owner = self._resolve_optional_foreign_key(data, "owner")
                old_owner_id = deal.owner_id
                new_owner_id = new_owner.pk if new_owner else None
                if old_owner_id != new_owner_id:
                    changes["owner"] = {
                        "old": str(old_owner_id) if old_owner_id else None,
                        "new": str(new_owner_id) if new_owner_id else None,
                    }
                    deal.owner = new_owner

            if not changes:
                return deal

            deal.save()

            self._log_audit(
                entity_type="Deal",
                entity_id=deal.pk,
                action=AuditLog.Action.UPDATE,
                user=user,
                changes=changes,
                ip_address=ip_address,
            )

        return deal

    def delete_deal(
        self,
        deal_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Delete a deal by ID with audit logging.

        Args:
            deal_id: The UUID of the deal to delete.
            user: The user performing the action (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            True if the deal was deleted, False if not found.
        """
        deal = self.get_deal(deal_id)
        if deal is None:
            return False

        deal_name = str(deal)
        deal_pk = deal.pk

        with transaction.atomic():
            deal.delete()

            self._log_audit(
                entity_type="Deal",
                entity_id=deal_pk,
                action=AuditLog.Action.DELETE,
                user=user,
                changes={"deleted": deal_name},
                ip_address=ip_address,
            )

        return True

    def assign_deal_owner(
        self,
        deal_id: uuid.UUID,
        owner_id,
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[Deal]:
        """
        Assign or reassign the owner of a deal.

        Args:
            deal_id: The UUID of the deal.
            owner_id: The PK of the user to assign as owner.
            user: The user performing the action (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            The updated Deal instance, or None if the deal is not found.

        Raises:
            ValueError: If the owner user is not found.
        """
        deal = self.get_deal(deal_id)
        if deal is None:
            return None

        from django.conf import settings
        from django.apps import apps

        UserModel = apps.get_model(settings.AUTH_USER_MODEL)

        try:
            new_owner = UserModel.objects.get(pk=owner_id)
        except UserModel.DoesNotExist:
            raise ValueError(f"User with ID '{owner_id}' not found.")

        old_owner_id = deal.owner_id

        if old_owner_id == new_owner.pk:
            return deal

        with transaction.atomic():
            deal.owner = new_owner
            deal.save(update_fields=["owner", "updated_at"])

            changes = {
                "owner": {
                    "old": str(old_owner_id) if old_owner_id else None,
                    "new": str(new_owner.pk),
                },
            }

            self._log_audit(
                entity_type="Deal",
                entity_id=deal.pk,
                action=AuditLog.Action.UPDATE,
                user=user,
                changes=changes,
                ip_address=ip_address,
            )

        deal.refresh_from_db()
        return deal

    def get_deals_by_customer(self, customer_id: uuid.UUID) -> QuerySet:
        """
        Get all deals for a specific customer.

        Args:
            customer_id: The UUID of the customer.

        Returns:
            A QuerySet of Deal instances.
        """
        return Deal.objects.select_related(
            "owner", "stage"
        ).filter(customer_id=customer_id)

    def get_deals_by_owner(self, owner_id) -> QuerySet:
        """
        Get all deals assigned to a specific owner.

        Args:
            owner_id: The PK of the owner user.

        Returns:
            A QuerySet of Deal instances.
        """
        return Deal.objects.select_related(
            "customer", "stage"
        ).filter(owner_id=owner_id)

    def get_deals_by_stage(self, stage_id: uuid.UUID) -> QuerySet:
        """
        Get all deals in a specific sales stage.

        Args:
            stage_id: The UUID of the sales stage.

        Returns:
            A QuerySet of Deal instances.
        """
        return Deal.objects.select_related(
            "customer", "owner"
        ).filter(stage_id=stage_id)

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
            if value is None:
                raise ValueError(f"Missing required field: {field}")
            if isinstance(value, str) and value.strip() == "":
                raise ValueError(f"Missing required field: {field}")

    def _validate_field_lengths(self, data: Dict[str, Any]) -> None:
        """
        Validate field lengths against model constraints.

        Raises:
            ValueError: If a field exceeds its maximum length.
        """
        length_constraints = {
            "name": 128,
        }

        for field, max_length in length_constraints.items():
            value = data.get(field)
            if value is not None and isinstance(value, str) and len(value.strip()) > max_length:
                raise ValueError(
                    f"Field '{field}' exceeds maximum length of {max_length} characters."
                )

    def _validate_deal_value(self, data: Dict[str, Any]) -> None:
        """
        Validate that the deal value is a positive number.

        Raises:
            ValueError: If the value is not a valid positive number.
        """
        value = data.get("value")
        if value is None:
            return

        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Deal value must be a valid number.")

        if decimal_value <= 0:
            raise ValueError("Deal value must be a positive number.")

        if decimal_value >= Decimal("10000000000"):
            raise ValueError(
                "Deal value exceeds maximum allowed value."
            )

    def _resolve_foreign_key(
        self, data: Dict[str, Any], field_name: str, model_path: str
    ) -> Any:
        """
        Resolve a foreign key value to a model instance.

        Args:
            data: The data dictionary.
            field_name: The field name in the data dict.
            model_path: The app_label.ModelName string.

        Returns:
            The resolved model instance.

        Raises:
            ValueError: If the referenced object does not exist.
        """
        from django.apps import apps

        value = data.get(field_name)
        if value is None:
            raise ValueError(f"Missing required field: {field_name}")

        if hasattr(value, "pk"):
            return value

        app_label, model_name = model_path.split(".")
        Model = apps.get_model(app_label, model_name)

        try:
            return Model.objects.get(pk=value)
        except Model.DoesNotExist:
            raise ValueError(
                f"{model_name} with ID '{value}' not found."
            )

    def _resolve_optional_foreign_key(
        self, data: Dict[str, Any], field_name: str
    ) -> Any:
        """
        Resolve an optional foreign key value to a user model instance.

        Args:
            data: The data dictionary.
            field_name: The field name in the data dict.

        Returns:
            The resolved user instance, or None.
        """
        value = data.get(field_name)
        if value is None or value == "":
            return None

        if hasattr(value, "pk"):
            return value

        from django.conf import settings
        from django.apps import apps

        UserModel = apps.get_model(settings.AUTH_USER_MODEL)

        try:
            return UserModel.objects.get(pk=value)
        except UserModel.DoesNotExist:
            raise ValueError(
                f"User with ID '{value}' not found."
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