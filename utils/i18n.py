"""
Tiny i18n helper for API responses.

Frontend sends `X-User-Lang: fr|ar` (and `Accept-Language` as fallback).
Use `tr(request, fr_text, ar_text)` in views to return the right one.
"""


def get_lang(request):
    """Return 'fr' or 'ar' based on request headers."""
    if request is None:
        return 'fr'
    lang = request.META.get('HTTP_X_USER_LANG') or ''
    if not lang:
        accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        lang = accept.split(',')[0].split(';')[0].split('-')[0].strip().lower()
    return 'ar' if lang.startswith('ar') else 'fr'


def tr(request, fr_text, ar_text=None):
    """Return the right message based on the user's language."""
    if get_lang(request) == 'ar' and ar_text:
        return ar_text
    return fr_text


# ─── Common message dictionary (used across views) ─────────────────────────
M = {
    # Generic
    'created':           {'fr': 'Créé avec succès.',           'ar': 'تم الإنشاء بنجاح.'},
    'updated':           {'fr': 'Mis à jour avec succès.',     'ar': 'تم التحديث بنجاح.'},
    'deleted':           {'fr': 'Supprimé avec succès.',       'ar': 'تم الحذف بنجاح.'},
    'not_found':         {'fr': 'Ressource introuvable.',      'ar': 'المورد غير موجود.'},
    'forbidden':         {'fr': "Action réservée aux administrateurs.",
                          'ar': 'هذا الإجراء مخصص للمسؤولين فقط.'},
    'invalid_data':      {'fr': 'Données invalides.',          'ar': 'بيانات غير صالحة.'},
    'required_fields':   {'fr': 'Champs requis manquants.',    'ar': 'حقول مطلوبة مفقودة.'},
    'invalid_amount':    {'fr': 'Montant invalide.',           'ar': 'مبلغ غير صالح.'},
    'amount_positive':   {'fr': 'Le montant doit être positif.',
                          'ar': 'يجب أن يكون المبلغ موجباً.'},
    'invalid_date':      {'fr': 'Date invalide. Utilisez le format AAAA-MM-JJ.',
                          'ar': 'تاريخ غير صالح. استخدم الصيغة YYYY-MM-DD.'},
    'server_error':      {'fr': 'Une erreur est survenue.',    'ar': 'حدث خطأ.'},

    # Auth
    'username_password_group_required': {
        'fr': 'Nom d\'utilisateur, mot de passe et rôle sont requis.',
        'ar': 'اسم المستخدم وكلمة المرور والدور مطلوبة.'
    },
    'invalid_group': {
        'fr': 'Rôle invalide.',
        'ar': 'الدور غير صالح.'
    },
    'username_exists': {
        'fr': 'Ce nom d\'utilisateur existe déjà.',
        'ar': 'اسم المستخدم موجود مسبقاً.'
    },
    'group_not_found': {
        'fr': 'Ce groupe n\'existe pas.',
        'ar': 'هذا الدور غير موجود.'
    },
    'user_created': {
        'fr': 'Utilisateur créé avec succès.',
        'ar': 'تم إنشاء المستخدم بنجاح.'
    },
    'user_updated': {
        'fr': 'Utilisateur mis à jour avec succès.',
        'ar': 'تم تحديث المستخدم بنجاح.'
    },
    'user_deleted': {
        'fr': 'Utilisateur supprimé avec succès.',
        'ar': 'تم حذف المستخدم بنجاح.'
    },
    'user_activated': {
        'fr': 'Utilisateur activé.',
        'ar': 'تم تفعيل المستخدم.'
    },
    'user_deactivated': {
        'fr': 'Utilisateur désactivé.',
        'ar': 'تم تعطيل المستخدم.'
    },
    'cannot_delete_self': {
        'fr': 'Vous ne pouvez pas supprimer votre propre compte.',
        'ar': 'لا يمكنك حذف حسابك الخاص.'
    },
    'profile_not_found': {
        'fr': 'Profil utilisateur introuvable.',
        'ar': 'الملف الشخصي غير موجود.'
    },
    'profile_updated': {
        'fr': 'Profil mis à jour avec succès.',
        'ar': 'تم تحديث الملف الشخصي بنجاح.'
    },
    'password_too_short': {
        'fr': 'Le mot de passe doit contenir au moins 6 caractères.',
        'ar': 'يجب أن تحتوي كلمة المرور على 6 أحرف على الأقل.'
    },
    'invalid_credentials': {
        'fr': 'Identifiant ou mot de passe incorrect.',
        'ar': 'اسم المستخدم أو كلمة المرور غير صحيحة.'
    },
    'account_inactive': {
        'fr': "Ce compte n'est pas actif.",
        'ar': 'هذا الحساب غير نشط.'
    },

    # Caisse
    'caisse_op_created':    {'fr': 'Opération enregistrée avec succès.',
                             'ar': 'تم تسجيل العملية بنجاح.'},
    'encaissement_done':    {'fr': 'Encaissement effectué avec succès.',
                             'ar': 'تم الإيداع بنجاح.'},
    'decaissement_done':    {'fr': 'Décaissement effectué avec succès.',
                             'ar': 'تم السحب بنجاح.'},
    'insufficient_balance': {'fr': 'Solde insuffisant.',
                             'ar': 'رصيد غير كاف.'},
    'project_id_required':  {'fr': 'Projet requis.',
                             'ar': 'المشروع مطلوب.'},
    'observation_required': {'fr': 'Une observation est requise pour la source "autre".',
                             'ar': 'الملاحظة مطلوبة عند اختيار المصدر "أخرى".'},
    'op_updated':           {'fr': 'Opération mise à jour. Solde recalculé.',
                             'ar': 'تم تحديث العملية. أُعيد حساب الرصيد.'},
    'op_deleted':           {'fr': 'Opération supprimée. Solde recalculé.',
                             'ar': 'تم حذف العملية. أُعيد حساب الرصيد.'},
    'op_linked_to_dette':   {'fr': 'Cette opération est liée à un paiement de dette. Modifiez-la via la gestion des dettes.',
                             'ar': 'هذه العملية مرتبطة بدفعة دين. عدّلها من إدارة الديون.'},
    'op_delete_linked':     {'fr': 'Cette opération est liée à un paiement de dette. Supprimez-la via la gestion des dettes.',
                             'ar': 'هذه العملية مرتبطة بدفعة دين. احذفها من إدارة الديون.'},

    # Projects
    'project_created':      {'fr': 'Projet créé avec succès.',     'ar': 'تم إنشاء المشروع بنجاح.'},
    'project_updated':      {'fr': 'Projet mis à jour avec succès.', 'ar': 'تم تحديث المشروع بنجاح.'},
    'project_not_found':    {'fr': 'Projet introuvable.',           'ar': 'المشروع غير موجود.'},

    # Dettes
    'dette_created':        {'fr': 'Dette créée avec succès.',      'ar': 'تم إنشاء الدين بنجاح.'},
    'payment_recorded':     {'fr': 'Paiement enregistré.',          'ar': 'تم تسجيل الدفعة.'},
    'dette_already_paid':   {'fr': 'Cette dette est déjà soldée.',  'ar': 'هذا الدين مسدّد بالفعل.'},
    'payment_exceeds':      {'fr': 'Le montant payé dépasse le restant.',
                             'ar': 'المبلغ المدفوع يتجاوز المتبقي.'},
    'dette_not_found':      {'fr': 'Dette introuvable.',            'ar': 'الدين غير موجود.'},

    # BL / BC / Missions
    'bl_created':           {'fr': 'Bon de livraison créé.',        'ar': 'تم إنشاء وصل التسليم.'},
    'bl_updated':           {'fr': 'Bon de livraison mis à jour.',  'ar': 'تم تحديث وصل التسليم.'},
    'bl_deleted':           {'fr': 'Bon de livraison supprimé.',    'ar': 'تم حذف وصل التسليم.'},
    'bc_created':           {'fr': 'Bon de commande créé.',         'ar': 'تم إنشاء أمر الشراء.'},
    'bc_updated':           {'fr': 'Bon de commande mis à jour.',   'ar': 'تم تحديث أمر الشراء.'},
    'bc_deleted':           {'fr': 'Bon de commande supprimé.',     'ar': 'تم حذف أمر الشراء.'},
    'mission_created':      {'fr': 'Ordre de mission créé.',        'ar': 'تم إنشاء أمر المهمة.'},
    'mission_updated':      {'fr': 'Ordre de mission mis à jour.',  'ar': 'تم تحديث أمر المهمة.'},
    'mission_deleted':      {'fr': 'Ordre de mission supprimé.',    'ar': 'تم حذف أمر المهمة.'},

    # Revenus / Accréances
    'revenu_created':       {'fr': 'Accréance créée avec succès.',  'ar': 'تم إنشاء الاعتماد بنجاح.'},
    'revenu_deleted':       {'fr': 'Accréance supprimée.',          'ar': 'تم حذف الاعتماد.'},
    'revenu_code_exists':   {'fr': 'Ce code d\'accréance existe déjà.',
                             'ar': 'رمز الاعتماد هذا موجود مسبقاً.'},
    'insufficient_budget':  {'fr': 'Budget insuffisant.',           'ar': 'الميزانية غير كافية.'},
}


def msg(request, key, fallback=None):
    """Look up a translated message by key. Returns the right language version."""
    entry = M.get(key)
    if not entry:
        return fallback or key
    return entry['ar'] if get_lang(request) == 'ar' else entry['fr']
