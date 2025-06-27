from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.template.loader import render_to_string
from django.conf import settings
from .models import (
    GlobalCaisse, Project, Product, BonDeLivraison, 
    BonDeLivraisonItem, AdditionalCharge, BonLivraisonHistory
)
import json
import os
from datetime import datetime
import weasyprint
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, permission_classes, parser_classes
# Global Caisse Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def global_caisse_get(request):
    """Get global caisse information"""
    caisse = GlobalCaisse.objects.first()
    if not caisse:
        caisse = GlobalCaisse.objects.create()
    return Response({
        'id': caisse.id,
        'total_amount': caisse.total_amount,
        'created_at': caisse.created_at,
        'updated_at': caisse.updated_at
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def global_caisse_update(request):
    """Update global caisse amount"""
    caisse = GlobalCaisse.objects.first()
    if not caisse:
        caisse = GlobalCaisse.objects.create()
    
    new_amount = request.data.get('total_amount')
    if new_amount is not None:
        caisse.total_amount = new_amount
        caisse.save()
    
    return Response({
        'id': caisse.id,
        'total_amount': caisse.total_amount,
        'updated_at': caisse.updated_at
    })

# Project Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_list(request):
    """Get list of all projects"""
    projects = Project.objects.select_related('created_by').all()
    data = []
    for project in projects:
        data.append({
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'contract_file': project.contract_file.url if project.contract_file else None,
            'estimated_cost': project.estimated_cost,
            'duration_days': project.duration_days,
            'actual_spent': project.actual_spent,
            'created_by': {
                'id': project.created_by.id,
                'username': project.created_by.username,
                'full_name': f"{project.created_by.first_name} {project.created_by.last_name}".strip()
            } if project.created_by else None,
            'created_at': project.created_at,
            'updated_at': project.updated_at
        })
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def project_create(request):
    project = Project.objects.create(
        name=request.data.get('name'),
        description=request.data.get('description'),
        contract_file=request.FILES.get('contract_file'),
        estimated_cost=request.data.get('estimated_cost'),
        duration_days=request.data.get('duration_days'),
        created_by=request.user
    )
    
    return Response({
        'id': project.id,
        'name': project.name,
        'description': project.description,
        'contract_file': project.contract_file.url if project.contract_file else None,
        'estimated_cost': project.estimated_cost,
        'duration_days': project.duration_days,
        'actual_spent': project.actual_spent,
        'created_by': {
            'id': project.created_by.id,
            'username': project.created_by.username,
            'full_name': f"{project.created_by.first_name} {project.created_by.last_name}".strip()
        },
        'created_at': project.created_at
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_detail(request, pk):
    """Get project details"""
    project = get_object_or_404(Project, pk=pk)
    
    return Response({
        'id': project.id,
        'name': project.name,
        'description': project.description,
        'contract_file': project.contract_file.url if project.contract_file else None,
        'estimated_cost': project.estimated_cost,
        'duration_days': project.duration_days,
        'actual_spent': project.actual_spent,
        'created_by': {
            'id': project.created_by.id,
            'username': project.created_by.username,
            'full_name': f"{project.created_by.first_name} {project.created_by.last_name}".strip()
        } if project.created_by else None,
        'created_at': project.created_at,
        'updated_at': project.updated_at
    })

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])  # Add this line
def project_update(request, pk):
    """Update project details - only update provided fields"""
    try:
        project = get_object_or_404(Project, pk=pk)
        updated_fields = []
        
        # Now request.data will work properly with FormData
        if 'name' in request.data and request.data.get('name'):
            project.name = request.data.get('name')
            updated_fields.append('name')
        
        if 'description' in request.data:
            project.description = request.data.get('description')
            updated_fields.append('description')
        
        if request.FILES.get('contract_file'):
            project.contract_file = request.FILES.get('contract_file')
            updated_fields.append('contract_file')
        
        if 'estimated_cost' in request.data and request.data.get('estimated_cost'):
            try:
                project.estimated_cost = float(request.data.get('estimated_cost'))
                updated_fields.append('estimated_cost')
            except (ValueError, TypeError):
                return Response({'error': 'Invalid estimated_cost value'}, status=400)
        
        if 'duration_days' in request.data and request.data.get('duration_days'):
            try:
                project.duration_days = int(request.data.get('duration_days'))
                updated_fields.append('duration_days')
            except (ValueError, TypeError):
                return Response({'error': 'Invalid duration_days value'}, status=400)
        
        if updated_fields:
            project.save(update_fields=updated_fields + ['updated_at'])
        
        return Response({
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'contract_file': project.contract_file.url if project.contract_file else None,
            'estimated_cost': project.estimated_cost,
            'duration_days': project.duration_days,
            'actual_spent': project.actual_spent,
            'updated_at': project.updated_at
        })
        
    except Exception as e:
        print(f"Error in project_update: {str(e)}")
        return Response({'error': str(e)}, status=500)
    
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def project_delete(request, pk):
    """Delete a project"""
    project = get_object_or_404(Project, pk=pk)
    project.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_bl_history(request, pk):
    """Get Bon de Livraison history for a project"""
    project = get_object_or_404(Project, pk=pk)
    
    # Get BL history
    history = BonLivraisonHistory.objects.filter(project=project).select_related('user', 'bon_de_livraison')
    
    data = []
    for entry in history:
        data.append({
            'id': entry.id,
            'bl_number': entry.bl_number,
            'action': entry.action,
            'action_display': entry.get_action_display(),
            'user': {
                'id': entry.user.id,
                'username': entry.user.username,
                'full_name': f"{entry.user.first_name} {entry.user.last_name}".strip()
            } if entry.user else None,
            'description': entry.description,
            'created_at': entry.created_at,
            'bon_de_livraison_id': entry.bon_de_livraison.id if entry.bon_de_livraison else None
        })
    
    return Response(data)

# Product Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_list(request):
    """Get list of all products"""
    products = Product.objects.all()
    data = []
    for product in products:
        data.append({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'created_at': product.created_at
        })
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def product_create(request):
    """Create a new product"""
    product = Product.objects.create(
        name=request.data.get('name'),
        description=request.data.get('description', '')
    )
    
    return Response({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'created_at': product.created_at
    }, status=status.HTTP_201_CREATED)

# Bon de Livraison Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bon_de_livraison_list(request):
    """Get list of all bon de livraison with optional project filter"""
    project_id = request.GET.get('project_id')
    print(f"Project ID filter: {project_id}")
    if project_id:
        bons = BonDeLivraison.objects.filter(project_id=project_id).select_related('created_by', 'pdf_generated_by', 'project')
    else:
        bons = BonDeLivraison.objects.select_related('created_by', 'pdf_generated_by', 'project').all()
    
    data = []
    for bon in bons:
        items_data = []
        for item in bon.items.all():
            items_data.append({
                'id': item.id,
                'product_id': item.product.id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'total_price': item.total_price
            })
        
        charges_data = []
        for charge in bon.additional_charges.all():
            charges_data.append({
                'id': charge.id,
                'description': charge.description,
                'amount': charge.amount
            })
        
        data.append({
            'id': bon.id,
            'bl_number': bon.bl_number,
            'project_id': bon.project.id,
            'project_name': bon.project.name,
            'origin_address': bon.origin_address,
            'destination_address': bon.destination_address,
            'description': bon.description,
            'payment_method': bon.payment_method,
            'payment_proof': bon.payment_proof.url if bon.payment_proof else None,
            'additional_charges': charges_data,
            'total_amount': bon.total_amount,
            'items': items_data,
            'created_by': {
                'id': bon.created_by.id,
                'username': bon.created_by.username,
                'full_name': f"{bon.created_by.first_name} {bon.created_by.last_name}".strip()
            } if bon.created_by else None,
            'pdf_generated_by': {
                'id': bon.pdf_generated_by.id,
                'username': bon.pdf_generated_by.username,
                'full_name': f"{bon.pdf_generated_by.first_name} {bon.pdf_generated_by.last_name}".strip()
            } if bon.pdf_generated_by else None,
            'has_pdf': bon.has_pdf(),
            'pdf_generated_at': bon.pdf_generated_at,
            'created_at': bon.created_at,
            'updated_at': bon.updated_at
        })
    return Response(data)

from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, permission_classes, parser_classes
import json

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])  # Add this line
def bon_de_livraison_create(request,pk):
    """Create a new bon de livraison"""
    project_id = Project.objects.filter(id=pk).first()
    try:
        bon = BonDeLivraison.objects.create(
            project_id=project_id.pk,
            origin_address=request.data.get('origin_address'),
            destination_address=request.data.get('destination_address'),
            description=request.data.get('description', ''),
            payment_method=request.data.get('payment_method'),
            payment_proof=request.FILES.get('payment_proof'),
            created_by=request.user
        )
         
        items_data = request.data.get('items', [])
        if isinstance(items_data, str):
            items_data = json.loads(items_data)
        
        for item_data in items_data:
            BonDeLivraisonItem.objects.create(
                bon_de_livraison=bon,
                product_id=item_data.get('product_id'),
                quantity=item_data.get('quantity'),
                unit_price=item_data.get('unit_price'),
                total_price=item_data.get('total_price')
            )
        
        charges_data = request.data.get('additional_charges', [])
        if isinstance(charges_data, str):
            charges_data = json.loads(charges_data)
        
        for charge_data in charges_data:
            AdditionalCharge.objects.create(
                bon_de_livraison=bon,
                description=charge_data.get('description'),
                amount=charge_data.get('amount')
            )
        
        # Update total amount
        bon.total_amount = bon.calculate_total()
        bon.save()
        
        # Update project actual spent
        project = bon.project
        project.actual_spent += bon.total_amount
        project.save()
        
        # Update global caisse
        caisse = GlobalCaisse.objects.first()
        if caisse:
            caisse.total_amount -= bon.total_amount
            caisse.save()
        
        # Create history entry
        BonLivraisonHistory.objects.create(
            project=bon.project,
            bon_de_livraison=bon,
            bl_number=bon.bl_number,
            action='created',
            user=request.user,
            description=f"Bon de Livraison created with {bon.items.count()} items"
        )
        
        return Response({
            'id': bon.id,
            'bl_number': bon.bl_number,
            'project_id': bon.project.id,
            'total_amount': bon.total_amount,
            'created_at': bon.created_at
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"Error in bon_de_livraison_create: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bon_de_livraison_detail(request, pk):
    """Get bon de livraison details"""
    bon = get_object_or_404(BonDeLivraison, pk=pk)
    
    items_data = []
    for item in bon.items.all():
        items_data.append({
            'id': item.id,
            'product_id': item.product.id,
            'product_name': item.product.name,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price
        })
    
    charges_data = []
    for charge in bon.additional_charges.all():
        charges_data.append({
            'id': charge.id,
            'description': charge.description,
            'amount': charge.amount
        })
    
    return Response({
        'id': bon.id,
        'bl_number': bon.bl_number,
        'project_id': bon.project.id,
        'project_name': bon.project.name,
        'origin_address': bon.origin_address,
        'destination_address': bon.destination_address,
        'description': bon.description,
        'payment_method': bon.payment_method,
        'payment_proof': bon.payment_proof.url if bon.payment_proof else None,
        'additional_charges': charges_data,
        'total_amount': bon.total_amount,
        'items': items_data,
        'created_by': {
            'id': bon.created_by.id,
            'username': bon.created_by.username,
            'full_name': f"{bon.created_by.first_name} {bon.created_by.last_name}".strip()
        } if bon.created_by else None,
        'pdf_generated_by': {
            'id': bon.pdf_generated_by.id,
            'username': bon.pdf_generated_by.username,
            'full_name': f"{bon.pdf_generated_by.first_name} {bon.pdf_generated_by.last_name}".strip()
        } if bon.pdf_generated_by else None,
        'has_pdf': bon.has_pdf(),
        'pdf_generated_at': bon.pdf_generated_at,
        'created_at': bon.created_at,
        'updated_at': bon.updated_at
    })

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def bon_de_livraison_delete(request, pk):
    """Delete a bon de livraison"""
    bon = get_object_or_404(BonDeLivraison, pk=pk)
    old_total = bon.total_amount
    project = bon.project
    bl_number = bon.bl_number
    
    # Update project actual spent
    project.actual_spent -= old_total
    project.save()
    
    # Update global caisse
    caisse = GlobalCaisse.objects.first()
    if caisse:
        caisse.total_amount += old_total
        caisse.save()
    
    # Create history entry before deletion
    BonLivraisonHistory.objects.create(
        project=project,
        bon_de_livraison=None,  # Will be null after deletion
        bl_number=bl_number,
        action='deleted',
        user=request.user,
        description=f"Bon de Livraison deleted (Amount: {old_total})"
    )
    
    bon.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)

# PDF Generation Views
@api_view(['POST'])
def generate_bl_pdf(request, pk):
    """Generate PDF for Bon de Livraison"""
    bon = get_object_or_404(BonDeLivraison, pk=pk)
    
    try:
        # Prepare context for template
        context = {
            'bon': bon,
            'project': bon.project,
            'items': bon.items.select_related('product').all(),
            'charges': bon.additional_charges.all(),
            'created_by': bon.created_by,
            'pdf_generated_by': request.user,
            'generation_date': datetime.now(),
        }
        
        # Render HTML template
        html_string = render_to_string('BL\pdf_template.html', context)
        
        # Generate PDF
        font_config = FontConfiguration()
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        
        # Create CSS for better PDF styling
        css = CSS(string='''
            @page {
                size: A4;
                margin: 1cm;
            }
            body {
                font-family: Arial, sans-serif;
                font-size: 12px;
            }
        ''', font_config=font_config)
        
        pdf = html.write_pdf(stylesheets=[css], font_config=font_config)
        
        # Save PDF file
        pdf_filename = bon.get_pdf_filename()
        pdf_path = os.path.join(settings.MEDIA_ROOT, 'bon_livraison_pdfs', str(bon.project.id))
        
        # Create directory if it doesn't exist
        os.makedirs(pdf_path, exist_ok=True)
        
        full_pdf_path = os.path.join(pdf_path, pdf_filename)
        
        with open(full_pdf_path, 'wb') as f:
            f.write(pdf)
        
        # Update bon with PDF info
        relative_path = os.path.join('bon_livraison_pdfs', str(bon.project.id), pdf_filename)
        bon.pdf_file = relative_path
        bon.pdf_generated_by = request.user
        bon.pdf_generated_at = datetime.now()
        bon.save()
        
        # Create history entry
        BonLivraisonHistory.objects.create(
            project=bon.project,
            bon_de_livraison=bon,
            bl_number=bon.bl_number,
            action='pdf_generated',
            user=request.user,
            description=f"PDF generated by {request.user.username}"
        )
        
        return Response({
            'message': 'PDF generated successfully',
            'pdf_url': bon.pdf_file.url,
            'generated_at': bon.pdf_generated_at,
            'generated_by': request.user.username
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to generate PDF: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_bl_pdf(request, pk):
    """Download PDF for Bon de Livraison"""
    bon = get_object_or_404(BonDeLivraison, pk=pk)
    
    if not bon.has_pdf():
        return Response({
            'error': 'PDF not found. Please generate PDF first.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    try:
        # Create history entry for download
        BonLivraisonHistory.objects.create(
            project=bon.project,
            bon_de_livraison=bon,
            bl_number=bon.bl_number,
            action='pdf_downloaded',
            user=request.user,
            description=f"PDF downloaded by {request.user.username}"
        )
        
        # Return file response
        with open(bon.pdf_file.path, 'rb') as pdf_file:
            response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{bon.get_pdf_filename()}"'
            return response
            
    except Exception as e:
        return Response({
            'error': f'Failed to download PDF: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)