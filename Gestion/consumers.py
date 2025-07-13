# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import GlobalCaisse, Project

class CaisseNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Add user to general caisse notifications group
        self.group_name = 'caisse_notifications'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        
        # Send current caisse status on connection
        await self.send_current_caisse_status()

    async def disconnect(self, close_code):
        # Remove user from group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe_project':
                project_id = data.get('project_id')
                await self.subscribe_to_project(project_id)
            elif message_type == 'unsubscribe_project':
                project_id = data.get('project_id')
                await self.unsubscribe_from_project(project_id)
            elif message_type == 'get_status':
                await self.send_current_caisse_status()
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))

    async def subscribe_to_project(self, project_id):
        """Subscribe to specific project caisse notifications"""
        if project_id:
            project_group = f'project_caisse_{project_id}'
            await self.channel_layer.group_add(
                project_group,
                self.channel_name
            )
            await self.send(text_data=json.dumps({
                'type': 'subscription_success',
                'message': f'Subscribed to project {project_id} notifications'
            }))

    async def unsubscribe_from_project(self, project_id):
        """Unsubscribe from specific project caisse notifications"""
        if project_id:
            project_group = f'project_caisse_{project_id}'
            await self.channel_layer.group_discard(
                project_group,
                self.channel_name
            )
            await self.send(text_data=json.dumps({
                'type': 'unsubscription_success',
                'message': f'Unsubscribed from project {project_id} notifications'
            }))

    async def send_current_caisse_status(self):
        """Send current caisse status to client"""
        global_caisse = await self.get_global_caisse()
        await self.send(text_data=json.dumps({
            'type': 'caisse_status',
            'global_caisse': {
                'total_amount': str(global_caisse.total_amount) if global_caisse else '0.00',
                'last_updated': global_caisse.updated_at.isoformat() if global_caisse else None
            }
        }))

    # WebSocket message handlers
    async def caisse_operation(self, event):
        """Handle global caisse operation notifications"""
        await self.send(text_data=json.dumps({
            'type': 'caisse_operation',
            'operation_type': event['operation_type'],
            'amount': event['amount'],
            'description': event['description'],
            'balance_before': event['balance_before'],
            'balance_after': event['balance_after'],
            'user': event['user'],
            'timestamp': event['timestamp'],
            'project_name': event.get('project_name', None)
        }))

    async def project_caisse_operation(self, event):
        """Handle project caisse operation notifications"""
        await self.send(text_data=json.dumps({
            'type': 'project_caisse_operation',
            'project_id': event['project_id'],
            'project_name': event['project_name'],
            'operation_type': event['operation_type'],
            'amount': event['amount'],
            'description': event['description'],
            'balance_before': event['balance_before'],
            'balance_after': event['balance_after'],
            'user': event['user'],
            'timestamp': event['timestamp'],
            'proof_type': event.get('proof_type', None)
        }))

    async def caisse_transfer(self, event):
        """Handle transfers between global and project caisse"""
        await self.send(text_data=json.dumps({
            'type': 'caisse_transfer',
            'transfer_type': event['transfer_type'],  # 'to_project' or 'from_project'
            'amount': event['amount'],
            'project_id': event['project_id'],
            'project_name': event['project_name'],
            'global_balance_before': event['global_balance_before'],
            'global_balance_after': event['global_balance_after'],
            'project_balance_before': event['project_balance_before'],
            'project_balance_after': event['project_balance_after'],
            'user': event['user'],
            'timestamp': event['timestamp']
        }))

    # Database operations
    @database_sync_to_async
    def get_global_caisse(self):
        try:
            return GlobalCaisse.objects.first()
        except GlobalCaisse.DoesNotExist:
            return None

    @database_sync_to_async
    def get_project(self, project_id):
        try:
            return Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return None