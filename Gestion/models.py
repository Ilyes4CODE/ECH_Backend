from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User
from decimal import Decimal
import os
from datetime import datetime
import base64
from io import BytesIO
import qrcode

class GlobalCaisse(models.Model):
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Global Caisse: {self.total_amount} DZD"

class CaisseOperation(models.Model):
    OPERATION_TYPES = [
        ('encaissement', 'Encaissement'),
        ('decaissement', 'Décaissement'),
    ]
    
    PAYMENT_MODES = [
        ('virement', 'Virement'),
        ('espece', 'Espèce'),
        ('cheque', 'Chèque'),
    ]
    
    INCOME_SOURCES = [
        ('personnelle', 'Personnelle'),
        ('collaborator', 'Collaborateur'),
        ('dette', 'Dette'),
        ('autre', 'Autre'),
    ]
    
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    description = models.TextField(blank=True)
    preuve_file = models.FileField(upload_to='caisse_preuves/', blank=True, null=True)
    mode_paiement = models.CharField(max_length=20, choices=PAYMENT_MODES, blank=True, null=True)
    
    # For virement
    nom_fournisseur = models.CharField(max_length=200, blank=True, null=True)
    banque = models.CharField(max_length=200, blank=True, null=True)
    # For cheque
    numero_cheque = models.CharField(max_length=100, blank=True, null=True)
    
    # For encaissement
    income_source = models.CharField(max_length=20, choices=INCOME_SOURCES, blank=True, null=True)
    
    observation = models.TextField(blank=True, null=True, help_text="Required when income_source is 'autre'")
    by_collaborator = models.BooleanField(default=False, help_text="Indicates if the operation is by a collaborator")
    
    # Relations
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
    dette = models.ForeignKey('Dette', on_delete=models.SET_NULL, null=True, blank=True)
    
    balance_before = models.DecimalField(max_digits=15, decimal_places=2)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField(help_text="User input date")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.operation_type} - {self.amount} DZD - {self.date}"

class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    estimated_budget = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    contract_file = models.FileField(upload_to='contracts/', blank=True, null=True)
    ods_file = models.FileField(upload_to='ods_files/', blank=True, null=True)
    
    # Project details
    operation = models.CharField(max_length=200, blank=True, null=True)
    numero_operation = models.CharField(max_length=100, blank=True, null=True)
    date_debut = models.DateField()
    period_months = models.PositiveIntegerField(help_text="Duration in months")
    
    # Collaborator (not a User)
    collaborator_name = models.CharField(max_length=200, blank=True, null=True)
    
    # Financial tracking
    total_depenses = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_accreance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_benefices = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    def calculate_benefices(self):
        """Calculate and update benefices (total_accreance - total_depenses)"""
        self.total_benefices = self.total_accreance - self.total_depenses
        return self.total_benefices
    
    def update_benefices(self):
        """Update benefices and save to database"""
        self.calculate_benefices()
        self.save(update_fields=['total_benefices'])
    
    def save(self, *args, **kwargs):
        # Always recalculate benefices before saving
        self.calculate_benefices()
        super().save(*args, **kwargs)

    def get_bon_livraison_history(self):
        return self.bon_livraisons.select_related('created_by', 'pdf_generated_by').order_by('-created_at')

class Dette(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]
    
    creditor_name = models.CharField(max_length=200, help_text="Name of the person/entity you took money from")
    original_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    remaining_amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Optional project relation
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='dettes')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"Dette to {self.creditor_name} - {self.remaining_amount}/{self.original_amount} DZD"

    def save(self, *args, **kwargs):
        if self.remaining_amount <= 0 and self.status == 'active':
            self.status = 'completed'
            self.completed_at = datetime.now()
        super().save(*args, **kwargs)

