#!/usr/bin/env python
"""
Script to add banks to the database
Usage: python add_banks_script.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payment_system.settings')
django.setup()

from payment_instructions.models import Bank


def add_banks_from_list(bank_names):
    """Add banks from a list of names"""
    created_count = 0
    skipped_count = 0
    
    for bank_name in bank_names:
        bank_name = bank_name.strip()
        if not bank_name:
            continue
            
        bank, created = Bank.objects.get_or_create(
            name=bank_name,
            defaults={'name': bank_name}
        )
        
        if created:
            created_count += 1
            print(f'✓ Created bank: {bank_name}')
        else:
            skipped_count += 1
            print(f'⚠ Bank already exists: {bank_name}')
    
    print(f'\nSummary: {created_count} banks created, {skipped_count} banks skipped')
    return created_count, skipped_count


def main():
    print("Bank Addition Script")
    print("=" * 50)
    
    # You can modify this list with your bank names
    bank_names = [
        "Banco Nación",
        "Banco Provincia", 
        "Banco Ciudad",
        "Banco Santander",
        "Banco Galicia",
        "Banco Macro",
        "BBVA",
        "Banco Supervielle",
        "Banco Patagonia",
        "Banco Comafi",
        "Banco Industrial",
        "ICBC",
        "Banco Hipotecario",
        "Banco Piano",
        "Banco del Sol",
        "Brubank",
        "Wilobank", 
        "Reba",
        "Mercado Pago",
        "Ualá",
        "Naranja X",
        "Personal Pay",
        "Cuenta DNI",
        "Prex",
        "Lemon",
        "Bimo",
        "Rebanking",
        "Openbank",
    ]
    
    print(f"Ready to add {len(bank_names)} banks:")
    for i, name in enumerate(bank_names, 1):
        print(f"{i:2d}. {name}")
    
    response = input(f"\nProceed with adding these banks? (y/n): ")
    if response.lower() in ['y', 'yes']:
        add_banks_from_list(bank_names)
    else:
        print("Operation cancelled.")


if __name__ == "__main__":
    main()