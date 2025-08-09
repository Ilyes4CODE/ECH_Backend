from django.urls import path
from . import views

urlpatterns = [
    path('caisse/status/', views.global_caisse_status, name='caisse_status'),
    path('caisse/encaissement/', views.caisse_encaissement, name='caisse_encaissement'),
    path('caisse/decaissement/', views.caisse_decaissement, name='caisse_decaissement'),
    path('caisse/operations/', views.caisse_operations_history, name='caisse_operations'),
    path('caisse/operations/history/pdf/', views.generate_caisse_history_pdf, name='generate_caisse_history_pdf'),
    path('caisse/history/', views.caisse_history, name='caisse_history'),
    path('caisse/operation/<int:history_id>/pdf/', views.generate_operation_pdf, name='generate_operation_pdf'),

    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.create_project, name='create_project'),
    path('projects/<int:project_id>/pdf/', views.generate_project_pdf, name='generate_project_pdf'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<int:project_id>/update/', views.update_project, name='update_project'),
    path('projects/project-finance-pdf/', views.generate_project_finance_pdf, name='generate_project_finance_pdf'),
    
    path('dettes/', views.dette_list, name='dette_list'),
    path('dettes/create/', views.create_dette, name='create_dette'),
    path('dettes/<int:dette_id>/', views.dette_detail, name='dette_detail'),
    path('dettes/<int:dette_id>/journal/pdf/', views.generate_dette_journal_pdf, name='dette_journal_pdf'),
    path('dettes/<int:dette_id>/payment/', views.dette_payment, name='dette_payment'),
    
    path('bon-livraison/', views.bon_livraison_list, name='bon_livraison_list'),
    path('bon-livraison/create/', views.create_bon_livraison, name='create_bon_livraison'),
    
    path('bon-commande/', views.bon_commande_list, name='bon_commande_list'),
    path('bon-commande/create/', views.create_bon_commande, name='create_bon_commande'),
    
    path('ordre-mission/', views.ordre_mission_list, name='ordre_mission_list'),
    path('ordre-mission/create/', views.create_ordre_mission, name='create_ordre_mission'),
    
    path('dashboard/', views.dashboard_stats, name='dashboard_stats'),

    path('api/revenus/create/', views.create_revenu, name='create_revenu'),
    path('api/revenus/project/<int:project_id>/', views.get_revenus_by_project, name='get_revenus_by_project'),
    path('api/revenus/<int:revenu_id>/', views.get_revenu_detail, name='get_revenu_detail'),
    path('api/revenus/<int:revenu_id>/delete/', views.delete_revenu, name='delete_revenu'),
]