from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

from payment_instructions.utils.file_compression import FileCompressor
from .utils.utils import validate_payment_amount
from .models import Payment, PaymentRecipient


def operator_login(request):
    """Login view for operators"""
    if request.user.is_authenticated:
        return redirect('payment_instructions:operator_dashboard')
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('payment_instructions:operator_dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'payment_instructions/login.html')


def operator_logout(request):
    """Logout view"""
    logout(request)
    return redirect('payment_instructions:operator_login')


@login_required
def operator_dashboard(request):
    """Main operator dashboard"""
    return render(request, 'payment_instructions/dashboard.html')


@login_required
@require_http_methods(["POST"])
def search_alias(request):
    """AJAX endpoint to search for alias given an amount"""
    try:
        data = json.loads(request.body)
        amount = data.get('amount')
        
        if not amount:
            return JsonResponse({'error': 'Monto requerido'}, status=400)
        
        # Validate and get suggested recipient
        is_valid, message, recipient = validate_payment_amount(amount)
        
        if not is_valid:
            return JsonResponse({'error': message}, status=400)
        
        if recipient:
            return JsonResponse({
                'success': True,
                'alias': recipient.alias,
                'name': recipient.name,
                'amount': str(amount)
            })
        else:
            return JsonResponse({'error': 'No hay destinatarios disponibles para este monto'}, status=400)
            
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        return JsonResponse({'error': 'Formato de monto inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Error interno del servidor'}, status=500)


@login_required
@require_http_methods(["POST"])
def create_payment(request):
    """Create a new payment"""
    try:
        amount = request.POST.get('amount')
        alias = request.POST.get('alias')
        file_obj = request.FILES.get('proof_of_payment_file') 
        
        if not amount or not alias:
            return JsonResponse({'error': 'Monto y alias son requeridos'}, status=400)

        if not file_obj:
            return JsonResponse({'error': 'El comprobante es requerido.'}, status=400)
        
        # Get recipient
        try:
            recipient = PaymentRecipient.objects.get(alias=alias, is_active=True)
        except PaymentRecipient.DoesNotExist:
            return JsonResponse({'error': 'Destinatario no encontrado'}, status=400)
        
        # Validate amount
        amount_decimal = int(str(amount))
        if not recipient.can_receive_amount(amount_decimal):
            return JsonResponse({'error': 'El destinatario no puede recibir este monto'}, status=400)
        
        # Validate and compress file
        # 5MB maximum
        max_bytes = 5 * 1024 * 1024
        if file_obj.size > max_bytes:
            return JsonResponse({'error': 'El archivo es demasiado grande. Máximo 5MB.'}, status=400)

        allowed_types = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'application/pdf'
        }

        if file_obj.content_type not in allowed_types:
            return JsonResponse({'error': 'Tipo de archivo no válido. Solo imágenes o PDF.'}, status=400)
        
        # Compress the file
        compressed_file = FileCompressor.compress_file(file_obj)
        
        # Create payment with compressed file
        payment = Payment.objects.create(
            amount=amount_decimal,
            payment_recipient=recipient,
            operator_user=request.user,
            proof_of_payment_file=compressed_file  # Use compressed file
        )
        
        return JsonResponse({
            'success': True,
            'payment_id': payment.id,
            'message': f'Pago creado exitosamente. (id: {payment.id})'
        })
        
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        return JsonResponse({'error': f'No se pudo registrar el pago. Error: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error interno del servidor: {str(e)}'}, status=500)