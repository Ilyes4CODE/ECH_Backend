# Updated signals.py with French messages
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import CaisseOperation, ProjectCaisseOperation
import json

channel_layer = get_channel_layer()

def get_operation_message_fr(operation_type, amount, project_name=None):
    """Get French operation message"""
    messages = {
        'encaissement': f"Encaissement de {amount} DA",
        'decaissement': f"Décaissement de {amount} DA",
        'transfer_to_project': f"Transfert vers le projet '{project_name}' de {amount} DA",
        'transfer_from_project': f"Transfert depuis le projet '{project_name}' de {amount} DA",
        'receive_from_global': f"Réception depuis la caisse globale de {amount} DA",
        'receive_from_project': f"Réception depuis le projet '{project_name}' de {amount} DA"
    }
    return messages.get(operation_type, f"Opération de {amount} DA")

@receiver(post_save, sender=CaisseOperation)
def notify_caisse_operation(sender, instance, created, **kwargs):
    """Send notification when a global caisse operation is created"""
    if created:
        # Determine notification type based on operation
        notification_data = {
            'type': 'caisse_operation',
            'operation_type': instance.operation_type,
            'amount': str(instance.amount),
            'description': instance.description,
            'balance_before': str(instance.balance_before),
            'balance_after': str(instance.balance_after),
            'user': instance.user.username if instance.user else 'Système',
            'timestamp': instance.created_at.isoformat(),
            'message': get_operation_message_fr(
                instance.operation_type, 
                instance.amount, 
                instance.project.name if instance.project else None
            )
        }
        
        # Add project name if it's a transfer operation
        if instance.project:
            notification_data['project_name'] = instance.project.name
        
        # Send to general caisse notifications group
        async_to_sync(channel_layer.group_send)(
            'caisse_notifications',
            notification_data
        )

@receiver(post_save, sender=ProjectCaisseOperation)
def notify_project_caisse_operation(sender, instance, created, **kwargs):
    """Send notification when a project caisse operation is created"""
    if created:
        notification_data = {
            'type': 'project_caisse_operation',
            'project_id': instance.project.id,
            'project_name': instance.project.name,
            'operation_type': instance.operation_type,
            'amount': str(instance.amount),
            'description': instance.description,
            'balance_before': str(instance.balance_before),
            'balance_after': str(instance.balance_after),
            'user': instance.user.username if instance.user else 'Système',
            'timestamp': instance.created_at.isoformat(),
            'message': f"Opération sur le projet '{instance.project.name}': {get_operation_message_fr(instance.operation_type, instance.amount)}"
        }
        
        if instance.preuve_type:
            notification_data['proof_type'] = instance.preuve_type
        
        # Send to general caisse notifications group
        async_to_sync(channel_layer.group_send)(
            'caisse_notifications',
            notification_data
        )
        
        # Also send to specific project subscribers
        async_to_sync(channel_layer.group_send)(
            f'project_caisse_{instance.project.id}',
            notification_data
        )

def send_transfer_notification(from_type, to_type, amount, project, user, 
                             global_balance_before, global_balance_after,
                             project_balance_before, project_balance_after,
                             timestamp=None):
    """Send notification for transfers between global and project caisse"""
    transfer_type = 'to_project' if from_type == 'global' else 'from_project'
    
    # Create French message based on transfer direction
    if transfer_type == 'to_project':
        message = f"Transfert de {amount} DA vers le projet '{project.name}'"
    else:
        message = f"Transfert de {amount} DA du projet '{project.name}' vers la caisse globale"
    
    notification_data = {
        'type': 'caisse_transfer',
        'transfer_type': transfer_type,
        'amount': str(amount),
        'project_id': project.id,
        'project_name': project.name,
        'global_balance_before': str(global_balance_before),
        'global_balance_after': str(global_balance_after),
        'project_balance_before': str(project_balance_before),
        'project_balance_after': str(project_balance_after),
        'user': user.username if user else 'Système',
        'timestamp': timestamp.isoformat() if timestamp else None,
        'message': message
    }
    
    # Send to general caisse notifications group
    async_to_sync(channel_layer.group_send)(
        'caisse_notifications',
        notification_data
    )
    
    # Also send to specific project subscribers
    async_to_sync(channel_layer.group_send)(
        f'project_caisse_{project.id}',
        notification_data
    )