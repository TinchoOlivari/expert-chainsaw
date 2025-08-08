from django.core.management.base import BaseCommand
from payment_instructions.models import PaymentRecipient, Payment
from decimal import Decimal


class Command(BaseCommand):
    help = 'Test automatic recipient selection logic with different payment amounts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--amount',
            type=float,
            help='Test with specific amount',
        )

    def handle(self, *args, **options):
        self.stdout.write('Testing automatic recipient selection logic...\n')
        
        # Show current recipient status
        recipients = PaymentRecipient.objects.filter(is_active=True).order_by('priority_order')
        
        self.stdout.write('--- CURRENT RECIPIENTS STATUS ---')
        for recipient in recipients:
            remaining = recipient.get_remaining_amount()
            capacity = recipient.get_capacity_percentage()
            
            self.stdout.write(
                f'{recipient.priority_order}. {recipient.alias}: '
                f'${remaining:,.2f} available (${recipient.max_amount:,.2f} max) '
            )
        
        # Test amounts
        test_amounts = [
            Decimal('1000.00'),
            Decimal('5000.00'),
            Decimal('10000.00'),
            Decimal('25000.00'),
            Decimal('50000.00'),
            Decimal('75000.00')
        ]
        
        if options['amount']:
            test_amounts = [Decimal(str(options['amount']))]
        
        self.stdout.write('\n--- RECIPIENT SELECTION TESTS ---')
        
        for amount in test_amounts:
            self.stdout.write(f'\nTesting amount: ${amount:,.2f}')
            
            # Get available recipients for this amount
            available = PaymentRecipient.objects.get_available_recipients(amount)
            
            if not available.exists():
                self.stdout.write('  ❌ No recipients available for this amount')
                continue
            
            self.stdout.write(f'  Available recipients: {available.count()}')
            for recipient in available:
                remaining = recipient.get_remaining_amount()
                self.stdout.write(f'    - {recipient.alias}: ${remaining:,.2f} available')
            
            # Find best recipient
            best_recipient = PaymentRecipient.objects.find_best_recipient(amount)
            
            if best_recipient:
                remaining = best_recipient.get_remaining_amount()
                waste = remaining - amount
                waste_percentage = (waste / remaining * 100) if remaining > 0 else 0
                
                self.stdout.write(
                    f'  ✅ Best recipient: {best_recipient.alias} '
                    f'(${remaining:,.2f} available, ${waste:,.2f} waste, {waste_percentage:.1f}% waste)'
                )
            else:
                self.stdout.write('  ❌ No suitable recipient found')
        
        # Show system summary
        self.stdout.write('\n--- SYSTEM SUMMARY ---')
        summary = PaymentRecipient.get_payment_summary()
        
        self.stdout.write(f'Total capacity: ${summary["total_capacity"]:,.2f}')
        self.stdout.write(f'Total used: ${summary["total_used"]:,.2f}')
        
        if summary["total_capacity"] > 0:
            usage_percentage = (summary["total_used"] / summary["total_capacity"]) * 100
            remaining_capacity = summary["total_capacity"] - summary["total_used"]
            self.stdout.write(f'Usage: {usage_percentage:.1f}%')
            self.stdout.write(f'Remaining capacity: ${remaining_capacity:,.2f}')
        
        self.stdout.write(f'Recipients by status: {summary["recipients_by_status"]}') 