from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from .models import User, PaymentRecipient, Payment, MonthlyBalance


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Administrators can see all users, operators can only see themselves
        if hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR:
            return qs
        return qs.filter(pk=request.user.pk)
    
    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR
        # Users can edit themselves, administrators can edit others
        return obj == request.user or (hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR)
    
    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR


@admin.register(PaymentRecipient)
class PaymentRecipientAdmin(admin.ModelAdmin):
    list_display = (
        'alias', 'max_amount_display', 'current_month_received', 'priority_order', 'is_recurring', 'is_active'
    )
    list_filter = ('is_recurring', 'is_active', 'created_at')
    search_fields = ('name', 'alias', 'cbu')
    ordering = ('priority_order', 'name')
    readonly_fields = ('created_at', 'updated_at', 'current_month_received', 'remaining_amount')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'alias', 'cbu', 'bank')
        }),
        ('Payment Configuration', {
            'fields': ('max_amount', 'priority_order', 'is_recurring', 'is_active')
        }),
        ('Current Status', {
            'fields': ('current_month_received', 'remaining_amount'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_recipients', 'deactivate_recipients']

    def max_amount_display(self, obj):
        return f"${obj.max_amount}"
    max_amount_display.short_description = 'Salario'


    def current_month_received(self, obj):
        amount = obj.get_current_month_received()
        return f"${amount}"
    current_month_received.short_description = 'Recibido'
    
    def remaining_amount(self, obj):
        remaining = obj.get_remaining_amount()
        return f"${remaining}"
    remaining_amount.short_description = 'Restante'
    
    def activate_recipients(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} recipients.")
    activate_recipients.short_description = "Activar seleccionados"
    
    def deactivate_recipients(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} recipients.")
    deactivate_recipients.short_description = "Desactivar seleccionados"
    
    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR
    
    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'amount_display', 'payment_recipient', 'operator_user', 
        'has_proof', 'created_at'
    )
    list_filter = ('created_at', 'payment_recipient', 'operator_user', 'created_at')
    search_fields = ('payment_recipient__name', 'payment_recipient__alias', 'operator_user__username', 'notes')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('amount', 'payment_recipient','operator_user','created_at',)
        }),
        ('Documentation', {
            'fields': ('proof_of_payment_file', 'notes')
        }),
    )

    def amount_display(self, obj):
        return f"${obj.amount}"
    amount_display.short_description = 'Monto'
    
    def has_proof(self, obj):
        if obj.proof_of_payment_file:
            return format_html(
                '<a href="{}" target="_blank">View File</a>',
                obj.proof_of_payment_file.url
            )
        return "No file"
    has_proof.short_description = 'Proof of Payment'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new payment
            obj.operator_user = request.user
        
        # Validate business rules before saving
        try:
            obj.clean()
        except ValidationError as e:
            from django.contrib import messages
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return
        
        super().save_model(request, obj, form, change)
        # Update monthly balance
        MonthlyBalance.update_balance(obj)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Filter recipients to show only active ones with available capacity
        if 'payment_recipient' in form.base_fields:
            form.base_fields['payment_recipient'].queryset = PaymentRecipient.objects.filter(
                is_active=True
            ).order_by('priority_order', 'name')
        
        # Set operator_user to current user for new payments
        if 'operator_user' in form.base_fields and not obj:
            form.base_fields['operator_user'].initial = request.user
            if hasattr(request.user, 'role') and request.user.role == User.OPERATOR:
                form.base_fields['operator_user'].widget.attrs['readonly'] = True
        
        return form
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Administrators see all payments, operators see only their own
        if hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR:
            return qs
        return qs.filter(operator_user=request.user)
    
    def has_add_permission(self, request):
        # Both administrators and operators can add payments
        return True
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        # Administrators can edit all, operators can edit only their own
        if hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR:
            return True
        return obj.operator_user == request.user
    
    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR


@admin.register(MonthlyBalance)
class MonthlyBalanceAdmin(admin.ModelAdmin):
    list_display = (
        'payment_recipient', 'year', 'month', 'total_received', 
        'payment_count', 'last_updated'
    )
    list_filter = ('year', 'month', 'payment_recipient')
    search_fields = ('payment_recipient__name', 'payment_recipient__alias')
    ordering = ('-year', '-month', 'payment_recipient__name')
    readonly_fields = ('total_received', 'payment_count', 'last_updated')
    
    def has_add_permission(self, request):
        # Monthly balances are auto-generated
        return False
    
    def has_change_permission(self, request, obj=None):
        # Monthly balances are auto-updated
        return False
    
    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'role') and request.user.role == User.ADMINISTRATOR


# Customize admin site headers
admin.site.site_header = "Docta Dent - Clinica dental"
admin.site.site_title = "Sistema de Instrucciones de pago"
