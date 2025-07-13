from django.urls import path
from . import views

urlpatterns = [
    # Global Caisse URLs
    path('api/global-caisse/', views.global_caisse_get, name='global_caisse_get'),
    path('api/global-caisse/update/', views.global_caisse_update, name='global_caisse_update'),
    path('api/global-caisse/history/', views.caisse_history, name='caisse_history'),
    path('api/global-caisse/generate-pdf/', views.generate_caisse_pdf, name='generate_caisse_pdf'),
    path('api/global-caisse/transfer-to-project/', views.transfer_to_project, name='transfer_to_project'),
    path('api/global-caisse/transfer-from-project/', views.transfer_from_project, name='transfer_from_project'),
    
    # Project URLs
    path('api/projects/', views.project_list, name='project_list'),
    path('api/projects/create/', views.project_create, name='project_create'),
    path('api/projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('api/projects/<int:pk>/update/', views.project_update, name='project_update'),
    path('api/projects/<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('api/projects/<int:pk>/benefits/', views.project_benefits),
    # path('api/projects/<int:pk>/bl-history/', views.bl_history, name='project_bl_history'),
    path('api/projects/<int:pk>/caisse-history/', views.project_caisse_history, name='project_caisse_history'),
    path('api/projects/<int:pk>/caisse-history-collaborator/', views.project_caisse_history_collaborator, name='project_caisse_history'),
    path('api/projects/<int:pk>/caisse-operation/', views.project_caisse_operation, name='project_caisse_operation'),
    path('api/projects/<int:pk>/generate-project-caisse-pdf/', views.project_caisse_history_pdf, name='generate_project_caisse_pdf'),
    path('api/projects/<int:pk>/generate-project-caisse-colab-pdf/', views.project_caisse_history_collaborator_pdf, name='generate_project_caisse_pdf'),

    # Product URLs
    path('api/products/', views.product_list, name='product_list'),
    path('api/products/create/', views.product_create, name='product_create'),
    path('api/products/<int:pk>/', views.product_detail, name='product_detail'),
    path('api/products/<int:pk>/update/', views.product_update, name='product_update'),
    path('api/products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    
    # Bon de Livraison URLs
    path('api/bon-de-livraison/', views.bon_de_livraison_list, name='bon_de_livraison_list'),
    path('api/bon-de-livraison/create/', views.bon_de_livraison_create, name='bon_de_livraison_create'),
    path('api/bon-de-livraison/<int:pk>/', views.bon_de_livraison_detail, name='bon_de_livraison_detail'),
    path('api/bon-de-livraison/bl-history/', views.bl_history, name='project_bl_history'),
    path('api/bon-de-livraison/<int:pk>/update/', views.bon_de_livraison_update, name='bon_de_livraison_update'),
    path('api/bon-de-livraison/<int:pk>/delete/', views.bon_de_livraison_delete, name='bon_de_livraison_delete'),
    path('api/bon-de-livraison/<int:pk>/add-item/', views.bon_de_livraison_add_item, name='bon_de_livraison_add_item'),
    path('api/bon-de-livraison/<int:pk>/add-charge/', views.bon_de_livraison_add_charge, name='bon_de_livraison_add_charge'),
    
    # PDF Generation URLs
    path('api/bon-de-livraison/<int:pk>/generate-pdf/', views.generate_bl_pdf, name='generate_bl_pdf'),
    path('api/bon-de-livraison/<int:pk>/download-pdf/', views.download_bl_pdf, name='download_bl_pdf'),

    # Ordre de Mission URLs
    path('api/ordre-mission/create/', views.create_ordre_mission, name='create_ordre_mission'),
    path('api/ordre-mission/delete/<int:mission_id>/', views.delete_ordre_mission, name='delete_ordre_mission'),
    path('api/ordre-mission/pdf/<int:mission_id>/', views.generate_pdf_ordre_mission, name='generate_pdf_ordre_mission'),
    path('api/ordre-mission/list/', views.list_ordre_missions, name='list_ordre_missions'),
    path('api/ordre-mission/detail/<int:mission_id>/', views.get_ordre_mission_detail, name='get_ordre_mission_detail'),
    # Bon de Commande URLs
    path('api/bon-de-commande/', views.list_bon_commandes, name='list_bon_commandes'),
    path('api/bon-de-commande/create/', views.create_bon_commande, name='create_bon_commande'),
    path('api/bon-de-commande/<int:bc_id>/', views.bon_commande_detail, name='get_bon_commande_detail'),
    path('api/delete-bon-de-commande/<int:bc_id>/', views.delete_bon_commande, name='delete_bon_commande'),
    path('api/bon-de-commande/<int:bc_id>/generate-pdf/', views.generate_bon_commande_pdf, name='update_bon_commande'),
    path('api/bon-de-commande/<int:bc_id>/download-pdf/', views.download_bon_commande_pdf, name='add_item_to_bon_commande'),

    #useful URLs
    path('projects/<int:project_id>/has-collaborator/', views.has_collaborator, name='has-collaborator'),


]