from django.contrib import admin
from .models import (
    GlobalCaisse,
    Project,
    Product,
    BonDeLivraison,
    BonDeLivraisonItem,
    AdditionalCharge,
    BonLivraisonHistory
)

# Simple default registrations
admin.site.register(GlobalCaisse)
admin.site.register(Project)
admin.site.register(Product)
admin.site.register(BonDeLivraison)
admin.site.register(BonDeLivraisonItem)
admin.site.register(AdditionalCharge)
admin.site.register(BonLivraisonHistory)
