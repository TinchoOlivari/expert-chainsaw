from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.core.exceptions import ValidationError
import os
from datetime import datetime

def modify_file_name(instance, filename):
    ext = filename.split('.')[-1]
    alias = instance.payment_recipient.alias if instance.payment_recipient else "unknown"
    day = datetime.now().strftime("%d_%H_%M_%S")
    year = datetime.now().strftime("%Y")
    month = datetime.now().strftime("%m")
    
    new_filename = f"{alias}_{day}.{ext}"
    return os.path.join(f'comprobantes/{year}/{month}', new_filename)


class Bank(models.Model):
    name = models.CharField(
        verbose_name='Nombre del Banco',
        max_length=100,
        unique=True,
        help_text='Nombre del banco o billetera virtual'
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Banco'
        verbose_name_plural = 'Bancos'
    
    def __str__(self):
        return self.name

class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('Username is required')
        email = self.normalize_email(email) if email else None
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.ADMINISTRATOR)
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    ADMINISTRATOR = 'administrator'
    OPERATOR = 'operator'
    
    ROLE_CHOICES = [
        (ADMINISTRATOR, 'Administrator'),
        (OPERATOR, 'Operator'),
    ]
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=OPERATOR,
        help_text='Rol del usuario'
    )
    
    objects = UserManager()
    
    def is_administrator(self):
        return self.role == self.ADMINISTRATOR
    
    def is_operator(self):
        return self.role == self.OPERATOR
    
    def __str__(self):
        return f"{self.username}"


class PaymentRecipientManager(models.Manager):
    def get_available_recipients(self, amount=None):
        """Get active recipients that can receive payments, ordered by priority"""
        queryset = self.filter(is_active=True)
        
        if amount is not None:
            # Filter recipients that can receive the specified amount
            available_recipients = []
            for recipient in queryset:
                if recipient.can_receive_amount(amount):
                    available_recipients.append(recipient.pk)
            queryset = queryset.filter(pk__in=available_recipients)
        
        return queryset.order_by('priority_order', 'name')
    
    def find_best_recipient(self, amount):
        """Find the best recipient for a given amount based on priority and availability"""
        available = self.get_available_recipients(amount)
        
        # First try: exact or close match that doesn't waste capacity
        # for recipient in available:
        #     remaining = recipient.get_remaining_amount()
        #     # Prefer recipients where the amount uses significant capacity but doesn't waste much
        #     if remaining >= amount and (remaining - amount) <= remaining * Decimal('0.3'):
        #         return recipient
        
        # Second try: any recipient that can handle the amount, by priority
        for recipient in available:
            if recipient.can_receive_amount(amount):
                return recipient
        
        return None


