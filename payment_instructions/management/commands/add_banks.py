from django.core.management.base import BaseCommand
from payment_instructions.models import Bank


class Command(BaseCommand):
    help = 'Add multiple banks from a predefined list'

    def add_arguments(self, parser):
        parser.add_argument(
            '--banks',
            nargs='+',
            help='List of bank names to add (space separated)',
        )
        parser.add_argument(
            '--file',
            type=str,
            help='File path containing bank names (one per line)',
        )

    def handle(self, *args, **options):
        bank_names = []
        
        # Get banks from command line arguments
        if options['banks']:
            bank_names.extend(options['banks'])
        
        # Get banks from file
        if options['file']:
            try:
                with open(options['file'], 'r', encoding='utf-8') as f:
                    file_banks = [line.strip() for line in f.readlines() if line.strip()]
                    bank_names.extend(file_banks)
            except FileNotFoundError:
                self.stdout.write(
                    self.style.ERROR(f'File not found: {options["file"]}')
                )
                return
        
        # Default banks list if no arguments provided
        if not bank_names:
            bank_names = [
                "Banco Ciudad",
                "Banco Comafi",
                "Banco Credicoop",
                "Banco De San Juan",
                "Banco De Santa Cruz ",
                "Banco Del Sol",
                "Banco Entre Ríos",
                "Banco Galicia",
                "Banco Hipotecario ",
                "Banco Patagonia ",
                "Banco Piano ",
                "Banco Santa Fe",
                "Banco Santander",
                "Banco Supervielle",
                "Banco de Cordoba (Bancor)",
                "Banco BBVA ",
                "Bica Modo",
                "Billetera Macro",
                "Billetera Ultra",
                "Bind Psp",
                "Blp",
                "Bna",
                "Brubank",
                "Buepp",
                "Claro Pay",
                "Click+",
                "Codigopago",
                "Credencial Payments",
                "Cuenta Dni",
                "Data 3.0",
                "Lemon",
                "Digipayments",
                "Easy Pagos",
                "Epagos",
                "Facaf",
                "Fertil Suma",
                "Finket",
                "Garpa",
                "Go Pay",
                "Hooli",
                "HSBC",
                "ICBC",
                "Koipay",
                "Lux 11",
                "Másbanco",
                "Mercado Pago",
                "Mi Bpn",
                "Modo",
                "Moni Online Sa",
                "N1u Level",
                "Naranja X",
                "Nbch24 Billetera",
                "Onda Siempre",
                "Pago24",
                "Paycloud",
                "Personal Pay",
                "Plus Pagos",
                "Prex",
                "Propago",
                "Pvs",
                "Reba",
                "Resimple",
                "Sidom Pay",
                "Sys",
                "Tach",
                "Tarjeta Urbana",
                "Tdk Labs",
                "Telepagos",
                "Totalcoin",
                "Ualá",
                "Unex",
                "Viapago",
                "Viumi",
                "+Simple",
            ]
        
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
                self.stdout.write(
                    self.style.SUCCESS(f'Created bank: {bank_name}')
                )
            else:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Bank already exists: {bank_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {created_count} banks created, {skipped_count} banks skipped'
            )
        )