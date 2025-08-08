from django.core.management.base import BaseCommand
from django.utils import timezone
from payment_instructions.models import PaymentRecipient, MonthlyBalance
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class get_current_month_received(BaseCommand):
    help = 'Reset monthly balances for recurring recipients (monthly rollover process)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually doing it',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reset even if not at month boundary',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        now = timezone.now()
        current_month = now.month
        current_year = now.year
        
        self.stdout.write(f'Processing monthly reset for {current_year}-{current_month:02d}')
        
        if not force and now.day != 1:
            self.stdout.write(
                self.style.WARNING(
                    'Warning: This is not the first day of the month. '
                    'Use --force to proceed anyway.'
                )
            )
            return
        
        # Get all recurring, active recipients
        recurring_recipients = PaymentRecipient.objects.filter(
            is_recurring=True,
            is_active=True
        )
        
        if not recurring_recipients.exists():
            self.stdout.write('No recurring recipients found.')
            return
        
        self.stdout.write(f'Found {recurring_recipients.count()} recurring recipients to process')
        
        reset_summary = {
            'total_processed': 0,
            'recipients_reset': 0,
            'total_previous_amount': Decimal('0.00'),
            'recipients_with_balances': 0
        }
        
        if dry_run:
            self.stdout.write(self.style.WARNING('--- DRY RUN MODE ---'))
        
        for recipient in recurring_recipients:
            reset_summary['total_processed'] += 1
            
            # Get previous month's balance
            previous_month = current_month - 1 if current_month > 1 else 12
            previous_year = current_year if current_month > 1 else current_year - 1
            
            try:
                previous_balance = MonthlyBalance.objects.get(
                    payment_recipient=recipient,
                    year=previous_year,
                    month=previous_month
                )
                previous_amount = previous_balance.total_received
                reset_summary['total_previous_amount'] += previous_amount
                reset_summary['recipients_with_balances'] += 1
                
                self.stdout.write(
                    f'  {recipient.alias}: Previous month balance ${previous_amount:,.2f}'
                )
                
            except MonthlyBalance.DoesNotExist:
                previous_amount = Decimal('0.00')
                self.stdout.write(
                    f'  {recipient.alias}: No previous month balance found'
                )
            
            # Check current month status
            current_received = recipient.get_current_month_received()
            remaining = recipient.get_remaining_amount()
            
            self.stdout.write(
                f'    Current month: ${current_received:,.2f} received, '
                f'${remaining:,.2f} remaining of ${recipient.max_amount:,.2f} limit'
            )
            
            if not dry_run:
                # The reset is automatic - monthly balances are calculated on-demand
                # We just log the rollover event
                reset_summary['recipients_reset'] += 1
                logger.info(
                    f'Monthly rollover processed for {recipient.alias}. '
                    f'Previous month: ${previous_amount}, '
                    f'Current month: ${current_received}'
                )
        
        # Display summary
        self.stdout.write('\n--- RESET SUMMARY ---')
        self.stdout.write(f'Total recipients processed: {reset_summary["total_processed"]}')
        self.stdout.write(f'Recipients with previous balances: {reset_summary["recipients_with_balances"]}')
        self.stdout.write(f'Total previous month amount: ${reset_summary["total_previous_amount"]:,.2f}')
        
        if not dry_run:
            self.stdout.write(f'Recipients reset: {reset_summary["recipients_reset"]}')
            self.stdout.write(
                self.style.SUCCESS('Monthly reset completed successfully!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Dry run completed. Use without --dry-run to actually reset.')
            )
        
        # Show current system status
        self.stdout.write('\n--- CURRENT SYSTEM STATUS ---')
        summary = PaymentRecipient.get_payment_summary()
        self.stdout.write(f'Total recipients: {summary["total_recipients"]}')
        self.stdout.write(f'Active recipients: {summary["active_recipients"]}')
        self.stdout.write(f'Available recipients: {summary["available_recipients"]}')
        self.stdout.write(f'Completed this month: {summary["completed_this_month"]}')
        self.stdout.write(f'Total monthly capacity: ${summary["total_capacity"]:,.2f}')
        self.stdout.write(f'Total used this month: ${summary["total_used"]:,.2f}')
        
        capacity_percentage = 0
        if summary["total_capacity"] > 0:
            capacity_percentage = (summary["total_used"] / summary["total_capacity"]) * 100
        
        self.stdout.write(f'Overall capacity used: {capacity_percentage:.1f}%') 