class PaymentRecipient(models.Model):
    name = models.CharField(
        verbose_name='Nombre',
        max_length=200,
        help_text='Nombre del destinatario'
    )
    alias = models.CharField(
        max_length=100,
        unique=True,
        help_text='Alias del destinatario'
    )
    cbu = models.CharField(
        verbose_name='CBU / CVU',
        max_length=22,
        unique=True,
        help_text='CBU / CVU del destinatario'
    )
    bank = models.ForeignKey(
        Bank,
        verbose_name='Banco',
        on_delete=models.PROTECT,
        related_name='payment_recipients',
        help_text='Banco o billetera virtual del destinatario',
        null=True,
        blank=True
    )
    max_amount = models.PositiveIntegerField(
        verbose_name='Salario',
        help_text='Monto que el destinatario puede recibir'
    )
    is_recurring = models.BooleanField(
        verbose_name='Recurrente',
        default=True,
        help_text='Si es Verdadero, se reinicia mensualmente. Si es Falso, es un pago único'
    )
    priority_order = models.PositiveIntegerField(
        verbose_name='Orden',
        default=1,
        help_text='Orden de prioridad para la selección automática (Menor numero es mayor prioridad)'
    )
    is_active = models.BooleanField(
        verbose_name='Activo',
        default=True,
        help_text='Si es Verdadero, el destinatario puede recibir pagos. Si es Falso, el destinatario no puede recibir pagos'
    )
    created_at = models.DateTimeField(
        verbose_name='Creado',
        auto_now_add=True)
    updated_at = models.DateTimeField(
        verbose_name='Actualizado',
        auto_now=True)
    
    objects = PaymentRecipientManager()
    
    class Meta:
        ordering = ['priority_order', 'name']
        verbose_name = 'Destinatario'
        verbose_name_plural = 'Destinatarios'
    
    def __str__(self):
        return f"{self.alias}"
    
    def clean(self):
        """Validate model data"""
        super().clean()
        
        if self.max_amount <= 0:
            raise ValidationError({'max_amount': 'Maximum amount must be greater than zero.'})
        
        if self.priority_order <= 0:
            raise ValidationError({'priority_order': 'Priority order must be greater than zero.'})
        
        # Check for duplicate priority (but allow during save process)
        if hasattr(self, '_skip_priority_validation'):
            pass  # Skip validation during internal operations
        else:
            existing = PaymentRecipient.objects.filter(priority_order=self.priority_order)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                # This will be handled automatically by the save method
                pass
        
        # Validate CBU format (should be 22 digits)
        if self.cbu and not self.cbu.isdigit():
            raise ValidationError({'cbu': 'CBU must contain only digits.'})
        
        if self.cbu and len(self.cbu) != 22:
            raise ValidationError({'cbu': 'CBU must be exactly 22 digits long.'})
    
    def save(self, *args, **kwargs):
        """Override save to handle unique priority logic"""
        from django.db import transaction
        
        # Use transaction to ensure atomicity
        with transaction.atomic():
            # Check if this is an update and priority has changed
            if self.pk:
                try:
                    old_instance = PaymentRecipient.objects.get(pk=self.pk)
                    old_priority = old_instance.priority_order
                except PaymentRecipient.DoesNotExist:
                    old_priority = None
            else:
                old_priority = None
            
            new_priority = self.priority_order
            
            # If priority changed or this is a new instance, adjust other priorities
            if old_priority != new_priority:
                self._adjust_priorities(old_priority, new_priority)
            
            super().save(*args, **kwargs)
    
    def _adjust_priorities(self, old_priority, new_priority):
        """Adjust priorities of other recipients when this one changes"""
        # Get all other recipients (excluding this one if it exists)
        other_recipients = PaymentRecipient.objects.exclude(pk=self.pk if self.pk else 0)
        
        if old_priority is None:
            # New recipient - shift all recipients with priority >= new_priority
            other_recipients.filter(priority_order__gte=new_priority).update(
                priority_order=models.F('priority_order') + 1
            )
        else:
            # Existing recipient changing priority
            if new_priority < old_priority:
                # Moving up (lower number = higher priority)
                # Shift down recipients between new_priority and old_priority-1
                other_recipients.filter(
                    priority_order__gte=new_priority,
                    priority_order__lt=old_priority
                ).update(priority_order=models.F('priority_order') + 1)
            elif new_priority > old_priority:
                # Moving down (higher number = lower priority)
                # Shift up recipients between old_priority+1 and new_priority
                other_recipients.filter(
                    priority_order__gt=old_priority,
                    priority_order__lte=new_priority
                ).update(priority_order=models.F('priority_order') - 1)
    
    def delete(self, *args, **kwargs):
        """Override delete to maintain priority order continuity"""
        priority_to_remove = self.priority_order
        super().delete(*args, **kwargs)
        
        # Shift up all recipients with priority > deleted priority
        PaymentRecipient.objects.filter(
            priority_order__gt=priority_to_remove
        ).update(priority_order=models.F('priority_order') - 1)
    
    def get_current_month_received(self, exclude_payment=None):
        """Get total amount received this month, optionally excluding a specific payment"""
        current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        queryset = self.payments.filter(created_at__gte=current_month)
        
        # Exclude specific payment if provided (useful when editing)
        if exclude_payment:
            queryset = queryset.exclude(pk=exclude_payment.pk)
        
        total = queryset.aggregate(total=models.Sum('amount'))['total']
        return total or 0
    
    def get_remaining_amount(self, exclude_payment=None):
        """Get remaining amount available for this recipient this month"""
        received = self.get_current_month_received(exclude_payment=exclude_payment)
        return self.max_amount - received
    
    def is_completed_this_month(self):
        """Check if recipient has reached max amount this month"""
        return self.get_remaining_amount() <= 0
    
    def can_receive_amount(self, amount, exclude_payment=None):
        """Check if recipient can receive the specified amount"""
        if not self.is_active:
            return False
        
        # For one-time recipients, check if they have already received any payment
        if not self.is_recurring:
            queryset = self.payments
            if exclude_payment:
                queryset = queryset.exclude(pk=exclude_payment.pk)
            
            total_received = queryset.aggregate(
                total=models.Sum('amount')
            )['total'] or 0
            return total_received == 0 and amount <= self.max_amount
        
        # For recurring recipients, check monthly limit
        return self.get_remaining_amount(exclude_payment=exclude_payment) >= amount
    
    def get_capacity_percentage(self):
        """Get the percentage of capacity used this month"""
        if self.max_amount == 0:
            return 100
        received = self.get_current_month_received()
        return float((received / self.max_amount) * 100)
    
    def get_status(self):
        """Get current status of the recipient"""
        if not self.is_active:
            return 'inactive'
        
        if not self.is_recurring:
            total_received = self.payments.aggregate(total=models.Sum('amount'))['total'] or 0
            if total_received > 0:
                return 'completed_onetime'
            return 'available_onetime'
        
        return 'available'
    
    def suggest_max_payment(self):
        """Suggest maximum payment amount that can be made to this recipient"""
        if not self.is_active:
            return 0
        
        if not self.is_recurring:
            total_received = self.payments.aggregate(
                total=models.Sum('amount')
            )['total'] or 0
            if total_received > 0:
                return 0
            return self.max_amount
        
        return self.get_remaining_amount()
    
    @classmethod
    def get_payment_summary(cls):
        """Get summary of all recipients and their current status"""
        summary = {
            'total_recipients': cls.objects.count(),
            'active_recipients': cls.objects.filter(is_active=True).count(),
            'completed_this_month': 0,
            'available_recipients': 0,
            'total_capacity': 0,
            'total_used': 0,
            'recipients_by_status': {}
        }
        
        status_counts = {}
        for recipient in cls.objects.filter(is_active=True):
            status = recipient.get_status()
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if recipient.is_recurring:
                summary['total_capacity'] += recipient.max_amount
                summary['total_used'] += recipient.get_current_month_received()
            
            if status in ['completed_monthly', 'completed_onetime']:
                summary['completed_this_month'] += 1
            elif status in ['available', 'half_full', 'nearly_full', 'available_onetime']:
                summary['available_recipients'] += 1
        
        summary['recipients_by_status'] = status_counts
        return summary


