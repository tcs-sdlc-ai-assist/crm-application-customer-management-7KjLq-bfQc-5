import logging
import uuid
from typing import Any, Dict, Optional

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="automation.tasks.send_follow_up_email_task",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_follow_up_email_task(
    self,
    customer_id: str,
    rule_id: str,
    triggered_by_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
):
    """
    Celery task that sends a follow-up email after a meeting/call/demo.

    Args:
        customer_id: UUID string of the customer to email.
        rule_id: UUID string of the automation rule that triggered this task.
        triggered_by_id: UUID string of the user who triggered the event (optional).
        context: Additional context data for the email (optional).
    """
    if context is None:
        context = {}

    logger.info(
        "send_follow_up_email_task started: customer_id=%s rule_id=%s triggered_by=%s",
        customer_id,
        rule_id,
        triggered_by_id,
    )

    try:
        from automation.models import AutomationLog, AutomationRule
        from customers.models import Customer

        try:
            rule = AutomationRule.objects.get(pk=rule_id)
        except AutomationRule.DoesNotExist:
            logger.error(
                "Automation rule not found: rule_id=%s",
                rule_id,
            )
            return {"status": "failed", "error": f"Rule {rule_id} not found"}

        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            logger.error(
                "Customer not found: customer_id=%s",
                customer_id,
            )
            _create_automation_log(
                rule=rule,
                triggered_by_id=triggered_by_id,
                target_entity_type="Customer",
                target_entity_id=str(customer_id),
                status="failed",
                result_message=f"Customer {customer_id} not found.",
            )
            return {"status": "failed", "error": f"Customer {customer_id} not found"}

        if not customer.email:
            message = f"Customer '{customer.name}' has no email address; email not sent."
            logger.warning(
                "send_follow_up_email_task: %s",
                message,
            )
            _create_automation_log(
                rule=rule,
                triggered_by_id=triggered_by_id,
                target_entity_type="Customer",
                target_entity_id=str(customer_id),
                status="failed",
                result_message=message,
            )
            return {"status": "failed", "error": message}

        triggered_by_user = _resolve_user(triggered_by_id)
        config = rule.config if isinstance(rule.config, dict) else {}
        subject = config.get("subject", f"Follow-up: {rule.name}")
        body = (
            f"Dear {customer.name},\n\n"
            f"This is an automated follow-up regarding our recent interaction.\n\n"
            f"Rule: {rule.name}\n"
            f"Trigger: {rule.get_trigger_type_display()}\n\n"
            f"Please let us know if you have any questions.\n\n"
            f"Best regards,\n"
            f"CRM Team"
        )

        email_sent = False
        email_result_message = ""

        try:
            from integrations.services import GmailAdapter

            if triggered_by_user is not None:
                adapter = GmailAdapter(user=triggered_by_user)
                result = adapter.send_email(
                    to=customer.email,
                    subject=subject,
                    body=body,
                )
                email_id = result.get("email_id", "unknown")
                email_result_message = f"Email sent via Gmail to {customer.email} (id={email_id})."
                email_sent = True
        except Exception as gmail_error:
            logger.warning(
                "Gmail adapter unavailable or failed for rule '%s': %s. "
                "Falling back to Django email.",
                rule.name,
                str(gmail_error),
            )

        if not email_sent:
            try:
                from django.conf import settings
                from django.core.mail import send_mail

                send_mail(
                    subject=subject,
                    message=body,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[customer.email],
                    fail_silently=False,
                )
                email_result_message = f"Email sent via Django mail to {customer.email}."
                email_sent = True
            except Exception as mail_error:
                error_message = f"Failed to send email to {customer.email}: {str(mail_error)}"
                logger.error(
                    "send_follow_up_email_task failed: %s",
                    error_message,
                )
                _create_automation_log(
                    rule=rule,
                    triggered_by_id=triggered_by_id,
                    target_entity_type="Customer",
                    target_entity_id=str(customer_id),
                    status="failed",
                    result_message=error_message,
                )
                raise self.retry(exc=mail_error)

        _create_automation_log(
            rule=rule,
            triggered_by_id=triggered_by_id,
            target_entity_type="Customer",
            target_entity_id=str(customer_id),
            status="success",
            result_message=email_result_message,
        )

        logger.info(
            "send_follow_up_email_task completed: %s",
            email_result_message,
        )

        return {"status": "success", "message": email_result_message}

    except Exception as exc:
        logger.error(
            "send_follow_up_email_task unexpected error: customer_id=%s rule_id=%s error=%s",
            customer_id,
            rule_id,
            str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="automation.tasks.assign_lead_task",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def assign_lead_task(
    self,
    rule_id: str,
    triggered_by_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
):
    """
    Celery task that assigns a lead to a sales rep based on automation rules.

    Args:
        rule_id: UUID string of the automation rule that triggered this task.
        triggered_by_id: UUID string of the user who triggered the event (optional).
        context: Dictionary containing deal_id and/or customer_id (optional).
    """
    if context is None:
        context = {}

    logger.info(
        "assign_lead_task started: rule_id=%s triggered_by=%s context_keys=%s",
        rule_id,
        triggered_by_id,
        list(context.keys()),
    )

    try:
        from automation.models import AutomationLog, AutomationRule

        try:
            rule = AutomationRule.objects.get(pk=rule_id)
        except AutomationRule.DoesNotExist:
            logger.error("Automation rule not found: rule_id=%s", rule_id)
            return {"status": "failed", "error": f"Rule {rule_id} not found"}

        config = rule.config if isinstance(rule.config, dict) else {}
        strategy = config.get("assignment_strategy", "round_robin")
        team_role = config.get("team", "sales")

        target_entity_type = "Deal" if context.get("deal_id") else "Customer"
        target_entity_id = str(context.get("deal_id") or context.get("customer_id") or uuid.uuid4())

        from django.apps import apps
        from django.conf import settings
        from django.db.models import Count

        UserModel = apps.get_model(settings.AUTH_USER_MODEL)

        assignee = None

        if strategy == "specific":
            assignee_id = config.get("assignee_id")
            if assignee_id:
                try:
                    assignee = UserModel.objects.get(pk=assignee_id, is_active=True)
                except UserModel.DoesNotExist:
                    message = f"Specified assignee (id={assignee_id}) not found or inactive."
                    _create_automation_log(
                        rule=rule,
                        triggered_by_id=triggered_by_id,
                        target_entity_type=target_entity_type,
                        target_entity_id=target_entity_id,
                        status="failed",
                        result_message=message,
                    )
                    return {"status": "failed", "error": message}
            else:
                message = "No assignee_id provided for 'specific' assignment strategy."
                _create_automation_log(
                    rule=rule,
                    triggered_by_id=triggered_by_id,
                    target_entity_type=target_entity_type,
                    target_entity_id=target_entity_id,
                    status="failed",
                    result_message=message,
                )
                return {"status": "failed", "error": message}
        else:
            candidates = (
                UserModel.objects.filter(
                    role=team_role,
                    is_active=True,
                )
                .annotate(deal_count=Count("owned_deals"))
                .order_by("deal_count", "created_at")
            )
            assignee = candidates.first()

            if assignee is None:
                message = f"No active users with role '{team_role}' available for assignment."
                _create_automation_log(
                    rule=rule,
                    triggered_by_id=triggered_by_id,
                    target_entity_type=target_entity_type,
                    target_entity_id=target_entity_id,
                    status="failed",
                    result_message=message,
                )
                return {"status": "failed", "error": message}

        result_message = ""
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
                result_message = (
                    f"Deal '{deal.name}' assigned to "
                    f"{assignee.get_full_name() or assignee.email} "
                    f"(was {old_owner_display})."
                )
            except Exception as e:
                result_message = f"Failed to assign deal (id={deal_id}): {str(e)}"
                logger.warning("assign_lead_task: %s", result_message)
                _create_automation_log(
                    rule=rule,
                    triggered_by_id=triggered_by_id,
                    target_entity_type=target_entity_type,
                    target_entity_id=target_entity_id,
                    status="failed",
                    result_message=result_message,
                )
                return {"status": "failed", "error": result_message}
        else:
            customer_id = context.get("customer_id")
            result_message = (
                f"Lead (customer_id={customer_id}) assigned to "
                f"{assignee.get_full_name() or assignee.email} "
                f"via {strategy} strategy."
            )

        _create_automation_log(
            rule=rule,
            triggered_by_id=triggered_by_id,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            status="success",
            result_message=result_message,
        )

        logger.info("assign_lead_task completed: %s", result_message)
        return {"status": "success", "message": result_message}

    except Exception as exc:
        logger.error(
            "assign_lead_task unexpected error: rule_id=%s error=%s",
            rule_id,
            str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="automation.tasks.send_task_reminder_task",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_task_reminder_task(
    self,
    task_id: Optional[str] = None,
    hours_before_due: int = 24,
):
    """
    Celery task that sends reminders for upcoming task due dates.

    If task_id is provided, sends a reminder for that specific task.
    If task_id is None, scans for all tasks due within hours_before_due
    and sends reminders for each.

    Args:
        task_id: UUID string of a specific task (optional).
        hours_before_due: Number of hours before due date to send reminder (default: 24).
    """
    logger.info(
        "send_task_reminder_task started: task_id=%s hours_before_due=%d",
        task_id,
        hours_before_due,
    )

    try:
        from datetime import timedelta

        from tasks.models import Task

        if task_id is not None:
            try:
                task = Task.objects.select_related(
                    "assigned_to", "customer", "deal"
                ).get(pk=task_id)
            except Task.DoesNotExist:
                logger.warning("Task not found for reminder: task_id=%s", task_id)
                return {"status": "failed", "error": f"Task {task_id} not found"}

            if task.status in (Task.Status.COMPLETED, Task.Status.CANCELLED):
                logger.info(
                    "Task %s is %s, skipping reminder.",
                    task_id,
                    task.status,
                )
                return {"status": "skipped", "reason": f"Task is {task.status}"}

            _send_single_task_reminder(task)
            return {"status": "success", "task_id": str(task.pk)}

        now = timezone.now()
        reminder_cutoff = (now + timedelta(hours=hours_before_due)).date()

        upcoming_tasks = Task.objects.select_related(
            "assigned_to", "customer", "deal"
        ).filter(
            due_date__isnull=False,
            due_date__lte=reminder_cutoff,
            due_date__gte=now.date(),
        ).exclude(
            status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED],
        )

        reminder_count = 0
        for task in upcoming_tasks:
            try:
                _send_single_task_reminder(task)
                reminder_count += 1
            except Exception as e:
                logger.warning(
                    "Failed to send reminder for task %s: %s",
                    task.pk,
                    str(e),
                )

        logger.info(
            "send_task_reminder_task completed: %d reminders sent",
            reminder_count,
        )
        return {"status": "success", "reminders_sent": reminder_count}

    except Exception as exc:
        logger.error(
            "send_task_reminder_task unexpected error: %s",
            str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="automation.tasks.process_automation_event_task",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_automation_event_task(
    self,
    event_type: str,
    context: Optional[Dict[str, Any]] = None,
    triggered_by_id: Optional[str] = None,
):
    """
    Celery task that evaluates and executes automation rules for a given event.

    Uses the AutomationEngine to find matching rules and execute their actions.

    Args:
        event_type: The type of event (e.g., 'meeting_completed', 'call_completed',
                    'demo_completed', 'new_lead').
        context: Dictionary containing event context data such as customer_id,
                 deal_id, user_id, etc. (optional).
        triggered_by_id: UUID string of the user who triggered the event (optional).
    """
    if context is None:
        context = {}

    logger.info(
        "process_automation_event_task started: event_type=%s triggered_by=%s context_keys=%s",
        event_type,
        triggered_by_id,
        list(context.keys()),
    )

    if not event_type:
        logger.warning("process_automation_event_task called with empty event_type")
        return {"status": "failed", "error": "Empty event_type"}

    try:
        from automation.engine import AutomationEngine

        triggered_by_user = _resolve_user(triggered_by_id)

        engine = AutomationEngine()
        logs = engine.publish_event(
            event_type=event_type,
            context=context,
            triggered_by=triggered_by_user,
        )

        results = []
        for log_entry in logs:
            results.append({
                "log_id": str(log_entry.pk),
                "rule": log_entry.rule.name,
                "status": log_entry.status,
                "message": log_entry.result_message,
            })

        logger.info(
            "process_automation_event_task completed: event_type=%s rules_executed=%d",
            event_type,
            len(results),
        )

        return {
            "status": "success",
            "event_type": event_type,
            "rules_executed": len(results),
            "results": results,
        }

    except Exception as exc:
        logger.error(
            "process_automation_event_task unexpected error: event_type=%s error=%s",
            event_type,
            str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)


def _resolve_user(user_id: Optional[str]):
    """Resolve a user instance from a user ID string. Returns None if not found."""
    if not user_id:
        return None

    try:
        from django.apps import apps
        from django.conf import settings

        UserModel = apps.get_model(settings.AUTH_USER_MODEL)
        return UserModel.objects.get(pk=user_id)
    except Exception:
        logger.warning("Could not resolve user_id=%s", user_id)
        return None


def _create_automation_log(
    rule,
    triggered_by_id: Optional[str],
    target_entity_type: str,
    target_entity_id: str,
    status: str,
    result_message: str,
):
    """Create an AutomationLog entry. Failures are logged but not raised."""
    try:
        from automation.models import AutomationLog

        triggered_by_user = _resolve_user(triggered_by_id)

        AutomationLog.objects.create(
            rule=rule,
            triggered_by=triggered_by_user,
            target_entity_type=target_entity_type,
            target_entity_id=str(target_entity_id),
            status=status,
            result_message=result_message or "",
        )
    except Exception as e:
        logger.error(
            "Failed to create AutomationLog entry: %s",
            str(e),
            exc_info=True,
        )


def _send_single_task_reminder(task):
    """
    Send a reminder notification for a single task.

    Attempts to send via Slack first, then falls back to Django email.
    """
    assignee = task.assigned_to
    if assignee is None:
        logger.info(
            "Task %s has no assignee, skipping reminder.",
            task.pk,
        )
        return

    task_title = task.title or "Untitled Task"
    due_date_str = task.due_date.isoformat() if task.due_date else "No due date"
    customer_name = task.customer.name if task.customer else "N/A"
    deal_name = task.deal.name if task.deal else "N/A"

    reminder_message = (
        f"🔔 Task Reminder: *{task_title}*\n"
        f"Due: {due_date_str}\n"
        f"Priority: {task.get_priority_display()}\n"
        f"Customer: {customer_name}\n"
        f"Deal: {deal_name}\n"
        f"Status: {task.get_status_display()}"
    )

    notification_sent = False

    try:
        from integrations.services import SlackAdapter

        adapter = SlackAdapter(user=assignee)
        adapter.send_notification(
            message=reminder_message,
            username="CRM Task Reminder",
            icon_emoji=":bell:",
        )
        notification_sent = True
        logger.info(
            "Slack reminder sent for task %s to %s",
            task.pk,
            assignee.email,
        )
    except Exception as slack_error:
        logger.warning(
            "Slack reminder failed for task %s: %s. Falling back to email.",
            task.pk,
            str(slack_error),
        )

    if not notification_sent and assignee.email:
        try:
            from django.conf import settings
            from django.core.mail import send_mail

            email_subject = f"Task Reminder: {task_title} (Due: {due_date_str})"
            email_body = (
                f"Hi {assignee.get_full_name() or assignee.email},\n\n"
                f"This is a reminder for your upcoming task:\n\n"
                f"Title: {task_title}\n"
                f"Due Date: {due_date_str}\n"
                f"Priority: {task.get_priority_display()}\n"
                f"Customer: {customer_name}\n"
                f"Deal: {deal_name}\n"
                f"Status: {task.get_status_display()}\n\n"
                f"Please ensure this task is completed on time.\n\n"
                f"Best regards,\n"
                f"CRM System"
            )

            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[assignee.email],
                fail_silently=False,
            )
            notification_sent = True
            logger.info(
                "Email reminder sent for task %s to %s",
                task.pk,
                assignee.email,
            )
        except Exception as email_error:
            logger.error(
                "Email reminder failed for task %s: %s",
                task.pk,
                str(email_error),
            )

    if not notification_sent:
        logger.warning(
            "No reminder sent for task %s — all notification channels failed.",
            task.pk,
        )