import uuid
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import IntegrityError


class Command(BaseCommand):
    help = "Seed the database with initial data: sales stages, admin user, sample customers, deals, and automation rules. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            default=False,
            help="Delete existing seed data before re-creating.",
        )

    def handle(self, *args, **options):
        flush = options["flush"]

        if flush:
            self.stdout.write(self.style.WARNING("Flushing existing seed data..."))
            self._flush_data()

        self.stdout.write(self.style.NOTICE("Starting database seeding..."))

        self._create_sales_stages()
        admin_user = self._create_admin_user()
        customers = self._create_sample_customers(admin_user)
        self._create_sample_deals(admin_user, customers)
        self._create_sample_automation_rules(admin_user)

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully."))

    def _flush_data(self):
        from automation.models import AutomationLog, AutomationRule
        from deals.models import Deal, SalesStage
        from customers.models import Customer

        AutomationLog.objects.all().delete()
        AutomationRule.objects.all().delete()
        Deal.objects.all().delete()
        Customer.objects.all().delete()
        SalesStage.objects.all().delete()
        self.stdout.write(self.style.WARNING("Existing seed data flushed."))

    def _create_sales_stages(self):
        from deals.models import SalesStage

        stages = [
            {"name": "Lead", "order": 1, "is_active": True},
            {"name": "Qualified", "order": 2, "is_active": True},
            {"name": "Proposal", "order": 3, "is_active": True},
            {"name": "Negotiation", "order": 4, "is_active": True},
            {"name": "Closed Won", "order": 5, "is_active": True},
            {"name": "Closed Lost", "order": 6, "is_active": True},
        ]

        created_count = 0
        for stage_data in stages:
            stage, created = SalesStage.objects.get_or_create(
                name=stage_data["name"],
                defaults={
                    "order": stage_data["order"],
                    "is_active": stage_data["is_active"],
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"  Created sales stage: {stage.name}")
            else:
                self.stdout.write(f"  Sales stage already exists: {stage.name}")

        self.stdout.write(
            self.style.SUCCESS(f"Sales stages: {created_count} created, {len(stages) - created_count} already existed.")
        )

    def _create_admin_user(self):
        from django.conf import settings
        from django.apps import apps

        User = apps.get_model(settings.AUTH_USER_MODEL)

        admin_email = "admin@crm.local"
        admin_password = "admin123456"

        try:
            user = User.objects.get(email=admin_email)
            self.stdout.write(f"  Admin user already exists: {admin_email}")
            return user
        except User.DoesNotExist:
            pass

        try:
            user = User.objects.create_superuser(
                email=admin_email,
                password=admin_password,
                first_name="Admin",
                last_name="User",
            )
            self.stdout.write(self.style.SUCCESS(f"  Created admin user: {admin_email} (password: {admin_password})"))
            return user
        except IntegrityError:
            user = User.objects.get(email=admin_email)
            self.stdout.write(f"  Admin user already exists (race condition): {admin_email}")
            return user

    def _create_sample_customers(self, created_by):
        from customers.models import Customer

        customers_data = [
            {
                "name": "Acme Corporation",
                "email": "contact@acme.example.com",
                "phone": "+1 (555) 100-1000",
                "industry": "Technology",
                "company": "Acme Corp",
                "address": "123 Innovation Drive, San Francisco, CA 94105",
                "notes": "Enterprise client with multiple departments.",
            },
            {
                "name": "Globex Industries",
                "email": "info@globex.example.com",
                "phone": "+1 (555) 200-2000",
                "industry": "Manufacturing",
                "company": "Globex Industries",
                "address": "456 Factory Lane, Detroit, MI 48201",
                "notes": "Interested in CRM integration for supply chain.",
            },
            {
                "name": "Initech Solutions",
                "email": "sales@initech.example.com",
                "phone": "+1 (555) 300-3000",
                "industry": "Consulting",
                "company": "Initech Solutions",
                "address": "789 Business Park, Austin, TX 73301",
                "notes": "Mid-market consulting firm looking for deal tracking.",
            },
            {
                "name": "Umbrella Health",
                "email": "partnerships@umbrella.example.com",
                "phone": "+1 (555) 400-4000",
                "industry": "Healthcare",
                "company": "Umbrella Health Inc.",
                "address": "321 Medical Center Blvd, Boston, MA 02101",
                "notes": "Healthcare provider exploring patient relationship management.",
            },
            {
                "name": "Wayne Financial",
                "email": "biz@waynefin.example.com",
                "phone": "+1 (555) 500-5000",
                "industry": "Finance",
                "company": "Wayne Financial Services",
                "address": "555 Wall Street, New York, NY 10005",
                "notes": "High-value prospect in financial services sector.",
            },
        ]

        created_customers = []
        created_count = 0

        for cust_data in customers_data:
            customer, created = Customer.objects.get_or_create(
                email=cust_data["email"],
                defaults={
                    "name": cust_data["name"],
                    "phone": cust_data["phone"],
                    "industry": cust_data["industry"],
                    "company": cust_data["company"],
                    "address": cust_data["address"],
                    "notes": cust_data["notes"],
                    "created_by": created_by,
                },
            )
            created_customers.append(customer)
            if created:
                created_count += 1
                self.stdout.write(f"  Created customer: {customer.name}")
            else:
                self.stdout.write(f"  Customer already exists: {customer.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Customers: {created_count} created, {len(customers_data) - created_count} already existed."
            )
        )
        return created_customers

    def _create_sample_deals(self, owner, customers):
        from deals.models import Deal, SalesStage

        stages = {stage.name: stage for stage in SalesStage.objects.all()}

        if not stages:
            self.stdout.write(self.style.WARNING("  No sales stages found. Skipping deal creation."))
            return

        if not customers:
            self.stdout.write(self.style.WARNING("  No customers found. Skipping deal creation."))
            return

        deals_data = [
            {
                "name": "Acme Enterprise License",
                "value": Decimal("150000.00"),
                "customer_index": 0,
                "stage_name": "Negotiation",
                "expected_close_date": "2025-03-15",
                "description": "Enterprise license deal for Acme Corporation covering 500 seats.",
            },
            {
                "name": "Globex CRM Integration",
                "value": Decimal("75000.00"),
                "customer_index": 1,
                "stage_name": "Proposal",
                "expected_close_date": "2025-04-01",
                "description": "CRM integration project for Globex supply chain management.",
            },
            {
                "name": "Initech Consulting Package",
                "value": Decimal("45000.00"),
                "customer_index": 2,
                "stage_name": "Qualified",
                "expected_close_date": "2025-05-10",
                "description": "Consulting package for deal tracking and pipeline management.",
            },
            {
                "name": "Umbrella Health Platform",
                "value": Decimal("200000.00"),
                "customer_index": 3,
                "stage_name": "Lead",
                "expected_close_date": "2025-06-30",
                "description": "Patient relationship management platform for Umbrella Health.",
            },
            {
                "name": "Wayne Financial Analytics",
                "value": Decimal("120000.00"),
                "customer_index": 4,
                "stage_name": "Closed Won",
                "expected_close_date": "2025-01-31",
                "description": "Financial analytics and reporting dashboard for Wayne Financial.",
            },
        ]

        created_count = 0
        for deal_data in deals_data:
            customer_index = deal_data["customer_index"]
            if customer_index >= len(customers):
                continue

            customer = customers[customer_index]
            stage_name = deal_data["stage_name"]
            stage = stages.get(stage_name)

            if stage is None:
                self.stdout.write(
                    self.style.WARNING(f"  Stage '{stage_name}' not found. Skipping deal: {deal_data['name']}")
                )
                continue

            existing = Deal.objects.filter(
                name=deal_data["name"],
                customer=customer,
            ).first()

            if existing:
                self.stdout.write(f"  Deal already exists: {deal_data['name']}")
                continue

            try:
                from datetime import date as date_type

                close_date_parts = deal_data["expected_close_date"].split("-")
                expected_close = date_type(
                    int(close_date_parts[0]),
                    int(close_date_parts[1]),
                    int(close_date_parts[2]),
                )

                Deal.objects.create(
                    name=deal_data["name"],
                    value=deal_data["value"],
                    customer=customer,
                    owner=owner,
                    stage=stage,
                    expected_close_date=expected_close,
                    description=deal_data["description"],
                )
                created_count += 1
                self.stdout.write(f"  Created deal: {deal_data['name']}")
            except IntegrityError as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create deal '{deal_data['name']}': {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Deals: {created_count} created, {len(deals_data) - created_count} already existed or skipped."
            )
        )

    def _create_sample_automation_rules(self, created_by):
        from automation.models import AutomationRule

        rules_data = [
            {
                "name": "Follow-up after meeting",
                "trigger_type": "meeting_completed",
                "action_type": "create_task",
                "config": {
                    "task_title": "Follow up after meeting",
                    "task_priority": "high",
                    "delay_hours": 24,
                },
                "is_active": True,
            },
            {
                "name": "Send welcome email to new leads",
                "trigger_type": "new_lead",
                "action_type": "send_email",
                "config": {
                    "email_template": "welcome_lead",
                    "subject": "Welcome! Let's get started",
                    "delay_minutes": 5,
                },
                "is_active": True,
            },
            {
                "name": "Auto-assign new leads to sales team",
                "trigger_type": "new_lead",
                "action_type": "assign_lead",
                "config": {
                    "assignment_strategy": "round_robin",
                    "team": "sales",
                },
                "is_active": True,
            },
            {
                "name": "Create follow-up task after demo",
                "trigger_type": "demo_completed",
                "action_type": "create_task",
                "config": {
                    "task_title": "Send proposal after demo",
                    "task_priority": "urgent",
                    "delay_hours": 2,
                },
                "is_active": True,
            },
            {
                "name": "Notify on call completion",
                "trigger_type": "call_completed",
                "action_type": "send_email",
                "config": {
                    "email_template": "call_summary",
                    "subject": "Call Summary",
                    "send_to_manager": True,
                },
                "is_active": False,
            },
        ]

        created_count = 0
        for rule_data in rules_data:
            rule, created = AutomationRule.objects.get_or_create(
                name=rule_data["name"],
                created_by=created_by,
                defaults={
                    "trigger_type": rule_data["trigger_type"],
                    "action_type": rule_data["action_type"],
                    "config": rule_data["config"],
                    "is_active": rule_data["is_active"],
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"  Created automation rule: {rule.name}")
            else:
                self.stdout.write(f"  Automation rule already exists: {rule.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Automation rules: {created_count} created, {len(rules_data) - created_count} already existed."
            )
        )