import logging
import uuid
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from automation.models import AutomationLog, AutomationRule

logger = logging.getLogger(__name__)


class AutomationEngine:
    """
    Automation rule engine that evaluates active rules against events
    and executes configured actions (send email, assign lead, create task).
    All executions are logged to AutomationLog.
    """

    def publish_event(
        self,
        event_type: str,
        context: Dict[str, Any],
        triggered_by=None,
    ) -> List[AutomationLog]:
        """
        Publish an event and evaluate all matching active automation rules.

        Args:
            event_type: The type of event that occurred (e.g., 'meeting_completed',
                        'call_completed', 'demo_completed', 'new_lead').
            context: Dictionary containing event context data such as:
                - customer_id: UUID of the related customer
                - deal_id: UUID of the related deal (optional)
                - user_id: UUID of the user involved (optional)
                - Additional data depending on event type
            triggered_by: The user who triggered the event (optional).

        Returns:
            A list of AutomationLog entries created during execution.
        """
        if not event_type:
            logger.warning("publish_event called with empty event_type")
            return []

        logger.info(
            "Event published: type=%s triggered_by=%s context_keys=%s",
            event_type,
            triggered_by,
            list(context.keys()) if context else [],
        )

        matching_rules = self.evaluate_rules(event_type)

        if not matching_rules:
            logger.info(
                "No active automation rules matched event_type=%s",
                event_type,
            )
            return []

        logs = []
        for rule in matching_rules:
            log_entry = self.execute_action(rule, context, triggered_by=triggered_by)
            if log_entry is not None:
                logs.append(log_entry)

        logger.info(
            "Event processing complete: type=%s rules_matched=%d actions_executed=%d",
            event_type,
            len(matching_rules),
            len(logs),
        )

        return logs

    def evaluate_rules(self, event_type: str) -> List[AutomationRule]:
        """
        Evaluate which active automation rules match the given event type.

        Args:
            event_type: The trigger event type to match against.

        Returns:
            A list of active AutomationRule instances matching the event type.
        """
        if not event_type:
            return []

        matching_rules = list(
            AutomationRule.objects.filter(
                trigger_type=event_type,
                is_active=True,
            ).select_related("created_by").order_by("created_at")
        )

        logger.debug(
            "Evaluated rules for event_type=%s: %d matching",
            event_type,
            len(matching_rules),
        )

        return matching_rules

    def execute_action(
        self,
        rule: AutomationRule,
        context: Dict[str, Any],
        triggered_by=None,
    ) -> Optional[AutomationLog]:
        """
        Execute the action defined by an automation rule.

        Args:
            rule: The AutomationRule to execute.
            context: Dictionary containing event context data.
            triggered_by: The user who triggered the event (optional).

        Returns:
            The AutomationLog entry recording the execution, or None on failure.
        """
        if rule is None:
            logger.warning("execute_action called with None rule")
            return None

        action_type = rule.action_type
        config = rule.config if isinstance(rule.config, dict) else {}

        target_entity_type = self._resolve_target_entity_type(context)
        target_entity_id = self._resolve_target_entity_id(context)

        logger.info(
            "Executing action: rule=%s action_type=%s target=%s/%s",
            rule.name,
            action_type,
            target_entity_type,
            target_entity_id,
        )

        action_handlers = {
            "send_email": self._action_send_email,
            "assign_lead": self._action_assign_lead,
            "create_task": self._action_create_task,
        }

        handler = action_handlers.get(action_type)
        if handler is None:
            logger.error(
                "Unknown action_type '%s' for rule '%s' (id=%s)",
                action_type,
                rule.name,
                rule.pk,
            )
            return self._create_log_entry(
                rule=rule,
                triggered_by=triggered_by,
                target_entity_type=target_entity_type,
                target_entity_id=target_entity_id,
                status="failed",
                result_message=f"Unknown action type: {action_type}",
            )

        try:
            result_message = handler(rule, config, context, triggered_by)

            log_entry = self._create_log_entry(
                rule=rule,
                triggered_by=triggered_by,
                target_entity_type=target_entity_type,
                target_entity_id=target_entity_id,
                status="success",
                result_message=result_message or "Action executed successfully.",
            )

            logger.info(
                "Action executed successfully: rule=%s action_type=%s log_id=%s",
                rule.name,
                action_type,
                log_entry.pk,
            )

            return log_entry

        except Exception as e:
            logger.error(
                "Action execution failed: rule=%s action_type=%s error=%s",
                rule.name,
                action_type,
                str(e),
                exc_info=True,
            )

            log_entry = self._create_log_entry(
                rule=rule,
                triggered_by=triggered_by,
                target_entity_type=target_entity_type,
                target_entity_id=target_entity_id,
                status="failed",
                result_message=f"Action failed: {str(e)}",
            )

            return log_entry

    def _action_send_email(
        self,
        rule: AutomationRule,
        config: Dict[str, Any],
        context: Dict[str, Any],
        triggered_by=None,
    ) -> str:
        """
        Execute a send_email action.

        Attempts to send an email via the Gmail integration adapter.
        Falls back to Django's email backend if the integration is not available.

        Config keys:
            - email_template: Template name (optional)
            - subject: Email subject line (optional, has default)
            - delay_minutes: Delay before sending (optional, not yet implemented)

        Context keys:
            - customer_id: UUID of the customer to email
        """
        customer = self._resolve_customer(context)
        if customer is None:
            return "No customer found in context; email not sent."

        if not customer.email:
            return f"Customer '{customer.name}' has no email address; email not sent."

        subject = config.get("subject", f"Follow-up: {rule.name}")
        email_template = config.get("email_template", "")
        body = self._build_email_body(rule, config, context, customer, email_template)

        try:
            from integrations.services import GmailAdapter

            if triggered_by is not None:
                adapter = GmailAdapter(user=triggered_by)
                result = adapter.send_email(
                    to=customer.email,
                    subject=subject,
                    body=body,
                )
                email_id = result.get("email_id", "unknown")
                return f"Email sent via Gmail to {customer.email} (id={email_id})."
        except Exception as gmail_error:
            logger.warning(
                "Gmail adapter unavailable or failed for rule '%s': %s. "
                "Falling back to Django email.",
                rule.name,
                str(gmail_error),
            )

        try:
            from django.core.mail import send_mail
            from django.conf import settings

            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[customer.email],
                fail_silently=False,
            )
            return f"Email sent via Django mail to {customer.email}."
        except Exception as mail_error:
            logger.error(
                "Django email send failed for rule '%s': %s",
                rule.name,
                str(mail_error),
            )
            raise RuntimeError(
                f"Failed to send email to {customer.email}: {str(mail_error)}"
            ) from mail_error

    def _action_assign_lead(
        self,
        rule: AutomationRule,
        config: Dict[str, Any],
        context: Dict[str, Any],
        triggered_by=None,
    ) -> str:
        """
        Execute an assign_lead action.

        Assigns a deal or customer to a sales team member based on the
        configured assignment strategy.

        Config keys:
            - assignment_strategy: 'round_robin' or 'specific' (default: 'round_robin')
            - team: Role name to filter assignees (default: 'sales')
            - assignee_id: Specific user ID for 'specific' strategy

        Context keys:
            - deal_id: UUID of the deal to assign (optional)
            - customer_id: UUID of the customer (optional)
        """
        from django.conf import settings
        from django.apps import apps

        UserModel = apps.get_model(settings.AUTH_USER_MODEL)

        strategy = config.get("assignment_strategy", "round_robin")
        team_role = config.get("team", "sales")

        assignee = None

        if strategy == "specific":
            assignee_id = config.get("assignee_id")
            if assignee_id:
                try:
                    assignee = UserModel.objects.get(pk=assignee_id, is_active=True)
                except UserModel.DoesNotExist:
                    return f"Specified assignee (id={assignee_id}) not found or inactive."
            else:
                return "No assignee_id provided for 'specific' assignment strategy."
        else:
            assignee = self._get_round_robin_assignee(UserModel, team_role)
            if assignee is None:
                return f"No active users with role '{team_role}' available for assignment."

        deal_id = context.get("deal_id")
        if deal_id:
            try:
                from deals.models import Deal

                deal = Deal.objects.get(pk=deal_id)
                old_owner = deal.owner
                deal.owner = assignee
                deal.save(update_fields=["owner", "updated_at"])

                old_owner_display = (
                    str(old_owner.get_full_name() or old_owner.email)
                    if old_owner
                    else "unassigned"
                )
                return (
                    f"Deal '{deal.name}' assigned to "
                    f"{assignee.get_full_name() or assignee.email} "
                    f"(was {old_owner_display})."
                )
            except Exception as e:
                logger.warning(
                    "Failed to assign deal (id=%s): %s",
                    deal_id,
                    str(e),
                )
                return f"Failed to assign deal (id={deal_id}): {str(e)}"

        customer_id = context.get("customer_id")
        if customer_id:
            return (
                f"Lead (customer_id={customer_id}) assigned to "
                f"{assignee.get_full_name() or assignee.email} "
                f"via {strategy} strategy."
            )

        return (
            f"No deal_id or customer_id in context; "
            f"assignee selected: {assignee.get_full_name() or assignee.email}."
        )

    def _action_create_task(
        self,
        rule: AutomationRule,
        config: Dict[str, Any],
        context: Dict[str, Any],
        triggered_by=None,
    ) -> str:
        """
        Execute a create_task action.

        Creates a new task linked to the customer/deal from the context.

        Config keys:
            - task_title: Title for the new task (optional, has default)
            - task_priority: Priority level (optional, default: 'medium')
            - delay_hours: Hours from now for the due date (optional, default: 24)

        Context keys:
            - customer_id: UUID of the related customer (optional)
            - deal_id: UUID of the related deal (optional)
        """
        from tasks.models import Task

        task_title = config.get("task_title", f"Follow-up: {rule.name}")
        task_priority = config.get("task_priority", "medium")
        delay_hours = config.get("delay_hours", 24)

        valid_priorities = [choice[0] for choice in Task.Priority.choices]
        if task_priority not in valid_priorities:
            task_priority = Task.Priority.MEDIUM

        try:
            delay_hours = int(delay_hours)
        except (ValueError, TypeError):
            delay_hours = 24

        from datetime import timedelta

        due_date = (timezone.now() + timedelta(hours=delay_hours)).date()

        customer = self._resolve_customer(context)
        deal = self._resolve_deal(context)

        assignee = triggered_by
        if assignee is None and deal is not None and deal.owner is not None:
            assignee = deal.owner

        task_data = {
            "title": task_title,
            "description": (
                f"Auto-created by automation rule: {rule.name}. "
                f"Trigger: {rule.get_trigger_type_display()}."
            ),
            "status": Task.Status.PENDING,
            "priority": task_priority,
            "due_date": due_date,
        }

        if customer is not None:
            task_data["customer"] = customer
        if deal is not None:
            task_data["deal"] = deal
        if assignee is not None:
            task_data["assigned_to"] = assignee
        if triggered_by is not None:
            task_data["created_by"] = triggered_by

        task = Task.objects.create(**task_data)

        assignee_display = ""
        if task.assigned_to:
            assignee_display = (
                f" assigned to {task.assigned_to.get_full_name() or task.assigned_to.email}"
            )

        return (
            f"Task '{task.title}' created (id={task.pk}){assignee_display}, "
            f"due {due_date.isoformat()}, priority={task_priority}."
        )

    def _resolve_customer(self, context: Dict[str, Any]):
        """Resolve a Customer instance from context['customer_id']."""
        customer_id = context.get("customer_id")
        if not customer_id:
            return None

        try:
            from customers.models import Customer

            return Customer.objects.get(pk=customer_id)
        except Exception:
            logger.warning(
                "Could not resolve customer_id=%s from context",
                customer_id,
            )
            return None

    def _resolve_deal(self, context: Dict[str, Any]):
        """Resolve a Deal instance from context['deal_id']."""
        deal_id = context.get("deal_id")
        if not deal_id:
            return None

        try:
            from deals.models import Deal

            return Deal.objects.select_related("owner", "customer").get(pk=deal_id)
        except Exception:
            logger.warning(
                "Could not resolve deal_id=%s from context",
                deal_id,
            )
            return None

    def _resolve_target_entity_type(self, context: Dict[str, Any]) -> str:
        """Determine the target entity type from context."""
        if context.get("deal_id"):
            return "Deal"
        if context.get("customer_id"):
            return "Customer"
        return "Unknown"

    def _resolve_target_entity_id(self, context: Dict[str, Any]) -> str:
        """Determine the target entity ID from context."""
        deal_id = context.get("deal_id")
        if deal_id:
            return str(deal_id)

        customer_id = context.get("customer_id")
        if customer_id:
            return str(customer_id)

        return str(uuid.uuid4())

    def _build_email_body(
        self,
        rule: AutomationRule,
        config: Dict[str, Any],
        context: Dict[str, Any],
        customer,
        template_name: str = "",
    ) -> str:
        """Build the email body for a send_email action."""
        if template_name:
            try:
                from django.template.loader import render_to_string

                template_context = {
                    "customer": customer,
                    "rule": rule,
                    "config": config,
                    "context": context,
                }
                return render_to_string(
                    f"emails/{template_name}.html",
                    template_context,
                )
            except Exception:
                logger.warning(
                    "Email template '%s' not found, using default body.",
                    template_name,
                )

        return (
            f"Dear {customer.name},\n\n"
            f"This is an automated follow-up regarding our recent interaction.\n\n"
            f"Rule: {rule.name}\n"
            f"Trigger: {rule.get_trigger_type_display()}\n\n"
            f"Please let us know if you have any questions.\n\n"
            f"Best regards,\n"
            f"CRM Team"
        )

    def _get_round_robin_assignee(self, user_model, team_role: str):
        """
        Get the next assignee using a simple round-robin strategy.

        Selects the active user with the specified role who has the fewest
        assigned deals, to distribute workload evenly.
        """
        from django.db.models import Count

        candidates = (
            user_model.objects.filter(
                role=team_role,
                is_active=True,
            )
            .annotate(deal_count=Count("owned_deals"))
            .order_by("deal_count", "created_at")
        )

        return candidates.first()

    def _create_log_entry(
        self,
        rule: AutomationRule,
        triggered_by,
        target_entity_type: str,
        target_entity_id: str,
        status: str,
        result_message: str,
    ) -> AutomationLog:
        """Create an AutomationLog entry for the execution."""
        try:
            log_entry = AutomationLog.objects.create(
                rule=rule,
                triggered_by=triggered_by if triggered_by and hasattr(triggered_by, "pk") else None,
                target_entity_type=target_entity_type,
                target_entity_id=str(target_entity_id),
                status=status,
                result_message=result_message or "",
            )
            return log_entry
        except Exception as e:
            logger.error(
                "Failed to create AutomationLog entry for rule '%s': %s",
                rule.name,
                str(e),
                exc_info=True,
            )
            raise