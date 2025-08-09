from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal
from .models import (
    GlobalCaisse, CaisseOperation, Project,
    Dette, DettePayment, CaisseHistory, BonDeLivraison,
    BonDeCommande, OrdreDeMission, Product,Revenu
)
import io
from django.template.loader import get_template
from django.utils import timezone
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from PIL import Image
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.dateparse import parse_datetime, parse_date
from django.contrib.auth.models import User
def get_or_create_global_caisse():
    """Get the global caisse or create it if it doesn't exist"""
    caisse = GlobalCaisse.objects.first()
    if not caisse:
        caisse = GlobalCaisse.objects.create(total_amount=Decimal('0.00'))
    return caisse

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def global_caisse_status(request):
    caisse = get_or_create_global_caisse()
    return Response({
        'total_amount': caisse.total_amount,
        'created_at': caisse.created_at,
        'updated_at': caisse.updated_at
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def caisse_encaissement(request):
    data = request.data
    
    with transaction.atomic():
        caisse = get_or_create_global_caisse()
        balance_before = caisse.total_amount
        
        amount = Decimal(str(data['amount']))
        balance_after = balance_before + amount
        
        caisse.total_amount = balance_after
        caisse.save()
        
        operation_date = parse_date(data.get('date')) or datetime.now().date()
        income_source = data.get('income_source')
        by_collaborator = income_source == 'collaborator'
        
        if income_source == 'autre' and not data.get('observation'):
            return Response({
                'error': 'Observation is required when income source is "autre"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if income_source == 'collaborator' and not data.get('project_id'):
            return Response({
                'error': 'Project ID is required when income source is "collaborator"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        operation = CaisseOperation.objects.create(
            operation_type='encaissement',
            amount=amount,
            description=data.get('description', ''),
            preuve_file=data.get('preuve_file'),
            mode_paiement=data.get('mode_paiement'),
            nom_fournisseur=data.get('nom_fournisseur'),
            banque=data.get('banque'),
            numero_cheque=data.get('numero_cheque'),
            income_source=income_source,
            observation=data.get('observation'),
            user=request.user,
            by_collaborator=by_collaborator,
            project_id=data.get('project_id') if income_source == 'collaborator' else None,
            dette_id=data.get('dette_id'),
            balance_before=balance_before,
            balance_after=balance_after,
            date=operation_date
        )
        
        dette_created = None
        if income_source == 'dette':
            dette_created = Dette.objects.create(
                creditor_name=data.get('creditor_name', 'Unknown Creditor'),
                original_amount=amount,
                remaining_amount=amount,
                description=data.get('description', f'Dette créée lors de l\'encaissement du {operation_date.strftime("%d/%m/%Y")}'),
                project_id=data.get('project_id'),
                created_by=request.user,
                status='active'
            )
            
            operation.dette = dette_created
            operation.save()
        
        caisse_history = CaisseHistory.objects.create(
            action='encaissement',
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            operation=operation,
            user=request.user,
            project_id=data.get('project_id') if income_source == 'collaborator' else None,
            description=data.get('description', ''),
            date=operation_date
        )
        
        response_data = {
            'message': 'Encaissement effectué avec succès',
            'operation_id': operation.id,
            'history_numero': caisse_history.numero,
            'new_balance': balance_after,
            'date': operation_date.isoformat()
        }
        
        if dette_created:
            response_data['dette_created'] = {
                'id': dette_created.id,
                'creditor_name': dette_created.creditor_name,
                'amount': dette_created.original_amount
            }
        
        return Response(response_data, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def caisse_decaissement(request):
    data = request.data
    
    with transaction.atomic():
        caisse = get_or_create_global_caisse()
        balance_before = caisse.total_amount
        
        amount = Decimal(str(data['amount']))
        
        if balance_before < amount:
            return Response({
                'error': 'Solde insuffisant'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not data.get('project_id'):
            return Response({
                'error': 'Project ID is required for decaissement'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        balance_after = balance_before - amount
        
        caisse.total_amount = balance_after
        caisse.save()
        
        operation_date = parse_date(data.get('date')) or datetime.now().date()
        
        operation = CaisseOperation.objects.create(
            operation_type='decaissement',
            amount=amount,
            description=data.get('description', ''),
            preuve_file=data.get('preuve_file'),
            mode_paiement=data.get('mode_paiement'),
            nom_fournisseur=data.get('nom_fournisseur'),
            banque=data.get('banque'),
            numero_cheque=data.get('numero_cheque'),
            user=request.user,
            project_id=data.get('project_id'),
            balance_before=balance_before,
            balance_after=balance_after,
            date=operation_date
        )
        
        project = get_object_or_404(Project, id=data['project_id'])
        project.total_depenses += amount
        project.save()
        
        caisse_history = CaisseHistory.objects.create(
            action='decaissement',
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            operation=operation,
            user=request.user,
            project=project,
            description=data.get('description', ''),
            date=operation_date
        )
        
        return Response({
            'message': 'Décaissement effectué avec succès',
            'operation_id': operation.id,
            'history_numero': caisse_history.numero,
            'new_balance': balance_after,
            'date': operation_date.isoformat(),
            'project_depenses_updated': float(project.total_depenses)
        }, status=status.HTTP_201_CREATED)
            

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def caisse_operations_history(request):
    operations = CaisseOperation.objects.all()
    
    operation_type = request.GET.get('type')
    if operation_type:
        operations = operations.filter(operation_type=operation_type)
    
    project_id = request.GET.get('project_id')
    if project_id:
        operations = operations.filter(project_id=project_id)
    
    year = request.GET.get('year')
    if year:
        operations = operations.filter(created_at__year=year)
    
    month = request.GET.get('month')
    if month:
        operations = operations.filter(created_at__month=month)
    
    day = request.GET.get('day')
    if day:
        operations = operations.filter(created_at__day=day)
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        operations = operations.filter(created_at__date__range=[start_date, end_date])
    elif start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        operations = operations.filter(created_at__date__gte=start_date)
    elif end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        operations = operations.filter(created_at__date__lte=end_date)
    
    operations_data = []
    for op in operations:
        preuve_file_url = None
        if op.preuve_file:
            preuve_file_url = request.build_absolute_uri(op.preuve_file.url)
        
        operations_data.append({
            'id': op.id,
            'operation_type': op.operation_type,
            'amount': op.amount,
            'description': op.description,
            'mode_paiement': op.mode_paiement,
            'nom_fournisseur': op.nom_fournisseur,
            'banque': op.banque,
            'numero_cheque': op.numero_cheque,
            'income_source': op.income_source,
            'bank_name': op.bank_name,
            'project_name': op.project.name if op.project else None,
            'dette_creditor': op.dette.creditor_name if op.dette else None,
            'user': op.user.username if op.user else None,
            'balance_before': op.balance_before,
            'balance_after': op.balance_after,
            'created_at': op.created_at,
            'preuve_file': preuve_file_url,
            'has_preuve': bool(op.preuve_file),
        })
    
    return Response(operations_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_caisse_history_pdf(request):
    # Start with CaisseHistory instead of CaisseOperation to match the history function
    history = CaisseHistory.objects.select_related(
        'operation', 'user', 'project', 'operation__dette'
    ).all()
    
    # Apply filters based on query parameters (same as history function)
    filters = Q()
    
    # Filter by project
    project_id = request.GET.get('project_id')
    if project_id:
        filters &= Q(project_id=project_id)
    
    # Filter by user
    user_id = request.GET.get('user_id')
    if user_id:
        filters &= Q(user_id=user_id)
    
    # Filter by action
    action = request.GET.get('action')
    if action:
        filters &= Q(action=action)
    
    # Filter by date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            filters &= Q(date__gte=date_from)
        except ValueError:
            pass
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            filters &= Q(date__lte=date_to)
        except ValueError:
            pass
    
    # Filter by amount range
    amount_min = request.GET.get('amount_min')
    amount_max = request.GET.get('amount_max')
    if amount_min:
        try:
            amount_min = Decimal(amount_min)
            filters &= Q(amount__gte=amount_min)
        except (ValueError, TypeError):
            pass
    if amount_max:
        try:
            amount_max = Decimal(amount_max)
            filters &= Q(amount__lte=amount_max)
        except (ValueError, TypeError):
            pass
    
    # Operation-specific filters
    if request.GET.get('operation_type'):
        filters &= Q(operation__operation_type=request.GET.get('operation_type'))
    
    if request.GET.get('mode_paiement'):
        filters &= Q(operation__mode_paiement=request.GET.get('mode_paiement'))
    
    if request.GET.get('income_source'):
        filters &= Q(operation__income_source=request.GET.get('income_source'))
    
    if request.GET.get('nom_fournisseur'):
        filters &= Q(operation__nom_fournisseur__icontains=request.GET.get('nom_fournisseur'))
    
    if request.GET.get('banque'):
        filters &= Q(operation__banque__icontains=request.GET.get('banque'))
    
    
    if request.GET.get('numero_cheque'):
        filters &= Q(operation__numero_cheque__icontains=request.GET.get('numero_cheque'))
    
    # Collaborator filtering
    by_collaborator = request.GET.get('by_collaborator')
    if by_collaborator is not None:
        collaborator_filter = by_collaborator.lower() == 'true'
        filters &= Q(operation__by_collaborator=collaborator_filter)
    
    if request.GET.get('dette_id'):
        filters &= Q(operation__dette_id=request.GET.get('dette_id'))
    
    # Filter by numero
    numero = request.GET.get('numero')
    if numero:
        filters &= Q(numero__icontains=numero)
    
    # Search in description and observation
    search = request.GET.get('search')
    if search:
        search_filters = (
            Q(description__icontains=search) |
            Q(operation__description__icontains=search) |
            Q(operation__observation__icontains=search)
        )
        filters &= search_filters
    
    # Apply all filters
    history = history.filter(filters)
    
    # Ordering
    ordering = request.GET.get('ordering', '-created_at')
    valid_orderings = [
        'created_at', '-created_at', 'date', '-date', 'amount', '-amount',
        'balance_after', '-balance_after', 'action', '-action'
    ]
    if ordering in valid_orderings:
        history = history.order_by(ordering)
    
    # Legacy date filters for backward compatibility
    year = request.GET.get('year')
    if year and not date_from and not date_to:
        history = history.filter(created_at__year=year)
    
    month = request.GET.get('month')
    if month and not date_from and not date_to:
        history = history.filter(created_at__month=month)
    
    day = request.GET.get('day')
    if day and not date_from and not date_to:
        history = history.filter(created_at__day=day)
    
    # Legacy start_date and end_date parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Determine period display
    period_display = "Toutes les opérations"
    
    if date_from and date_to:
        period_display = f"Du {date_from.strftime('%d/%m/%Y')} au {date_to.strftime('%d/%m/%Y')}"
    elif date_from:
        period_display = f"À partir du {date_from.strftime('%d/%m/%Y')}"
    elif date_to:
        period_display = f"Jusqu'au {date_to.strftime('%d/%m/%Y')}"
    elif start_date and end_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        period_display = f"Du {start_date_obj.strftime('%d/%m/%Y')} au {end_date_obj.strftime('%d/%m/%Y')}"
    elif start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        period_display = f"À partir du {start_date_obj.strftime('%d/%m/%Y')}"
    elif end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        period_display = f"Jusqu'au {end_date_obj.strftime('%d/%m/%Y')}"
    elif year and month and day:
        period_display = f"{day}/{month}/{year}"
    elif year and month:
        period_display = f"{month}/{year}"
    elif year:
        period_display = f"Année {year}"
    
    # Calculate totals from history entries
    total_encaissements = history.filter(action='encaissement').aggregate(Sum('amount'))['amount__sum'] or 0
    total_decaissements = history.filter(action='decaissement').aggregate(Sum('amount'))['amount__sum'] or 0
    solde_net = total_encaissements - total_decaissements
    total_operations = history.count()
    
    # Check which payment methods are present to determine dynamic columns
    has_cheque = history.filter(operation__mode_paiement='cheque').exists()
    has_virement = history.filter(operation__mode_paiement='virement').exists()
    has_espece = history.filter(operation__mode_paiement='espece').exists()
    
    # Get project info
    project = None
    report_title = 'Historique des Opérations de Caisse'
    
    if project_id:
        try:
            project = Project.objects.get(id=project_id)
            report_title = f'Historique des Opérations - {project.name}'
            
            # Add collaborator info to title if filtering by collaborator
            if by_collaborator is not None:
                collaborator_filter = by_collaborator.lower() == 'true'
                if collaborator_filter and project.collaborator_name:
                    report_title += f' - {project.collaborator_name}'
                elif not collaborator_filter:
                    report_title += f' - {request.user.get_full_name() or request.user.username}'
                    
        except Project.DoesNotExist:
            pass
    
    # Generate QR code data
    qr_data_parts = ["EURL E.C.H SAHRA", "Historique Caisse"]
    
    if project:
        qr_data_parts.append(f"Projet: {project.name}")
        if by_collaborator is not None:
            collaborator_filter = by_collaborator.lower() == 'true'
            if collaborator_filter and project.collaborator_name:
                qr_data_parts.append(f"Collaborateur: {project.collaborator_name}")
            elif not collaborator_filter:
                qr_data_parts.append(f"Utilisateur: {request.user.get_full_name() or request.user.username}")
    
    qr_data_parts.extend([period_display, f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}"])
    qr_data = " - ".join(qr_data_parts)
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    # Prepare history entries with additional context
    history_with_context = []
    for entry in history:
        entry_data = {
            'entry': entry,
            'is_collaborator': entry.operation and entry.operation.by_collaborator,
            'is_dette': entry.operation and entry.operation.dette_id,
            'dette_status': entry.operation.dette.status if entry.operation and entry.operation.dette else None,
            'income_source_display': entry.operation.get_income_source_display() if entry.operation and entry.operation.income_source else None,
            'mode_paiement_display': entry.operation.get_mode_paiement_display() if entry.operation and entry.operation.mode_paiement else None,
        }
        history_with_context.append(entry_data)
    
    # PAGINATION LOGIC - Split operations into pages of 8
    OPERATIONS_PER_PAGE = 8
    
    def paginate_operations(operations_list, page_size):
        """Split operations into pages with additional metadata"""
        pages = []
        for i in range(0, len(operations_list), page_size):
            page_operations = operations_list[i:i + page_size]
            page_info = {
                'operations': page_operations,
                'page_number': len(pages) + 1,
                'start_operation': i + 1,
                'end_operation': min(i + page_size, len(operations_list)),
                'total_operations_in_page': len(page_operations)
            }
            pages.append(page_info)
        return pages
    
    # Create paginated history
    paginated_history = paginate_operations(history_with_context, OPERATIONS_PER_PAGE)
    total_pages = len(paginated_history)
        
    # Collaborator info for context
    collaborator_info = None
    if project and by_collaborator is not None:
        collaborator_filter = by_collaborator.lower() == 'true'
        if collaborator_filter:
            collaborator_info = {
                'is_collaborator': True,
                'name': project.collaborator_name or 'Collaborateur'
            }
        else:
            collaborator_info = {
                'is_collaborator': False,
                'name': request.user.get_full_name() or request.user.username
            }
    
    # Context for template
    context = {
        'report_title': report_title,
        'generation_date': timezone.now(),
        'generated_by': request.user,
        'period_display': period_display,
        'history': history,
        'history_with_context': history_with_context,
        'paginated_history': paginated_history,
        'total_pages': total_pages,
        'operations_per_page': OPERATIONS_PER_PAGE,
        'total_encaissements': total_encaissements,
        'total_decaissements': total_decaissements,
        'solde_net': solde_net,
        'total_operations': total_operations,
        'project': project,
        'collaborator_info': collaborator_info,
        'qr_code_base64': qr_code_base64,
        # Dynamic column flags
        'has_cheque': has_cheque,
        'has_virement': has_virement,
        'has_espece': has_espece,
    }
    
    # Render HTML template
    html_string = render_to_string('history/caisse_history.html', context)
    
    # Generate PDF
    font_config = FontConfiguration()
    html = HTML(string=html_string)
    pdf = html.write_pdf(font_config=font_config)
    
    # Generate filename with filters info
    filename_parts = ["historique_caisse"]
    
    if project:
        project_name_clean = "".join(c for c in project.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename_parts.append(project_name_clean.replace(' ', '_'))
        
        if by_collaborator is not None:
            collaborator_filter = by_collaborator.lower() == 'true'
            if collaborator_filter:
                filename_parts.append("collaborateur")
            else:
                filename_parts.append("utilisateur")
    
    if action:
        filename_parts.append(action)
    
    filename_parts.append(timezone.now().strftime("%Y%m%d_%H%M%S"))
    filename = "_".join(filename_parts) + ".pdf"
    
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_project(request):
    data = request.data
    
    try:
        # Convert estimated_budget to Decimal
        estimated_budget = Decimal(str(data['estimated_budget']))
        
        project = Project.objects.create(
            name=data['name'],
            description=data['description'],
            estimated_budget=estimated_budget,  # Use the converted Decimal
            contract_file=data.get('contract_file'),
            ods_file=data.get('ods_file'),
            operation=data.get('operation'),
            numero_operation=data.get('numero_operation'),
            date_debut=data['date_debut'],
            period_months=data['period_months'],
            collaborator_name=data.get('collaborator_name'),
            created_by=request.user
        )
        
        return Response({
            'message': 'Projet créé avec succès',
            'project_id': project.id,
            'project_name': project.name
        }, status=status.HTTP_201_CREATED)
        
    except (ValueError, TypeError, KeyError) as e:
        return Response({
            'error': f'Invalid data provided: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_list(request):
    projects = Project.objects.all()
    
    projects_data = []
    for project in projects:
        projects_data.append({
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'estimated_budget': project.estimated_budget,
            'operation': project.operation,
            'numero_operation': project.numero_operation,
            'date_debut': project.date_debut,
            'period_months': project.period_months,
            'collaborator_name': project.collaborator_name,
            'total_depenses': project.total_depenses,
            'total_accreance': project.total_accreance,
            'total_benefices': project.total_benefices,
            'created_by': project.created_by.username if project.created_by else None,
            'created_at': project.created_at
        })
    
    return Response(projects_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    return Response({
        'id': project.id,
        'name': project.name,
        'description': project.description,
        'estimated_budget': project.estimated_budget,
        'operation': project.operation,
        'numero_operation': project.numero_operation,
        'date_debut': project.date_debut,
        'period_months': project.period_months,
        'collaborator_name': project.collaborator_name,
        'total_depenses': project.total_depenses,
        'total_accreance': project.total_accreance,
        'total_benefices': project.total_benefices,
        'created_by': project.created_by.username if project.created_by else None,
        'created_at': project.created_at,
        # Add file URLs
        'contract_file_url': project.contract_file.url if project.contract_file else None,
        'ods_file_url': project.ods_file.url if project.ods_file else None,
        'contract_file_name': project.contract_file.name.split('/')[-1] if project.contract_file else None,
        'ods_file_name': project.ods_file.name.split('/')[-1] if project.ods_file else None,
    })


@api_view(['GET'])
def generate_project_pdf(request, project_id):
    """
    Generate PDF for project information
    """
    try:
        # Get the project
        project = get_object_or_404(Project, id=project_id)
        
        # Prepare context data
        context = {
            'project': project,
            'operation': project.operation or '--',
            'numero_operation': project.numero_operation or '--',
            'date_debut': project.date_debut.strftime('%d/%m/%Y') if project.date_debut else '--',
            'period_months': project.period_months or '--',
            'collaborator_name': project.collaborator_name or '--',
            'estimated_budget': f"{project.estimated_budget:,.2f} DA" if project.estimated_budget else '--',
            'total_depenses': f"{project.total_depenses:,.2f} DA",
            'total_accreance': f"{project.total_accreance:,.2f} DA",
            'total_benefices': f"{project.total_benefices:,.2f} DA",
            'created_at': project.created_at.strftime('%d/%m/%Y à %H:%M'),
        }
        
        # Load template
        template = get_template('projects/project_info_pdf.html')
        html_content = template.render(context)
        
        # Generate PDF
        pdf_file = BytesIO()
        
        # CSS for sticker styling
        css_content = """
        @page {
            size: 10cm 7cm;
            margin: 0.5cm;
        }
        body {
            font-family: 'DejaVu Sans', Arial, sans-serif;
            font-size: 11px;
            line-height: 1.3;
            color: #000;
        }
        """
        
        HTML(string=html_content).write_pdf(
            pdf_file,
            stylesheets=[CSS(string=css_content)]
        )
        
        pdf_file.seek(0)
        
        # Create response
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="etiquette_projet_{project.id}.pdf"'
        
        return response
        
    except Exception as e:
        return Response({
            'error': 'Erreur lors de la génération du PDF',
            'detail': str(e)
        }, status=500)



@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    data = request.data
    
    old_values = {
        'name': project.name,
        'description': project.description,
        'estimated_budget': float(project.estimated_budget),
        'collaborator_name': project.collaborator_name
    }
    
    project.name = data.get('name', project.name)
    project.description = data.get('description', project.description)
    project.estimated_budget = data.get('estimated_budget', project.estimated_budget)
    project.operation = data.get('operation', project.operation)
    project.numero_operation = data.get('numero_operation', project.numero_operation)
    project.collaborator_name = data.get('collaborator_name', project.collaborator_name)
    
    if 'contract_file' in data:
        project.contract_file = data['contract_file']
    if 'ods_file' in data:
        project.ods_file = data['ods_file']
    
    project.save()
    
    new_values = {
        'name': project.name,
        'description': project.description,
        'estimated_budget': float(project.estimated_budget),
        'collaborator_name': project.collaborator_name
    }
    
    
    return Response({
        'message': 'Projet mis à jour avec succès',
        'project': {
            'id': project.id,
            'name': project.name,
            'total_benefices': project.total_benefices
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_dette(request):
    from django.db import transaction
    from decimal import Decimal
    from datetime import date
    
    data = request.data
    
    # Convert string amounts to Decimal
    original_amount = Decimal(str(data['original_amount']))
    
    # Get current balance from the latest history entry
    latest_history = CaisseHistory.objects.order_by('-created_at').first()
    current_balance = latest_history.balance_after if latest_history else Decimal('0.00')
    
    # Calculate new balance after receiving the dette (encaissement)
    new_balance = current_balance + original_amount
    
    # Use atomic transaction to ensure both dette and history are created together
    with transaction.atomic():
        # Create the Dette
        dette = Dette.objects.create(
            creditor_name=data['creditor_name'],
            original_amount=original_amount,
            remaining_amount=original_amount,
            description=data.get('description', ''),
            project_id=data.get('project_id'),
            created_by=request.user
        )
        
        # Create corresponding CaisseHistory entry
        CaisseHistory.objects.create(
            action='encaissement',
            amount=original_amount,
            balance_before=current_balance,
            balance_after=new_balance,
            user=request.user,
            project_id=data.get('project_id'),
            description=f"Dette créée - {data['creditor_name']}: {data.get('description', '')}",
            date=data.get('date', date.today())  # Use provided date or today
        )
    
    return Response({
        'message': 'Dette créée avec succès et enregistrée dans l\'historique',
        'dette_id': dette.id,
        'creditor_name': dette.creditor_name,
        'original_amount': dette.original_amount,
        'new_balance': new_balance
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dette_list(request):
    dettes = Dette.objects.all()
    
    status_filter = request.GET.get('status')
    if status_filter:
        dettes = dettes.filter(status=status_filter)
    
    project_id = request.GET.get('project_id')
    if project_id:
        dettes = dettes.filter(project_id=project_id)
    
    dettes_data = []
    for dette in dettes:
        dettes_data.append({
            'id': dette.id,
            'creditor_name': dette.creditor_name,
            'original_amount': dette.original_amount,
            'remaining_amount': dette.remaining_amount,
            'description': dette.description,
            'status': dette.status,
            'project_name': dette.project.name if dette.project else None,
            'created_by': dette.created_by.username if dette.created_by else None,
            'date_created': dette.date_created,
            'completed_at': dette.completed_at
        })
    
    return Response(dettes_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dette_detail(request, dette_id):
    dette = get_object_or_404(Dette, id=dette_id)
    
    payments = DettePayment.objects.filter(dette=dette)
    payments_data = []
    for payment in payments:
        payments_data.append({
            'id': payment.id,
            'amount_paid': payment.amount_paid,
            'payment_date': payment.payment_date,
            'description': payment.description,
            'mode_paiement': payment.mode_paiement,
            'nom_fournisseur': payment.nom_fournisseur,
            'banque': payment.banque,
            'numero_cheque': payment.numero_cheque,
            'created_by': payment.created_by.username if payment.created_by else None
        })
    
    return Response({
        'id': dette.id,
        'creditor_name': dette.creditor_name,
        'original_amount': dette.original_amount,
        'remaining_amount': dette.remaining_amount,
        'description': dette.description,
        'status': dette.status,
        'project_name': dette.project.name if dette.project else None,
        'created_by': dette.created_by.username if dette.created_by else None,
        'date_created': dette.date_created,
        'completed_at': dette.completed_at,
        'payments': payments_data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dette_payment(request, dette_id):
    dette = get_object_or_404(Dette, id=dette_id)
    data = request.data
    
    if dette.status == 'completed':
        return Response({
            'error': 'Cette dette est déjà complètement payée'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    amount_paid = Decimal(str(data['amount_paid']))
    
    if amount_paid > dette.remaining_amount:
        return Response({
            'error': 'Le montant payé dépasse le montant restant'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    with transaction.atomic():
        caisse = get_or_create_global_caisse()
        balance_before = caisse.total_amount
        balance_after = balance_before - amount_paid
        
        if balance_before < amount_paid:
            return Response({
                'error': 'Solde insuffisant dans la caisse'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        caisse.total_amount = balance_after
        caisse.save()
        
        caisse_operation = CaisseOperation.objects.create(
            operation_type='decaissement',
            amount=amount_paid,
            description=f'Paiement dette - {dette.creditor_name}',
            preuve_file=data.get('preuve_file'),
            mode_paiement=data.get('mode_paiement'),
            nom_fournisseur=data.get('nom_fournisseur'),
            banque=data.get('banque'),
            date=timezone.now().date(),
            numero_cheque=data.get('numero_cheque'),
            user=request.user,
            dette=dette,
            balance_before=balance_before,
            balance_after=balance_after
        )
        
        payment = DettePayment.objects.create(
            dette=dette,
            amount_paid=amount_paid,
            description=data.get('description', ''),
            preuve_file=data.get('preuve_file'),
            mode_paiement=data.get('mode_paiement'),
            nom_fournisseur=data.get('nom_fournisseur'),
            banque=data.get('banque'),
            numero_cheque=data.get('numero_cheque'),
            created_by=request.user,
            caisse_operation=caisse_operation
        )
        
        dette.remaining_amount -= amount_paid
        dette.save()
        
        CaisseHistory.objects.create(
            action='decaissement',
            amount=amount_paid,
            balance_before=balance_before,
            balance_after=balance_after,
            operation=caisse_operation,
            date = timezone.now().date() , 
            user=request.user,
            description=f'Paiement dette - {dette.creditor_name}'
        )
        
        return Response({
            'message': 'Paiement effectué avec succès',
            'payment_id': payment.id,
            'remaining_amount': dette.remaining_amount,
            'status': dette.status,
            'new_caisse_balance': balance_after
        }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def caisse_history(request):
    history = CaisseHistory.objects.select_related(
        'operation', 'user', 'project', 'operation__dette'
    ).all()
    
    # Apply filters based on query parameters
    filters = Q()
    
    # Filter by project
    project_id = request.GET.get('project_id')
    if project_id:
        filters &= Q(project_id=project_id)
    
    # Filter by user
    user_id = request.GET.get('user_id')
    if user_id:
        filters &= Q(user_id=user_id)
    
    # Filter by action
    action = request.GET.get('action')
    if action:
        filters &= Q(action=action)
    
    # Filter by date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            filters &= Q(date__gte=date_from)
        except ValueError:
            pass
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            filters &= Q(date__lte=date_to)
        except ValueError:
            pass
    
    # Filter by amount range
    amount_min = request.GET.get('amount_min')
    amount_max = request.GET.get('amount_max')
    if amount_min:
        try:
            amount_min = Decimal(amount_min)
            filters &= Q(amount__gte=amount_min)
        except (ValueError, TypeError):
            pass
    if amount_max:
        try:
            amount_max = Decimal(amount_max)
            filters &= Q(amount__lte=amount_max)
        except (ValueError, TypeError):
            pass
    
    # Operation-specific filters
    if request.GET.get('operation_type'):
        filters &= Q(operation__operation_type=request.GET.get('operation_type'))
    
    if request.GET.get('mode_paiement'):
        filters &= Q(operation__mode_paiement=request.GET.get('mode_paiement'))
    
    if request.GET.get('income_source'):
        filters &= Q(operation__income_source=request.GET.get('income_source'))
    
    if request.GET.get('nom_fournisseur'):
        filters &= Q(operation__nom_fournisseur__icontains=request.GET.get('nom_fournisseur'))
    
    if request.GET.get('banque'):
        filters &= Q(operation__banque__icontains=request.GET.get('banque'))
    
    if request.GET.get('numero_cheque'):
        filters &= Q(operation__numero_cheque__icontains=request.GET.get('numero_cheque'))
    
    # Handle by_collaborator filter - UPDATED LOGIC
    by_collaborator_param = request.GET.get('by_collaborator')
    if by_collaborator_param is not None:
        by_collaborator = by_collaborator_param.lower() == 'true'
        filters &= Q(operation__by_collaborator=by_collaborator)
    
    if request.GET.get('dette_id'):
        filters &= Q(operation__dette_id=request.GET.get('dette_id'))
    
    # Filter by numero
    numero = request.GET.get('numero')
    if numero:
        filters &= Q(numero__icontains=numero)
    
    # Search in description and observation
    search = request.GET.get('search')
    if search:
        search_filters = (
            Q(description__icontains=search) |
            Q(operation__description__icontains=search) |
            Q(operation__observation__icontains=search)
        )
        filters &= search_filters
    
    # Apply all filters
    history = history.filter(filters)
    
    # Only include entries that have operations (for project history)
    history = history.filter(operation__isnull=False)
    
    # Ordering
    ordering = request.GET.get('ordering', '-created_at')
    valid_orderings = [
        'created_at', '-created_at', 'date', '-date', 'amount', '-amount',
        'balance_after', '-balance_after', 'action', '-action'
    ]
    if ordering in valid_orderings:
        history = history.order_by(ordering)
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 50))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = history.count()
    history_page = history[start:end]
    
    history_data = []
    for entry in history_page:
        data = {
            'id': entry.id,
            'numero': entry.numero,
            'action': entry.action,
            'amount': str(entry.amount),
            'balance_before': str(entry.balance_before),
            'balance_after': str(entry.balance_after),
            'user': {
                'id': entry.user.id if entry.user else None,
                'username': entry.user.username if entry.user else None,
                'first_name': entry.user.first_name if entry.user else None,
                'last_name': entry.user.last_name if entry.user else None,
            } if entry.user else None,
            'project': {
                'id': entry.project.id if entry.project else None,
                'name': entry.project.name if entry.project else None,
            } if entry.project else None,
            'description': entry.description,
            'date': entry.date,
            'created_at': entry.created_at,
            'operation': None
        }
        
        # Add operation details if exists
        if entry.operation:
            operation_data = {
                'id': entry.operation.id,
                'operation_type': entry.operation.operation_type,
                'amount': str(entry.operation.amount),
                'description': entry.operation.description,
                'mode_paiement': entry.operation.mode_paiement,
                'income_source': entry.operation.income_source,
                'observation': entry.operation.observation,
                'by_collaborator': entry.operation.by_collaborator,
                'nom_fournisseur': entry.operation.nom_fournisseur,
                'banque': entry.operation.banque,
                'numero_cheque': entry.operation.numero_cheque,
                'preuve_file': entry.operation.preuve_file.url if entry.operation.preuve_file else None,
                'date': entry.operation.date,
                'dette': {
                    'id': entry.operation.dette.id if entry.operation.dette else None,
                    # Add other dette fields you want to include
                } if entry.operation.dette else None,
            }
            data['operation'] = operation_data
        
        history_data.append(data)
    
    return Response({
        'results': history_data,
        'count': total_count,
        'page': page,
        'page_size': page_size,
        'total_pages': (total_count + page_size - 1) // page_size,
        'has_next': end < total_count,
        'has_previous': page > 1,
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_bon_livraison(request):
    data = request.data
    
    project = get_object_or_404(Project, id=data['project_id'])
    
    bon_livraison = BonDeLivraison.objects.create(
        project=project,
        origin_address=data['origin_address'],
        destination_address=data['destination_address'],
        description=data.get('description', ''),
        payment_method=data['payment_method'],
        payment_proof=data.get('payment_proof'),
        nom_fournisseur=data.get('nom_fournisseur'),
        banque=data.get('banque'),
        numero_cheque=data.get('numero_cheque'),
        created_by=request.user
    )
    
    return Response({
        'message': 'Bon de livraison créé avec succès',
        'bl_id': bon_livraison.id,
        'bl_number': bon_livraison.bl_number
    }, status=status.HTTP_201_CREATED)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_operation_pdf(request, history_id):
    """
    Generate PDF for a single caisse operation
    """
    try:
        # Get the specific history entry
        history_entry = get_object_or_404(CaisseHistory, id=history_id)
        
        # Check if user has permission to view this operation
        # Add your permission logic here if needed
        
        # Generate QR code
        qr_data = f"ECH-OP-{history_entry.numero}-{history_entry.date}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
        
        # Prepare context data
        generation_date = timezone.now()
        
        # Determine if operation is by collaborator or related to dette
        is_collaborator = False
        is_dette = False
        collaborator_info = None
        
        if history_entry.operation:
            is_collaborator = history_entry.operation.by_collaborator
            is_dette = history_entry.operation.dette is not None
            
            # Get collaborator info if applicable
            if is_collaborator and history_entry.project:
                collaborator_info = {
                    'is_collaborator': True,
                    'name': getattr(history_entry.project, 'collaborator_name', 'N/A')
                }
        
        # Check payment mode features
        has_cheque = history_entry.operation and history_entry.operation.mode_paiement == 'cheque'
        has_virement = history_entry.operation and history_entry.operation.mode_paiement == 'virement'
        
        context = {
            'report_title': f'Détail Opération {history_entry.numero}',
            'generation_date': generation_date,
            'generated_by': request.user,
            'history_entry': history_entry,
            'is_collaborator': is_collaborator,
            'is_dette': is_dette,
            'collaborator_info': collaborator_info,
            'has_cheque': has_cheque,
            'has_virement': has_virement,
            'qr_code_base64': qr_base64,
            'project': history_entry.project,
        }
        
        # Render HTML template
        html_string = render_to_string('caisse/operation_detail_pdf.html', context)
        
        # Generate PDF
        font_config = FontConfiguration()
        html = HTML(string=html_string)
        
        # Create CSS for better PDF rendering
        css = CSS(string='''
            @page {
                size: A4;
                margin: 1cm;
            }
            body {
                font-family: Arial, sans-serif;
            }
        ''', font_config=font_config)
        
        # Generate the PDF
        pdf = html.write_pdf(stylesheets=[css], font_config=font_config)
        
        # Create HTTP response
        filename = f"operation_{history_entry.numero}_{history_entry.date.strftime('%Y%m%d')}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except CaisseHistory.DoesNotExist:
        return Response(
            {'error': 'Operation not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Error generating PDF: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bon_livraison_list(request):
    bons = BonDeLivraison.objects.all()
    
    project_id = request.GET.get('project_id')
    if project_id:
        bons = bons.filter(project_id=project_id)
    
    bons_data = []
    for bon in bons:
        bons_data.append({
            'id': bon.id,
            'bl_number': bon.bl_number,
            'project_name': bon.project.name,
            'origin_address': bon.origin_address,
            'destination_address': bon.destination_address,
            'description': bon.description,
            'payment_method': bon.payment_method,
            'total_amount': bon.total_amount,
            'created_by': bon.created_by.username if bon.created_by else None,
            'created_at': bon.created_at
        })
    
    return Response(bons_data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_bon_commande(request):
    data = request.data
    
    bon_commande = BonDeCommande.objects.create(
        description=data.get('description', ''),
        created_by=request.user
    )
    
    return Response({
        'message': 'Bon de commande créé avec succès',
        'bc_id': bon_commande.id,
        'bc_number': bon_commande.bc_number
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bon_commande_list(request):
    bons = BonDeCommande.objects.all()
    
    bons_data = []
    for bon in bons:
        bons_data.append({
            'id': bon.id,
            'bc_number': bon.bc_number,
            'date_commande': bon.date_commande,
            'description': bon.description,
            'total_ht': bon.total_ht,
            'created_by': bon.created_by.username if bon.created_by else None,
            'created_at': bon.created_at
        })
    
    return Response(bons_data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_ordre_mission(request):
    data = request.data
    
    ordre_mission = OrdreDeMission.objects.create(
        nom_prenom=data['nom_prenom'],
        fonction=data['fonction'],
        adresse=data['adresse'],
        destination=data['destination'],
        motif=data['motif'],
        moyen_deplacement=data['moyen_deplacement'],
        matricule=data['matricule'],
        matricule_2=data.get('matricule_2'),
        date_depart=data['date_depart'],
        date_retour=data.get('date_retour'),
        accompagne_par=data.get('accompagne_par', ''),
        created_by=request.user.username
    )
    
    return Response({
        'message': 'Ordre de mission créé avec succès',
        'mission_id': ordre_mission.id,
        'numero': ordre_mission.numero
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ordre_mission_list(request):
    missions = OrdreDeMission.objects.all()
    
    missions_data = []
    for mission in missions:
        missions_data.append({
            'id': mission.id,
            'numero': mission.numero,
            'nom_prenom': mission.nom_prenom,
            'fonction': mission.fonction,
            'destination': mission.destination,
            'motif': mission.motif,
            'date_depart': mission.date_depart,
            'date_retour': mission.date_retour,
            'created_by': mission.created_by,
            'date_creation': mission.date_creation
        })
    
    return Response(missions_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    caisse = get_or_create_global_caisse()
    
    total_projects = Project.objects.count()
    active_dettes = Dette.objects.filter(status='active').count()
    completed_dettes = Dette.objects.filter(status='completed').count()
    
    total_encaissements = CaisseOperation.objects.filter(
        operation_type='encaissement'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_decaissements = CaisseOperation.objects.filter(
        operation_type='decaissement'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_depenses = Project.objects.aggregate(
        total=Sum('total_depenses')
    )['total'] or 0
    
    total_recus = Project.objects.aggregate(
        total=Sum('total_recus')
    )['total'] or 0
    
    total_benefices = Project.objects.aggregate(
        total=Sum('total_benefices')
    )['total'] or 0
    
    return Response({
        'caisse_balance': caisse.total_amount,
        'total_projects': total_projects,
        'active_dettes': active_dettes,
        'completed_dettes': completed_dettes,
        'total_encaissements': total_encaissements,
        'total_decaissements': total_decaissements,
        'total_depenses': total_depenses,
        'total_recus': total_recus,
        'total_benefices': total_benefices,
        'recent_operations': CaisseOperation.objects.all()[:5].values(
            'operation_type', 'amount', 'created_at', 'project__name'
        )
    })


from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_revenu(request):
    try:
        data = request.data
        
        # Get required fields
        project_id = data.get('project_id')
        montant_str = data.get('montant')
        date_str = data.get('date')
        revenu_code = data.get('revenu_code')  # New required field
        
        if not all([project_id, montant_str, date_str, revenu_code]):
            return Response({
                'success': False,
                'error': 'Missing required fields: project_id, montant, date, revenu_code'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate revenu_code uniqueness
        if Revenu.objects.filter(revenu_code=revenu_code).exists():
            return Response({
                'success': False,
                'error': f'Revenu code "{revenu_code}" already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get project
        try:
            project = get_object_or_404(Project, id=project_id)
        except:
            return Response({
                'success': False,
                'error': 'Project not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Convert and validate montant
        try:
            montant = Decimal(str(montant_str))
            if montant <= 0:
                return Response({
                    'success': False,
                    'error': 'Amount must be greater than 0'
                }, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError, Decimal.InvalidOperation):
            return Response({
                'success': False,
                'error': 'Invalid amount format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse date
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Optional: Check if project has enough budget (you may remove this if not needed)
        if project.estimated_budget < montant:
            return Response({
                'success': False,
                'error': f'Insufficient budget. Available: {project.estimated_budget} DZD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create revenu with user-provided code
        revenu = Revenu.objects.create(
            revenu_code=revenu_code,
            project=project,
            montant=montant,
            date=date,
            created_by=request.user
        )
        
        # Handle PDF file if provided
        if 'pdf_file' in request.FILES:
            revenu.pdf_file = request.FILES['pdf_file']
            revenu.save()
        
        # Refresh project from database to get updated values
        project.refresh_from_db()
        
        return Response({
            'success': True,
            'message': 'Revenu created successfully',
            'revenu': {
                'id': revenu.id,
                'revenu_code': revenu.revenu_code,
                'project_name': revenu.project.name,
                'montant': str(revenu.montant),
                'date': revenu.date.strftime('%Y-%m-%d'),
                'created_by': revenu.created_by.username,
                'created_at': revenu.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'remaining_budget': str(project.estimated_budget),
                'project_total_accreance': str(project.total_accreance),
                'project_total_depenses': str(project.total_depenses),
                'project_benefices': str(project.total_benefices)
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        # Log the actual error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error creating revenu: {str(e)}', exc_info=True)
        
        return Response({
            'success': False,
            'error': f'Error creating revenu: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_revenus_by_project(request, project_id):
    try:
        project = get_object_or_404(Project, id=project_id)
        
        # Get query parameters for date filtering
        year = request.GET.get('year')
        month = request.GET.get('month')
        day = request.GET.get('day')
        
        # Start with all revenus for the project
        revenus = Revenu.objects.filter(project=project)
        
        # Apply date filters
        if year:
            revenus = revenus.filter(date__year=year)
        if month:
            revenus = revenus.filter(date__month=month)
        if day:
            revenus = revenus.filter(date__day=day)
        
        # Prepare response data
        revenu_list = []
        for revenu in revenus:
            revenu_list.append({
                'id': revenu.id,
                'revenu_code': revenu.revenu_code,
                'montant': str(revenu.montant),
                'date': revenu.date.strftime('%Y-%m-%d'),
                'pdf_file': revenu.pdf_file.url if revenu.pdf_file else None,
                'created_by': revenu.created_by.username if revenu.created_by else None,
                'created_at': revenu.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return Response({
            'success': True,
            'project': {
                'id': project.id,
                'name': project.name,
                'estimated_budget': str(project.estimated_budget)
            },
            'revenus': revenu_list,
            'total_revenus': len(revenu_list)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error retrieving revenus: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_revenu_detail(request, revenu_id):
    try:
        revenu = get_object_or_404(Revenu, id=revenu_id)
        
        return Response({
            'success': True,
            'revenu': {
                'id': revenu.id,
                'revenu_code': revenu.revenu_code,
                'project': {
                    'id': revenu.project.id,
                    'name': revenu.project.name,
                    'estimated_budget': str(revenu.project.estimated_budget)
                },
                'montant': str(revenu.montant),
                'date': revenu.date.strftime('%Y-%m-%d'),
                'pdf_file': revenu.pdf_file.url if revenu.pdf_file else None,
                'created_by': revenu.created_by.username if revenu.created_by else None,
                'created_at': revenu.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': revenu.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error retrieving revenu: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_revenu(request, revenu_id):
    try:
        revenu = get_object_or_404(Revenu, id=revenu_id)
        
        # Store revenu data before deletion
        revenu_data = {
            'id': revenu.id,
            'revenu_code': revenu.revenu_code,
            'project_name': revenu.project.name,
            'montant': str(revenu.montant),
            'date': revenu.date.strftime('%Y-%m-%d')
        }
        
        # Get project and restore the budget
        project = revenu.project
        project.estimated_budget += revenu.montant
        project.save(update_fields=['estimated_budget'])
        
        # Delete the PDF file if it exists
        if revenu.pdf_file:
            try:
                revenu.pdf_file.delete(save=False)
            except Exception:
                pass  # Continue even if file deletion fails
        
        # Delete the revenu
        revenu.delete()
        
        return Response({
            'success': True,
            'message': 'Revenu deleted successfully',
            'deleted_revenu': revenu_data,
            'project_budget_restored': str(project.estimated_budget)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error deleting revenu: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_project_finance_pdf(request):
    """
    Generate PDF report for project finances showing accreance and depenses
    
    POST parameters:
    - project_id: ID of the project
    - start_date: Start date (YYYY-MM-DD) - optional
    - end_date: End date (YYYY-MM-DD) - optional
    - by_collaborator: boolean - if true, show only collaborator operations
    """
    try:
        # Get parameters
        project_id = request.data.get('project_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        by_collaborator = request.data.get('by_collaborator', False)
        print(request.method)
        print(request.GET)
        print(request.data)
        print(request.query_params)  # if using DRF

        print(f"Parameters received: project_id={project_id}, start_date={start_date}, end_date={end_date}, by_collaborator={by_collaborator}")
        if not project_id:
            return Response({'error': 'project_id is required'}, status=400)
        
        # Get project
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({'error': 'Project not found'}, status=404)
        
        # Parse dates
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Invalid start_date format. Use YYYY-MM-DD'}, status=400)
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Invalid end_date format. Use YYYY-MM-DD'}, status=400)
        
        # Build the financial history
        history_entries = []
        
        if by_collaborator:
            # For collaborator view: show only encaissement operations by collaborator
            operations_query = CaisseOperation.objects.filter(
                project=project,
                by_collaborator=True,
                operation_type='encaissement'
            )
            
            if start_date:
                operations_query = operations_query.filter(date__gte=start_date)
            if end_date:
                operations_query = operations_query.filter(date__lte=end_date)
            
            operations = operations_query.order_by('date', 'created_at')
            
            for operation in operations:
                # Get corresponding history entry
                try:
                    history = CaisseHistory.objects.get(operation=operation)
                    history_entries.append({
                        'date': operation.date,
                        'created_at': operation.created_at,
                        'numero': history.numero,
                        'description': operation.description or f"Encaissement collaborateur - {project.collaborator_name or 'N/A'}",
                        'type': 'encaissement',
                        'amount': operation.amount,
                        'balance_after': history.balance_after,
                        'operation': operation,
                        'user': operation.user,
                        'is_collaborator': True,
                        'is_dette': operation.dette is not None,
                    })
                except CaisseHistory.DoesNotExist:
                    continue
            
            report_title = f"Rapport Collaborateur - {project.name}"
            collaborator_info = {
                'is_collaborator': True,
                'name': project.collaborator_name or 'N/A'
            }
            
        else:
            # For regular view: show accreance (revenus) and depenses
            
            # Get revenus (accreance)
            revenus_query = Revenu.objects.filter(project=project)
            if start_date:
                revenus_query = revenus_query.filter(date__gte=start_date)
            if end_date:
                revenus_query = revenus_query.filter(date__lte=end_date)
            
            revenus = revenus_query.order_by('date', 'created_at')
            
            for revenu in revenus:
                history_entries.append({
                    'date': revenu.date,
                    'created_at': revenu.created_at,
                    'numero': revenu.revenu_code,
                    'description': f"Revenu - {project.name}",
                    'type': 'accreance',
                    'amount': revenu.montant,
                    'balance_after': None,  # Not applicable for revenus
                    'operation': None,
                    'user': revenu.created_by,
                    'is_collaborator': False,
                    'is_dette': False,
                    'revenu': revenu,
                })
            
            # Get depenses (operations that are not by collaborator)
            depenses_query = CaisseOperation.objects.filter(
                project=project,
                by_collaborator=False,
                operation_type='decaissement'
            )
            
            if start_date:
                depenses_query = depenses_query.filter(date__gte=start_date)
            if end_date:
                depenses_query = depenses_query.filter(date__lte=end_date)
            
            depenses = depenses_query.order_by('date', 'created_at')
            
            for operation in depenses:
                try:
                    history = CaisseHistory.objects.get(operation=operation)
                    history_entries.append({
                        'date': operation.date,
                        'created_at': operation.created_at,
                        'numero': history.numero,
                        'description': operation.description or f"Dépense - {project.name}",
                        'type': 'depense',
                        'amount': operation.amount,
                        'balance_after': history.balance_after,
                        'operation': operation,
                        'user': operation.user,
                        'is_collaborator': False,
                        'is_dette': operation.dette is not None,
                    })
                except CaisseHistory.DoesNotExist:
                    continue
            
            report_title = f"Rapport Financier - {project.name}"
            collaborator_info = None
        
        # Sort all entries by date and created_at
        history_entries.sort(key=lambda x: (x['date'], x['created_at']))
        
        # Calculate totals
        if by_collaborator:
            total_encaissements = sum(entry['amount'] for entry in history_entries if entry['type'] == 'encaissement')
            total_decaissements = Decimal('0.00')
            total_accreance = Decimal('0.00')
            total_depenses = Decimal('0.00')
            solde_net = total_encaissements
        else:
            total_encaissements = Decimal('0.00')
            total_decaissements = Decimal('0.00')
            total_accreance = sum(entry['amount'] for entry in history_entries if entry['type'] == 'accreance')
            total_depenses = sum(entry['amount'] for entry in history_entries if entry['type'] == 'depense')
            solde_net = total_accreance - total_depenses
        
        # Determine period display
        if start_date and end_date:
            period_display = f"Du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}"
        elif start_date:
            period_display = f"À partir du {start_date.strftime('%d/%m/%Y')}"
        elif end_date:
            period_display = f"Jusqu'au {end_date.strftime('%d/%m/%Y')}"
        else:
            period_display = "Toute la période"
        
        # Check for payment modes to show appropriate columns
        has_cheque = False
        has_virement = False
        
        for entry in history_entries:
            if entry['operation']:
                if entry['operation'].mode_paiement == 'cheque':
                    has_cheque = True
                elif entry['operation'].mode_paiement == 'virement':
                    has_virement = True
        
        # Generate QR Code
        qr_data = f"EURL E.C.H SAHRA - {report_title} - {period_display}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert QR code to base64
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
        
        # Prepare context for template
        context = {
            'report_title': report_title,
            'project': project,
            'period_display': period_display,
            'history': history_entries,
            'history_with_context': [{'entry': entry, 'is_collaborator': entry['is_collaborator'], 'is_dette': entry['is_dette']} for entry in history_entries],
            'total_encaissements': total_encaissements,
            'total_decaissements': total_decaissements,
            'total_accreance': total_accreance,
            'total_depenses': total_depenses,
            'solde_net': solde_net,
            'total_operations': len(history_entries),
            'generation_date': timezone.now(),
            'generated_by': request.user,
            'collaborator_info': collaborator_info,
            'by_collaborator': by_collaborator,
            'has_cheque': has_cheque,
            'has_virement': has_virement,
            'qr_code_base64': qr_base64,
        }
        
        # Render HTML
        html_content = render_to_string('projects/project_history.html', context)
        
        # Generate PDF
        pdf_file = HTML(string=html_content).write_pdf()
        
        # Create response
        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = f"{report_title.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_dette_journal_pdf(request, dette_id):
    try:
        dette = Dette.objects.select_related('project', 'created_by').get(id=dette_id)
        payments = DettePayment.objects.filter(dette=dette).select_related(
            'created_by', 'caisse_operation'
        ).order_by('payment_date')

        total_paid = payments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        remaining_amount = dette.remaining_amount
        payment_count = payments.count()

        # QR Code
        qr_data = f"Dette ID: {dette.id}\nCréancier: {dette.creditor_name}\nMontant: {dette.original_amount} DZD\nDate: {dette.date_created.strftime('%d/%m/%Y')}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        qr_img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

        context = {
            'dette': dette,
            'payments': payments,
            'total_paid': total_paid,
            'remaining_amount': remaining_amount,
            'payment_count': payment_count,
            'generation_date': timezone.now(),
            'generated_by': request.user,
            'qr_code_base64': qr_code_base64,
            'report_title': f'Journal de Dette - {dette.creditor_name}',
            'has_cheque': payments.filter(mode_paiement='cheque').exists(),
            'has_virement': payments.filter(mode_paiement='virement').exists(),
            'has_especes': payments.filter(mode_paiement='especes').exists(),
            'is_completed': dette.status == 'completed',
            'completion_percentage': (total_paid / dette.original_amount * 100) if dette.original_amount > 0 else 0,
        }

        html_string = render_to_string('dettes/dette_journal.html', context)

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="dette_journal_{dette.id}_{dette.creditor_name}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'

        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(
            response,
            stylesheets=[CSS(string='@page { size: A4; margin: 1cm; }')]
        )

        return response

    except Dette.DoesNotExist:
        return Response({'detail': 'Dette not found'}, status=404)
    except Exception as e:
        return Response({'detail': f'Error generating PDF: {str(e)}'}, status=500)