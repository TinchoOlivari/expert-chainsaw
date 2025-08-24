from ..models import PaymentRecipient


def validate_payment_amount(amount, recipient_alias=None):
    """
    Validate if a payment amount is feasible.
    Returns tuple of (is_valid, message, suggested_recipient)
    """
    try:
        amount = int(str(amount))
    except (ValueError, TypeError):
        return False, "Formato de monto inválido", None
    
    if amount <= 0:
        return False, "El monto debe ser mayor a cero", None
    
    if recipient_alias:
        try:
            recipient = PaymentRecipient.objects.get(alias=recipient_alias, is_active=True)
            if recipient.can_receive_amount(amount):
                return True, "Pago valido", recipient
            else:
                remaining = recipient.get_remaining_amount()
                return False, f"El destinatario solo puede recibir ${remaining:,.2f} mas este mes", recipient
        except PaymentRecipient.DoesNotExist:
            return False, "Destinatario no encontrado o inactivo", None
    
    # Find any suitable recipient
    suggested_recipient = PaymentRecipient.objects.find_best_recipient(amount)
    if suggested_recipient:
        return True, f"Monto valido - destinatario sugerido: {suggested_recipient.alias}", suggested_recipient
    else:
        return False, "No hay destinatarios disponibles para este monto", None
