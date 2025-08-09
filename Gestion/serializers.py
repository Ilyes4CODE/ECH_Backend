from rest_framework import serializers
from .models import Project, CaisseHistory, CaisseOperation, Revenu, User,Dette

class UserBasicSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() if obj.first_name or obj.last_name else None

class DetteBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dette  # You'll need to import this
        fields = ['id', 'nom_crediteur']

class CaisseOperationDetailSerializer(serializers.ModelSerializer):
    dette = DetteBasicSerializer(read_only=True)
    has_preuve = serializers.SerializerMethodField()
    
    class Meta:
        model = CaisseOperation
        fields = [
            'id', 'operation_type', 'mode_paiement', 'nom_fournisseur', 
            'banque', 'numero_cheque', 'income_source', 'observation',
            'by_collaborator', 'dette', 'has_preuve'
        ]
    
    def get_has_preuve(self, obj):
        return bool(obj.preuve_file)

class CaisseHistorySerializer(serializers.ModelSerializer):
    operation = CaisseOperationDetailSerializer(read_only=True)
    user = UserBasicSerializer(read_only=True)
    is_collaborator = serializers.SerializerMethodField()
    is_dette = serializers.SerializerMethodField()
    
    class Meta:
        model = CaisseHistory
        fields = [
            'id', 'numero', 'action', 'amount', 'balance_before', 
            'balance_after', 'description', 'date', 'created_at',
            'operation', 'user', 'is_collaborator', 'is_dette'
        ]
    
    def get_is_collaborator(self, obj):
        return obj.operation.by_collaborator if obj.operation else False
    
    def get_is_dette(self, obj):
        return bool(obj.operation.dette) if obj.operation else False

class RevenuSerializer(serializers.ModelSerializer):
    created_by = UserBasicSerializer(read_only=True)
    has_pdf = serializers.SerializerMethodField()
    
    class Meta:
        model = Revenu
        fields = [
            'id', 'revenu_code', 'montant', 'date', 'created_at',
            'created_by', 'has_pdf'
        ]
    
    def get_has_pdf(self, obj):
        return bool(obj.pdf_file)

class ProjectBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'collaborator_name', 'estimated_budget',
            'total_depenses', 'total_accreance', 'total_benefices'
        ]

class ProjectHistorySerializer(serializers.Serializer):
    project = ProjectBasicSerializer(read_only=True)
    period = serializers.DictField(read_only=True)
    summary = serializers.DictField(read_only=True)
    history = CaisseHistorySerializer(many=True, read_only=True)
    revenus = RevenuSerializer(many=True, read_only=True)
