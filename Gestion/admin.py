from django.contrib import admin
from .models import (
    GlobalCaisse, CaisseOperation, Project, Dette, DettePayment,
    CaisseHistory, Product, BonDeLivraison, BonDeLivraisonItem, AdditionalCharge,
    BonLivraisonHistory, OrdreDeMission, BonDeCommande, BonDeCommandeItem
)

@admin.register(GlobalCaisse)
class GlobalCaisseAdmin(admin.ModelAdmin):
    list_display = ('total_amount', 'created_at', 'updated_at')
    ordering = ('-created_at',)

@admin.register(CaisseOperation)
class CaisseOperationAdmin(admin.ModelAdmin):
    list_display = ('operation_type', 'amount', 'project', 'mode_paiement', 'balance_before', 'balance_after', 'created_at')
    search_fields = ('description',)
    list_filter = ('operation_type', 'mode_paiement', 'created_at')
    ordering = ('-created_at',)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'estimated_budget', 'total_depenses', 'total_benefices', 'created_by', 'created_at')
    search_fields = ('name', 'description', 'operation', 'numero_operation')
    list_filter = ('created_at',)
    ordering = ('-created_at',)


@admin.register(Dette)
class DetteAdmin(admin.ModelAdmin):
    list_display = ('creditor_name', 'original_amount', 'remaining_amount', 'status', 'project', 'created_by', 'date_created')
    list_filter = ('status', 'date_created')
    search_fields = ('creditor_name', 'description')
    ordering = ('-date_created',)

@admin.register(DettePayment)
class DettePaymentAdmin(admin.ModelAdmin):
    list_display = ('dette', 'amount_paid', 'mode_paiement', 'payment_date', 'created_by')
    list_filter = ('mode_paiement', 'payment_date')
    ordering = ('-payment_date',)

@admin.register(CaisseHistory)
class CaisseHistoryAdmin(admin.ModelAdmin):
    list_display = ('action', 'amount', 'balance_before', 'balance_after', 'user', 'created_at')
    list_filter = ('action', 'created_at')
    ordering = ('-created_at',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    ordering = ('-created_at',)

@admin.register(BonDeLivraison)
class BonDeLivraisonAdmin(admin.ModelAdmin):
    list_display = ('bl_number', 'project', 'payment_method', 'total_amount', 'created_by', 'created_at')
    list_filter = ('payment_method', 'created_at')
    search_fields = ('bl_number', 'description')
    ordering = ('-created_at',)

@admin.register(BonDeLivraisonItem)
class BonDeLivraisonItemAdmin(admin.ModelAdmin):
    list_display = ('bon_de_livraison', 'product', 'quantity', 'unit_price', 'total_price')
    ordering = ('-id',)

@admin.register(AdditionalCharge)
class AdditionalChargeAdmin(admin.ModelAdmin):
    list_display = ('bon_de_livraison', 'description', 'amount', 'created_at')
    ordering = ('-created_at',)

@admin.register(BonLivraisonHistory)
class BonLivraisonHistoryAdmin(admin.ModelAdmin):
    list_display = ('bl_number', 'action', 'user', 'created_at')
    list_filter = ('action', 'created_at')
    ordering = ('-created_at',)

@admin.register(OrdreDeMission)
class OrdreDeMissionAdmin(admin.ModelAdmin):
    list_display = ('numero', 'nom_prenom', 'destination', 'date_depart', 'date_retour', 'created_by', 'date_creation')
    search_fields = ('numero', 'nom_prenom', 'destination')
    list_filter = ('date_creation',)
    ordering = ('-date_creation',)

@admin.register(BonDeCommande)
class BonDeCommandeAdmin(admin.ModelAdmin):
    list_display = ('bc_number', 'total_ht', 'created_by', 'date_commande', 'created_at')
    search_fields = ('bc_number', 'description')
    ordering = ('-created_at',)

@admin.register(BonDeCommandeItem)
class BonDeCommandeItemAdmin(admin.ModelAdmin):
    list_display = ('bon_de_commande', 'product', 'designation', 'quantity', 'prix_unitaire', 'montant_ht')
    ordering = ('-id',)