class Payment(models.Model):
    amount = models.PositiveIntegerField(
        verbose_name='Monto',
        help_text='Monto del pago'
    )
    payment_recipient = models.ForeignKey(
        PaymentRecipient,
        verbose_name='Destinatario',
        on_delete=models.PROTECT,
        related_name='payments',
        help_text='Destinatario del pago'
    )
    proof_of_payment_file = models.FileField(
        verbose_name='Comprobante',
        upload_to=modify_file_name,
        blank=True,
        null=True,
        help_text='Subir comprobante de pago (imagen o PDF)'
    )
    operator_user = models.ForeignKey(
        User,
        verbose_name='Operador',
        on_delete=models.PROTECT,
        related_name='registered_payments',
        help_text='Operador que registró este pago'
    )
    notes = models.TextField(
        verbose_name='Notas',
        blank=True,
        help_text='Additional notes about this payment'
    )
    created_at = models.DateTimeField(
        verbose_name='Creado',
        auto_now_add=True
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
    
    def __str__(self):
        return f"${self.amount} to {self.payment_recipient.alias} on {self.created_at.strftime('%Y-%m-%d')}"
    
    
    def clean(self):
        """Validate payment data"""
        super().clean()
        
        if self.amount <= 0:
            raise ValidationError({'amount': 'Payment amount must be greater than zero.'})
        
        # Validate that recipient can receive this amount
        if self.payment_recipient:
            # When editing existing payment, exclude current payment from capacity calculation
            exclude_payment = self if self.pk else None
            
            if not self.payment_recipient.can_receive_amount(self.amount, exclude_payment=exclude_payment):
                remaining = self.payment_recipient.get_remaining_amount(exclude_payment=exclude_payment)
                if remaining <= 0:
                    raise ValidationError({
                        'payment_recipient': f'Recipient {self.payment_recipient.alias} has already reached their monthly limit.'
                    })
                else:
                    raise ValidationError({
                        'amount': f'Amount exceeds remaining capacity. Maximum available: ${remaining}'
                    })
    
    @classmethod
    def suggest_recipient_for_amount(cls, amount):
        """Suggest the best recipient for a given payment amount"""
        return PaymentRecipient.objects.find_best_recipient(amount)
    
    @classmethod
    def get_monthly_totals(cls, year=None, month=None):
        """Get monthly payment totals"""
        now = timezone.now()
        year = year or now.year
        month = month or now.month
        
        payments = cls.objects.filter(created_at__year=year, created_at__month=month)
        
        return {
            'total_amount': payments.aggregate(total=models.Sum('amount'))['total'] or 0,
            'payment_count': payments.count(),
            'unique_recipients': payments.values('payment_recipient').distinct().count(),
            'unique_operators': payments.values('operator_user').distinct().count(),
        }


class MonthlyBalance(models.Model):
    payment_recipient = models.ForeignKey(
        PaymentRecipient,
        on_delete=models.CASCADE,
        related_name='monthly_balances'
    )
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()  # 1-12
    total_received = models.PositiveIntegerField()
    payment_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['payment_recipient', 'year', 'month']
        ordering = ['-year', '-month']
        verbose_name = 'Balance Mensual'
        verbose_name_plural = 'Balances Mensuales'
    
    def __str__(self):
        return f"{self.payment_recipient.alias} - {self.year}/{self.month:02d}: ${self.total_received}"
    
    @classmethod
    def update_balance(cls, payment):
        """Update monthly balance when a payment is made"""
        balance, created = cls.objects.get_or_create(
            payment_recipient=payment.payment_recipient,
            year=payment.created_at.year,
            month=payment.created_at.month,
            defaults={
                'total_received': 0,
                'payment_count': 0
            }
        )
        
        # Recalculate from all payments for this month
        monthly_payments = Payment.objects.filter(
            payment_recipient=payment.payment_recipient,
            created_at__year=payment.created_at.year,
            created_at__month=payment.created_at.month
        )
        
        balance.total_received = monthly_payments.aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        balance.payment_count = monthly_payments.count()
        balance.save()
        
        return balance
    
    @classmethod
    def reset_monthly_balances(cls, recipients=None):
        """Reset monthly balances for recurring recipients (used for month rollover)"""
        if recipients is None:
            recipients = PaymentRecipient.objects.filter(is_recurring=True, is_active=True)
        
        reset_count = 0
        for recipient in recipients:
            # For recurring recipients, we don't actually delete balances
            # The balance will automatically show current month data
            # This method is more for marking the rollover event
            reset_count += 1
        
        return reset_count
