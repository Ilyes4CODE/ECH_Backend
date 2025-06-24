from django.urls import path
from . import views

urlpatterns = [
    # Global Caisse URLs
    path('api/global-caisse/', views.global_caisse_get, name='global_caisse_get'),
    path('api/global-caisse/update/', views.global_caisse_update, name='global_caisse_update'),
    
    # Project URLs
    path('api/projects/', views.project_list, name='project_list'),
    path('api/projects/create/', views.project_create, name='project_create'),
    path('api/projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('api/projects/<int:pk>/update/', views.project_update, name='project_update'),
    path('api/projects/<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('api/projects/<int:pk>/bl-history/', views.project_bl_history, name='project_bl_history'),
    
    # Product URLs
    path('api/products/', views.product_list, name='product_list'),
    path('api/products/create/', views.product_create, name='product_create'),
    
    # Bon de Livraison URLs
    path('api/bon-de-livraison/', views.bon_de_livraison_list, name='bon_de_livraison_list'),
    path('api/bon-de-livraison/create/', views.bon_de_livraison_create, name='bon_de_livraison_create'),
    path('api/bon-de-livraison/<int:pk>/', views.bon_de_livraison_detail, name='bon_de_livraison_detail'),
    path('api/bon-de-livraison/<int:pk>/delete/', views.bon_de_livraison_delete, name='bon_de_livraison_delete'),
    
    # PDF Generation URLs
    path('api/bon-de-livraison/<int:pk>/generate-pdf/', views.generate_bl_pdf, name='generate_bl_pdf'),
    path('api/bon-de-livraison/<int:pk>/download-pdf/', views.download_bl_pdf, name='download_bl_pdf'),
]
