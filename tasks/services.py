import logging
import uuid
from datetime import date as date_type
from typing import Any, Dict, List, Optional

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from audit_logs.models import AuditLog
from tasks.models import Task

logger = logging.getLogger(__name__)


class TaskManagerService:
    """
    Business logic service for Task CRUD operations.
    Wraps repository operations with validation, audit logging,
    and automation event triggers on task completion.
    """

    def create_task(
        self,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Task:
        """
        Create a new task with validation and audit logging.

        Args:
            data: Dictionary containing task fields:
                - title: Task title (required)
                - description: Task description (optional)
                - customer_id: UUID of the related customer (optional)
                - deal_id: UUID of the related deal (optional)
                - assigned_to_id: UUID of the assignee user (optional)
                - status: Task status (optional, defaults to 'pending')
                - priority: Task priority (optional, defaults to 'medium')
                - due_date: Due date (optional)
                - reminder_date: Reminder datetime (optional)
            user: The user performing the action (for audit logging and created_by).
            ip_address: Optional IP address for audit logging.

        Returns:
            The newly created Task instance.

        Raises:
            ValueError: If required fields are missing or validation fails.
        """
        self._validate_required_fields(data, ["title"])
        self._validate_field_lengths(data)

        if "status" in data and data["status"]:
            self._validate_status(data["status"])

        if "priority" in data and data["priority"]:
            self._validate_priority(data["priority"])

        with transaction.atomic():
            task_data = {
                "title": data["title"].strip() if isinstance(data["title"], str) else data["title"],
                "description": data.get("description", "").strip() if data.get("description") else "",
                "status": data.get("status", Task.Status.PENDING),
                "priority": data.get("priority", Task.Priority.MEDIUM),
            }

            if user is not None and hasattr(user, "pk"):
                task_data["created_by"] = user

            # Resolve customer
            customer = self._resolve_optional_fk(data, "customer_id", "customers.Customer")
            if customer is not None:
                task_data["customer"] = customer

            # Resolve deal
            deal = self._resolve_optional_fk(data, "deal_id", "deals.Deal")
            if deal is not None:
                task_data["deal"] = deal

            # Resolve assignee
            assigned_to = self._resolve_optional_user(data, "assigned_to_id")
            if assigned_to is not None:
                task_data["assigned_to"] = assigned_to
            elif "assigned_to" in data:
                if hasattr(data["assigned_to"], "pk"):
                    task_data["assigned_to"] = data["assigned_to"]
                elif data["assigned_to"] is not None and data["assigned_to"] != "":
                    assigned_to = self._resolve_optional_user(
                        {"assigned_to_id": data["assigned_to"]}, "assigned_to_id"
                    )
                    if assigned_to is not None:
                        task_data["assigned_to"] = assigned_to

            # Due date
            due_date = data.get("due_date")
            if due_date is not None:
                task_data["due_date"] = due_date

            # Reminder date
            reminder_date = data.get("reminder_date")
            if reminder_date is not None:
                task_data["reminder_date"] = reminder_date

            task = Task.objects.create(**task_data)

            audit_changes = {
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
            }
            if task.customer_id:
                audit_changes["customer_id"] = str(task.customer_id)
            if task.deal_id:
                audit_changes["deal_id"] = str(task.deal_id)
            if task.assigned_to_id:
                audit_changes["assigned_to_id"] = str(task.assigned_to_id)
            if task.due_date:
                audit_changes["due_date"] = str(task.due_date)

            self._log_audit(
                entity_type="Task",
                entity_id=task.pk,
                action=AuditLog.Action.CREATE,
                user=user,
                changes={"created": audit_changes},
                ip_address=ip_address,
            )

        logger.info(
            "Task created: id=%s title=%s assignee=%s user=%s",
            task.pk,
            task.title,
            task.assigned_to_id,
            user,
        )

        return task

    def get_task(self, task_id: uuid.UUID) -> Optional[Task]:
        """
        Retrieve a single task by ID with related objects.

        Args:
            task_id: The UUID of the task.

        Returns:
            The Task instance or None if not found.
        """
        try:
            return Task.objects.select_related(
                "customer", "deal", "assigned_to", "created_by"
            ).get(pk=task_id)
        except Task.DoesNotExist:
            return None

    def list_tasks(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        List tasks with optional filtering.

        Args:
            filters: Optional dictionary of filter parameters:
                - status: Filter by status
                - priority: Filter by priority
                - assigned_to: Filter by assignee user ID
                - customer_id: Filter by customer ID
                - deal_id: Filter by deal ID
                - search: Search by title or description
                - due_date_from: Filter tasks due from this date
                - due_date_to: Filter tasks due up to this date
                - is_overdue: If True, only return overdue tasks

        Returns:
            A QuerySet of Task instances.
        """
        queryset = Task.objects.select_related(
            "customer", "deal", "assigned_to", "created_by"
        ).all()

        if not filters:
            return queryset

        status = filters.get("status", "").strip() if filters.get("status") else ""
        if status and status in Task.Status.values:
            queryset = queryset.filter(status=status)

        priority = filters.get("priority", "").strip() if filters.get("priority") else ""
        if priority and priority in Task.Priority.values:
            queryset = queryset.filter(priority=priority)

        assigned_to = filters.get("assigned_to")
        if assigned_to is not None and str(assigned_to).strip() != "":
            queryset = queryset.filter(assigned_to_id=assigned_to)

        customer_id = filters.get("customer_id")
        if customer_id is not None and str(customer_id).strip() != "":
            queryset = queryset.filter(customer_id=customer_id)

        deal_id = filters.get("deal_id")
        if deal_id is not None and str(deal_id).strip() != "":
            queryset = queryset.filter(deal_id=deal_id)

        search = filters.get("search")
        if search is not None and isinstance(search, str) and search.strip() != "":
            search = search.strip()
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
            )

        due_date_from = filters.get("due_date_from")
        if due_date_from:
            queryset = queryset.filter(due_date__gte=due_date_from)

        due_date_to = filters.get("due_date_to")
        if due_date_to:
            queryset = queryset.filter(due_date__lte=due_date_to)

        if filters.get("is_overdue"):
            today = timezone.now().date()
            queryset = queryset.filter(
                due_date__lt=today,
            ).exclude(
                status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED],
            )

        return queryset

    def get_tasks_by_assignee(self, user_id) -> QuerySet:
        """
        Get all tasks assigned to a specific user.

        Args:
            user_id: The PK of the assignee user.

        Returns:
            A QuerySet of Task instances.
        """
        return Task.objects.select_related(
            "customer", "deal", "created_by"
        ).filter(assigned_to_id=user_id)

    def get_tasks_by_customer(self, customer_id: uuid.UUID) -> QuerySet:
        """
        Get all tasks related to a specific customer.

        Args:
            customer_id: The UUID of the customer.

        Returns:
            A QuerySet of Task instances.
        """
        return Task.objects.select_related(
            "deal", "assigned_to", "created_by"
        ).filter(customer_id=customer_id)

    def get_tasks_by_deal(self, deal_id: uuid.UUID) -> QuerySet:
        """
        Get all tasks related to a specific deal.

        Args:
            deal_id: The UUID of the deal.

        Returns:
            A QuerySet of Task instances.
        """
        return Task.objects.select_related(
            "customer", "assigned_to", "created_by"
        ).filter(deal_id=deal_id)

    def get_overdue_tasks(self, user_id=None) -> QuerySet:
        """
        Get overdue tasks, optionally filtered by assignee.

        Args:
            user_id: Optional user PK to filter by assignee.

        Returns:
            A QuerySet of overdue Task instances.
        """
        today = timezone.now().date()
        queryset = Task.objects.select_related(
            "customer", "deal", "assigned_to", "created_by"
        ).filter(
            due_date__lt=today,
        ).exclude(
            status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED],
        ).order_by("due_date")

        if user_id is not None:
            queryset = queryset.filter(assigned_to_id=user_id)

        return queryset

    def get_upcoming_tasks(self, user_id=None, limit: int = 10) -> QuerySet:
        """
        Get upcoming tasks (pending or in progress with due dates),
        optionally filtered by assignee.

        Args:
            user_id: Optional user PK to filter by assignee.
            limit: Maximum number of tasks to return.

        Returns:
            A QuerySet of upcoming Task instances.
        """
        queryset = Task.objects.select_related(
            "customer", "deal", "assigned_to", "created_by"
        ).filter(
            status__in=[Task.Status.PENDING, Task.Status.IN_PROGRESS],
        ).exclude(
            due_date__isnull=True,
        ).order_by("due_date")

        if user_id is not None:
            queryset = queryset.filter(assigned_to_id=user_id)

        return queryset[:limit]

    def update_task(
        self,
        task_id: uuid.UUID,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[Task]:
        """
        Update an existing task with validation and audit logging.

        Args:
            task_id: The UUID of the task to update.
            data: Dictionary containing fields to update.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            The updated Task instance, or None if not found.

        Raises:
            ValueError: If validation fails.
        """
        task = self.get_task(task_id)
        if task is None:
            return None

        self._validate_field_lengths(data)

        if "status" in data and data["status"]:
            self._validate_status(data["status"])

        if "priority" in data and data["priority"]:
            self._validate_priority(data["priority"])

        changes = {}

        with transaction.atomic():
            # Simple string/value fields
            simple_fields = ["title", "description", "status", "priority", "due_date", "reminder_date"]
            for field in simple_fields:
                if field in data:
                    new_value = data[field]
                    if isinstance(new_value, str) and field in ("title", "description"):
                        new_value = new_value.strip()
                    old_value = getattr(task, field, None)
                    if old_value != new_value:
                        changes[field] = {
                            "old": str(old_value) if old_value is not None else None,
                            "new": str(new_value) if new_value is not None else None,
                        }
                        setattr(task, field, new_value)

            # Handle customer
            if "customer_id" in data:
                new_customer = self._resolve_optional_fk(data, "customer_id", "customers.Customer")
                old_customer_id = task.customer_id
                new_customer_id = new_customer.pk if new_customer else None
                if old_customer_id != new_customer_id:
                    changes["customer"] = {
                        "old": str(old_customer_id) if old_customer_id else None,
                        "new": str(new_customer_id) if new_customer_id else None,
                    }
                    task.customer = new_customer
            elif "customer" in data:
                if hasattr(data["customer"], "pk"):
                    if task.customer_id != data["customer"].pk:
                        changes["customer"] = {
                            "old": str(task.customer_id) if task.customer_id else None,
                            "new": str(data["customer"].pk),
                        }
                        task.customer = data["customer"]

            # Handle deal
            if "deal_id" in data:
                new_deal = self._resolve_optional_fk(data, "deal_id", "deals.Deal")
                old_deal_id = task.deal_id
                new_deal_id = new_deal.pk if new_deal else None
                if old_deal_id != new_deal_id:
                    changes["deal"] = {
                        "old": str(old_deal_id) if old_deal_id else None,
                        "new": str(new_deal_id) if new_deal_id else None,
                    }
                    task.deal = new_deal
            elif "deal" in data:
                if hasattr(data["deal"], "pk"):
                    if task.deal_id != data["deal"].pk:
                        changes["deal"] = {
                            "old": str(task.deal_id) if task.deal_id else None,
                            "new": str(data["deal"].pk),
                        }
                        task.deal = data["deal"]

            # Handle assigned_to
            if "assigned_to_id" in data:
                new_assignee = self._resolve_optional_user(data, "assigned_to_id")
                old_assignee_id = task.assigned_to_id
                new_assignee_id = new_assignee.pk if new_assignee else None
                if old_assignee_id != new_assignee_id:
                    changes["assigned_to"] = {
                        "old": str(old_assignee_id) if old_assignee_id else None,
                        "new": str(new_assignee_id) if new_assignee_id else None,
                    }
                    task.assigned_to = new_assignee
            elif "assigned_to" in data:
                if hasattr(data["assigned_to"], "pk"):
                    if task.assigned_to_id != data["assigned_to"].pk:
                        changes["assigned_to"] = {
                            "old": str(task.assigned_to_id) if task.assigned_to_id else None,
                            "new": str(data["assigned_to"].pk),
                        }
                        task.assigned_to = data["assigned_to"]

            # Check if status changed to completed
            was_completed = False
            if "status" in changes and changes["status"]["new"] == Task.Status.COMPLETED:
                task.completed_at = timezone.now()
                was_completed = True

            if not changes:
                return task

            task.save()

            self._log_audit(
                entity_type="Task",
                entity_id=task.pk,
                action=AuditLog.Action.UPDATE,
                user=user,
                changes=changes,
                ip_address=ip_address,
            )

        logger.info(
            "Task updated: id=%s fields=%s user=%s",
            task.pk,
            list(changes.keys()),
            user,
        )

        # Trigger automation events on task completion
        if was_completed:
            self._trigger_task_completion_automation(task, user)

        return task

    def complete_task(
        self,
        task_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[Task]:
        """
        Mark a task as completed with audit logging and automation triggers.

        Args:
            task_id: The UUID of the task to complete.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            The completed Task instance, or None if not found.
        """
        task = self.get_task(task_id)
        if task is None:
            return None

        if task.status == Task.Status.COMPLETED:
            return task

        old_status = task.status

        with transaction.atomic():
            task.status = Task.Status.COMPLETED
            task.completed_at = timezone.now()
            task.save(update_fields=["status", "completed_at", "updated_at"])

            changes = {
                "status": {
                    "old": old_status,
                    "new": Task.Status.COMPLETED,
                },
                "completed_at": {
                    "old": None,
                    "new": str(task.completed_at),
                },
            }

            self._log_audit(
                entity_type="Task",
                entity_id=task.pk,
                action=AuditLog.Action.UPDATE,
                user=user,
                changes=changes,
                ip_address=ip_address,
            )

        logger.info(
            "Task completed: id=%s title=%s user=%s",
            task.pk,
            task.title,
            user,
        )

        # Trigger automation events on task completion
        self._trigger_task_completion_automation(task, user)

        return task

    def delete_task(
        self,
        task_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Delete a task by ID with audit logging.

        Args:
            task_id: The UUID of the task to delete.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            True if deleted, False if not found.
        """
        task = self.get_task(task_id)
        if task is None:
            return False

        task_repr = str(task)
        task_pk = task.pk

        with transaction.atomic():
            task.delete()

            self._log_audit(
                entity_type="Task",
                entity_id=task_pk,
                action=AuditLog.Action.DELETE,
                user=user,
                changes={"deleted": task_repr},
                ip_address=ip_address,
            )

        logger.info(
            "Task deleted: id=%s user=%s",
            task_pk,
            user,
        )

        return True

    def search_tasks(self, query: str) -> QuerySet:
        """
        Search tasks by title or description.

        Args:
            query: The search string.

        Returns:
            A QuerySet of matching Task instances.
        """
        if not query or not query.strip():
            return Task.objects.select_related(
                "customer", "deal", "assigned_to", "created_by"
            ).all()

        query = query.strip()
        return Task.objects.select_related(
            "customer", "deal", "assigned_to", "created_by"
        ).filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
        )

    def _trigger_task_completion_automation(self, task: Task, user=None) -> None:
        """
        Trigger automation rules when a task is completed.
        Evaluates active automation rules with relevant trigger types.
        """
        try:
            from automation.models import AutomationLog, AutomationRule

            # Find rules triggered by call_completed or meeting_completed
            # that might apply to task completion scenarios
            relevant_triggers = ["call_completed", "meeting_completed", "demo_completed"]
            rules = AutomationRule.objects.filter(
                is_active=True,
                trigger_type__in=relevant_triggers,
            )

            for rule in rules:
                try:
                    config = rule.config or {}

                    # Check if the rule's config matches the task context
                    should_trigger = self._evaluate_rule_criteria(rule, task, config)

                    if should_trigger:
                        self._execute_automation_action(rule, task, user)

                        AutomationLog.objects.create(
                            rule=rule,
                            triggered_by=user if user is not None and hasattr(user, "pk") else None,
                            target_entity_type="Task",
                            target_entity_id=str(task.pk),
                            status="success",
                            result_message=f"Automation rule '{rule.name}' triggered on task completion: {task.title}",
                        )

                        logger.info(
                            "Automation rule triggered: rule=%s task=%s user=%s",
                            rule.name,
                            task.pk,
                            user,
                        )

                except Exception as e:
                    logger.warning(
                        "Failed to execute automation rule %s for task %s: %s",
                        rule.pk,
                        task.pk,
                        str(e),
                        exc_info=True,
                    )

                    try:
                        AutomationLog.objects.create(
                            rule=rule,
                            triggered_by=user if user is not None and hasattr(user, "pk") else None,
                            target_entity_type="Task",
                            target_entity_id=str(task.pk),
                            status="failed",
                            result_message=f"Failed to execute rule '{rule.name}': {str(e)}",
                        )
                    except Exception:
                        pass

        except ImportError:
            logger.warning(
                "Automation module not available, skipping task completion triggers."
            )
        except Exception:
            logger.warning(
                "Failed to trigger automation for task %s",
                task.pk,
                exc_info=True,
            )

    def _evaluate_rule_criteria(self, rule, task: Task, config: Dict[str, Any]) -> bool:
        """
        Evaluate whether an automation rule's criteria match the given task.
        Returns True if the rule should be triggered.
        """
        # If no specific criteria, trigger for all matching events
        if not config:
            return True

        # Check task priority criteria
        required_priority = config.get("task_priority")
        if required_priority and task.priority != required_priority:
            return False

        return True

    def _execute_automation_action(self, rule, task: Task, user=None) -> None:
        """
        Execute the action defined by an automation rule.
        """
        action_type = rule.action_type
        config = rule.config or {}

        if action_type == "create_task":
            self._execute_create_task_action(config, task, user)
        elif action_type == "send_email":
            self._execute_send_email_action(config, task, user)
        elif action_type == "assign_lead":
            logger.info(
                "Lead assignment action triggered by rule %s for task %s",
                rule.name,
                task.pk,
            )
        else:
            logger.warning(
                "Unknown automation action type: %s for rule %s",
                action_type,
                rule.name,
            )

    def _execute_create_task_action(
        self, config: Dict[str, Any], source_task: Task, user=None
    ) -> None:
        """
        Create a follow-up task based on automation rule configuration.
        """
        try:
            title = config.get("task_title", f"Follow up: {source_task.title}")
            priority = config.get("task_priority", Task.Priority.MEDIUM)
            delay_hours = config.get("delay_hours", 24)

            due_date = timezone.now().date()
            if delay_hours:
                from datetime import timedelta
                due_date = (timezone.now() + timedelta(hours=int(delay_hours))).date()

            follow_up_data = {
                "title": title,
                "description": f"Auto-generated follow-up for completed task: {source_task.title}",
                "priority": priority,
                "due_date": due_date,
                "status": Task.Status.PENDING,
            }

            if source_task.customer_id:
                follow_up_data["customer_id"] = source_task.customer_id

            if source_task.deal_id:
                follow_up_data["deal_id"] = source_task.deal_id

            if source_task.assigned_to_id:
                follow_up_data["assigned_to_id"] = source_task.assigned_to_id

            self.create_task(follow_up_data, user=user)

            logger.info(
                "Follow-up task created for completed task %s",
                source_task.pk,
            )

        except Exception as e:
            logger.warning(
                "Failed to create follow-up task for task %s: %s",
                source_task.pk,
                str(e),
                exc_info=True,
            )

    def _execute_send_email_action(
        self, config: Dict[str, Any], task: Task, user=None
    ) -> None:
        """
        Send an email notification based on automation rule configuration.
        """
        try:
            from integrations.services import get_adapter, IntegrationError

            if user is None:
                logger.warning(
                    "Cannot send email notification: no user context for task %s",
                    task.pk,
                )
                return

            subject = config.get("subject", f"Task Completed: {task.title}")
            template = config.get("email_template", "")
            body = f"Task '{task.title}' has been completed."

            if template:
                body = f"[Template: {template}] {body}"

            try:
                adapter = get_adapter("gmail", user=user)
                adapter.send_email(
                    to=user.email,
                    subject=subject,
                    body=body,
                )
                logger.info(
                    "Email notification sent for task completion: task=%s user=%s",
                    task.pk,
                    user,
                )
            except IntegrationError as e:
                logger.warning(
                    "Failed to send email notification for task %s: %s",
                    task.pk,
                    str(e),
                )
            except Exception as e:
                logger.warning(
                    "Failed to send email notification for task %s: %s",
                    task.pk,
                    str(e),
                )

        except ImportError:
            logger.warning(
                "Integration module not available for email notification."
            )

    def _validate_required_fields(
        self, data: Dict[str, Any], required_fields: List[str]
    ) -> None:
        """Validate that all required fields are present and non-empty."""
        for field in required_fields:
            value = data.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                raise ValueError(f"Missing required field: {field}")

    def _validate_field_lengths(self, data: Dict[str, Any]) -> None:
        """Validate field lengths against model constraints."""
        length_constraints = {
            "title": 255,
        }

        for field, max_length in length_constraints.items():
            value = data.get(field)
            if value is not None and isinstance(value, str) and len(value.strip()) > max_length:
                raise ValueError(
                    f"Field '{field}' exceeds maximum length of {max_length} characters."
                )

    def _validate_status(self, status: str) -> None:
        """Validate that the status is valid."""
        valid_statuses = Task.Status.values
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{status}'. "
                f"Must be one of: {', '.join(valid_statuses)}"
            )

    def _validate_priority(self, priority: str) -> None:
        """Validate that the priority is valid."""
        valid_priorities = Task.Priority.values
        if priority not in valid_priorities:
            raise ValueError(
                f"Invalid priority '{priority}'. "
                f"Must be one of: {', '.join(valid_priorities)}"
            )

    def _resolve_optional_fk(
        self, data: Dict[str, Any], field_name: str, model_path: str
    ) -> Any:
        """
        Resolve an optional foreign key value to a model instance.

        Args:
            data: The data dictionary.
            field_name: The field name in the data dict.
            model_path: The app_label.ModelName string.

        Returns:
            The resolved model instance, or None.
        """
        value = data.get(field_name)
        if value is None or value == "":
            return None

        if hasattr(value, "pk"):
            return value

        from django.apps import apps

        app_label, model_name = model_path.split(".")
        Model = apps.get_model(app_label, model_name)

        try:
            return Model.objects.get(pk=value)
        except Model.DoesNotExist:
            raise ValueError(
                f"{model_name} with ID '{value}' not found."
            )

    def _resolve_optional_user(
        self, data: Dict[str, Any], field_name: str
    ) -> Any:
        """
        Resolve an optional user foreign key value to a user model instance.

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
        """Create an audit log entry. Failures are silently ignored."""
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
            logger.warning(
                "Failed to create audit log entry for %s %s",
                entity_type,
                entity_id,
                exc_info=True,
            )