class DettePayment(models.Model):
    dette = models.ForeignKey(Dette, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)
    preuve_file = models.FileField(upload_to='dette_payments/', blank=True, null=True)
    
    # Payment details
    mode_paiement = models.CharField(max_length=20, choices=CaisseOperation.PAYMENT_MODES)
    nom_fournisseur = models.CharField(max_length=200, blank=True, null=True)
    banque = models.CharField(max_length=200, blank=True, null=True)
    numero_cheque = models.CharField(max_length=100, blank=True, null=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    caisse_operation = models.ForeignKey(CaisseOperation, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment {self.amount_paid} DZD for {self.dette.creditor_name} on {self.payment_date.strftime('%d/%m/%Y')}"

class CaisseHistory(models.Model):
    ACTION_CHOICES = [
        ('encaissement', 'Encaissement'),
        ('decaissement', 'Décaissement'),
        ('balance_adjustment', 'Balance Adjustment'),
    ]
    
    numero = models.CharField(max_length=10, unique=True, editable=False)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    balance_before = models.DecimalField(max_digits=15, decimal_places=2)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    operation = models.ForeignKey(CaisseOperation, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    date = models.DateField(help_text="User input date")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.numero:
            last_history = CaisseHistory.objects.order_by('-numero').first()
            if last_history and last_history.numero.startswith('ECH'):
                try:
                    last_number = int(last_history.numero[3:])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1
            else:
                new_number = 1
            self.numero = f"ECH{new_number:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero} - {self.action} - {self.amount} DZD on {self.date}"

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

def bon_livraison_pdf_path(instance, filename):
    return f'bon_livraison_pdfs/{instance.project.id}/{instance.bl_number}.pdf'

class BonDeLivraison(models.Model):
    PAYMENT_MODES = [
        ('virement', 'Virement'),
        ('espece', 'Espèce'),
        ('cheque', 'Chèque'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='bon_livraisons')
    bl_number = models.CharField(max_length=50, unique=True, blank=True)
    origin_address = models.TextField()
    destination_address = models.TextField()
    description = models.TextField(blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_MODES)
    payment_proof = models.ImageField(upload_to='payment_proofs/', blank=True, null=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    #pour virement
    nom_fournisseur = models.CharField(max_length=200, blank=True, null=True)
    banque = models.CharField(max_length=200, blank=True, null=True)
    #pour cheque
    numero_cheque = models.CharField(max_length=100, blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_bon_livraisons')
    pdf_generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_pdfs')
    
    pdf_file = models.FileField(upload_to=bon_livraison_pdf_path, blank=True, null=True)
    pdf_generated_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bon de Livraison {self.bl_number} - {self.project.name}"

    def generate_bl_number(self):
        if not self.bl_number:
            year = datetime.now().year
            project_id = str(self.project.id).zfill(3)
            
            existing_count = BonDeLivraison.objects.filter(
                project=self.project,
                created_at__year=year
            ).count()
            
            sequence = str(existing_count + 1).zfill(3)
            self.bl_number = f"BL-{year}-{project_id}-{sequence}"

    def calculate_total(self):
        products_total = sum([item.total_price for item in self.items.all()])
        charges_total = sum([charge.amount for charge in self.additional_charges.all()])
        return products_total + charges_total

    def save(self, *args, **kwargs):
        if not self.bl_number:
            self.generate_bl_number()
        
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if not is_new:
            new_total = self.calculate_total()
            if new_total != self.total_amount:
                self.total_amount = new_total
                super().save(update_fields=['total_amount'])

    def get_pdf_filename(self):
        return f"{self.bl_number}.pdf"

    def has_pdf(self):
        return bool(self.pdf_file and os.path.exists(self.pdf_file.path))

class BonDeLivraisonItem(models.Model):
    bon_de_livraison = models.ForeignKey(BonDeLivraison, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], blank=True, null=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.unit_price and self.quantity and not self.total_price:
            self.total_price = self.quantity * self.unit_price
        
        elif self.total_price and self.quantity and not self.unit_price:
            self.unit_price = self.total_price / self.quantity
        
        if not self.total_price:
            self.total_price = Decimal('0.00')
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} x {self.unit_price or 0}"

class AdditionalCharge(models.Model):
    bon_de_livraison = models.ForeignKey(BonDeLivraison, on_delete=models.CASCADE, related_name='additional_charges')
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description}: {self.amount} DZD"

class BonLivraisonHistory(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('pdf_generated', 'PDF Generated'),
        ('pdf_downloaded', 'PDF Downloaded'),
        ('deleted', 'Deleted'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='bl_history')
    bon_de_livraison = models.ForeignKey(BonDeLivraison, on_delete=models.SET_NULL, null=True, blank=True)
    bl_number = models.CharField(max_length=50)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.bl_number} - {self.action} by {self.user.username if self.user else 'Unknown'}"

class OrdreDeMission(models.Model):
    numero = models.CharField(max_length=20, unique=True, editable=False)
    nom_prenom = models.CharField(max_length=100)
    fonction = models.CharField(max_length=50)
    adresse = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    motif = models.CharField(max_length=50)
    moyen_deplacement = models.CharField(max_length=100)
    matricule = models.CharField(max_length=50)
    matricule_2 = models.CharField(max_length=50, blank=True, null=True)
    date_depart = models.DateField()
    date_retour = models.DateField(blank=True, null=True)
    accompagne_par = models.CharField(max_length=100, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, default='System')
    
    class Meta:
        ordering = ['-date_creation']
        
    def save(self, *args, **kwargs):
        if not self.numero:
            current_year = datetime.now().year
            last_mission = OrdreDeMission.objects.filter(
                numero__endswith=f'/{current_year}'
            ).order_by('-numero').first()
            
            if last_mission:
                last_number = int(last_mission.numero.split('/')[0])
                new_number = last_number + 1
            else:
                new_number = 1
                
            self.numero = f'{new_number:03d}/{current_year}'
        super().save(*args, **kwargs)
    
    def get_date_retour_display(self):
        if self.date_retour:
            return self.date_retour.strftime('%d/%m/%Y')
        return 'FIN DE MISSION'
    
    def generate_qr_code(self):
        qr_data = f"""MISSION DETAILS
                      Number: {self.numero}
                      Name: {self.nom_prenom}
                      Departure: {self.date_depart.strftime('%d/%m/%Y')}
                      Return: {self.get_date_retour_display()}
                      Destination: {self.destination}
                      Cree par: {self.created_by}
                      Motif: {self.motif} """
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"
    
    def __str__(self):
        return f"{self.numero} - {self.nom_prenom}"
    
def bon_commande_pdf_path(instance, filename):
    return f'bon_de_commande/{instance.bc_number}.pdf'

class BonDeCommande(models.Model):
    bc_number = models.CharField(max_length=50, unique=True, blank=True)
    date_commande = models.DateField(auto_now_add=True)
    description = models.TextField(blank=True)
    total_ht = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    doit = models.CharField(max_length=200, blank=True) 
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_bon_commandes')
    pdf_generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_bc_pdfs')
    pdf_file = models.FileField(upload_to=bon_commande_pdf_path, blank=True, null=True)
    pdf_generated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Bon de Commande {self.bc_number}"

    def generate_bc_number(self):
        if not self.bc_number:
            year = datetime.now().year
            existing_count = BonDeCommande.objects.filter(
                created_at__year=year
            ).count()
            sequence = str(existing_count + 1).zfill(3)
            self.bc_number = f"BC-{year}-{sequence}"

    def calculate_total_ht(self):
        return sum([item.montant_ht for item in self.items.all()])

    def save(self, *args, **kwargs):
        if not self.bc_number:
            self.generate_bc_number()
        
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if not is_new:
            new_total = self.calculate_total_ht()
            if new_total != self.total_ht:
                self.total_ht = new_total
                super().save(update_fields=['total_ht'])

    def get_pdf_filename(self):
        return f"{self.bc_number}.pdf"

    def has_pdf(self):
        return bool(self.pdf_file and os.path.exists(self.pdf_file.path))

    def generate_qr_code(self):
        qr_data = f"""BON DE COMMANDE
Number: {self.bc_number}
Date: {self.date_commande.strftime('%d/%m/%Y')}
Total HT: {self.total_ht} DZD
Created by: {self.created_by.username if self.created_by else 'Unknown'}
Items: {self.items.count()}"""
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"

class BonDeCommandeItem(models.Model):
    bon_de_commande = models.ForeignKey(BonDeCommande, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    designation = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    montant_ht = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.quantity and self.prix_unitaire:
            self.montant_ht = self.quantity * self.prix_unitaire
        else:
            self.montant_ht = Decimal('0.00')
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.designation} - {self.quantity} x {self.prix_unitaire}"

def revenu_pdf_path(instance, filename):
    return f'revenu_pdfs/{instance.project.id}/{instance.revenu_code}.pdf'

class Revenu(models.Model):
    revenu_code = models.CharField(max_length=50, unique=True)  # Remove blank=True to make it required
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='revenus')
    montant = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    date = models.DateField()
    pdf_file = models.FileField(upload_to=revenu_pdf_path, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_revenus')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Revenu {self.revenu_code} - {self.montant} DZD - {self.project.name}"

    def save(self, *args, **kwargs):
        # Don't auto-generate revenu_code anymore since user will provide it
        
        # Only update project totals when creating new revenu
        if not self.pk:
            # Add to project's total_accreance
            self.project.total_accreance += self.montant
            # Subtract from estimated_budget (if you still want this behavior)
            if self.project.estimated_budget >= self.montant:
                self.project.estimated_budget -= self.montant
            # Calculate benefices (total_accreance - total_depenses)
            self.project.total_benefices = self.project.total_accreance - self.project.total_depenses
            self.project.save(update_fields=['total_accreance', 'estimated_budget', 'total_benefices'])
        
        super().save(*args, **kwargs)