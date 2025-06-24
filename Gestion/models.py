from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User
from decimal import Decimal
import os
from datetime import datetime

class GlobalCaisse(models.Model):
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Global Caisse: {self.total_amount}"

class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    contract_file = models.FileField(upload_to='contracts/', blank=True, null=True)
    estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    duration_days = models.PositiveIntegerField()
    actual_spent = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_bon_livraison_history(self):
        """Get all bon de livraison for this project with user info"""
        return self.bon_livraisons.select_related('created_by', 'pdf_generated_by').order_by('-created_at')

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

def bon_livraison_pdf_path(instance, filename):
    """Generate path for PDF files"""
    return f'bon_livraison_pdfs/{instance.project.id}/{instance.bl_number}.pdf'

class BonDeLivraison(models.Model):
    PAYMENT_METHODS = [
        ('bank_cheque', 'Bank - Chèque'),
        ('bank_virement', 'Bank - Ordre de Virement'),
        ('poste_baridi', 'Poste - Baridi Mob'),
        ('poste_ccp', 'Poste - CCP'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='bon_livraisons')
    bl_number = models.CharField(max_length=50, unique=True, blank=True)  # Auto-generated BL number
    origin_address = models.TextField()
    destination_address = models.TextField()
    description = models.TextField(blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_proof = models.ImageField(upload_to='payment_proofs/', blank=True, null=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # User tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_bon_livraisons')
    pdf_generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_pdfs')
    
    # PDF management
    pdf_file = models.FileField(upload_to=bon_livraison_pdf_path, blank=True, null=True)
    pdf_generated_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bon de Livraison {self.bl_number} - {self.project.name}"

    def generate_bl_number(self):
        """Generate unique BL number with format: BL-YYYY-PROJECT_ID-XXX"""
        if not self.bl_number:
            year = datetime.now().year
            project_id = str(self.project.id).zfill(3)
            
            # Count existing BLs for this project in current year
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
        
        # Update total amount after saving items
        if not is_new:
            new_total = self.calculate_total()
            if new_total != self.total_amount:
                self.total_amount = new_total
                super().save(update_fields=['total_amount'])

    def get_pdf_filename(self):
        """Get the PDF filename"""
        return f"{self.bl_number}.pdf"

    def has_pdf(self):
        """Check if PDF exists"""
        return bool(self.pdf_file and os.path.exists(self.pdf_file.path))

class BonDeLivraisonItem(models.Model):
    bon_de_livraison = models.ForeignKey(BonDeLivraison, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], blank=True, null=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Calculate total price if both unit_price and quantity are provided
        if self.unit_price and self.quantity and not self.total_price:
            self.total_price = self.quantity * self.unit_price
        
        # If total_price is provided but unit_price is not, calculate unit_price
        elif self.total_price and self.quantity and not self.unit_price:
            self.unit_price = self.total_price / self.quantity
        
        # Default total_price to 0 if not provided
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
    """Track history of actions on Bon de Livraison"""
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('pdf_generated', 'PDF Generated'),
        ('pdf_downloaded', 'PDF Downloaded'),
        ('deleted', 'Deleted'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='bl_history')
    bon_de_livraison = models.ForeignKey(BonDeLivraison, on_delete=models.SET_NULL, null=True, blank=True)
    bl_number = models.CharField(max_length=50)  # Store BL number even if BL is deleted
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.bl_number} - {self.action} by {self.user.username if self.user else 'Unknown'}"