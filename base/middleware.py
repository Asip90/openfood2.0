"""Journal d'activité de l'équipe (page « Activité », owner/coadmin).

Le middleware observe les POST réussis sur les vues admin listées dans
AUDITED_ACTIONS et crée une entrée ActivityLog. Aucune vue n'a besoin
d'appeler quoi que ce soit : ajouter une vue au dict suffit à la tracer.

L'instantané de l'objet visé est pris AVANT l'exécution de la vue
(process_view), sinon une suppression ou une modification ferait perdre
l'état d'origine.
"""
import logging

logger = logging.getLogger(__name__)

# url_name -> (libellé affiché, type de cible pour l'instantané)
AUDITED_ACTIONS = {
    # Commandes
    'create_manual_order':   ("Création de commande", ""),
    'update_order':          ("Modification de commande", "order"),
    'delete_order':          ("Suppression de commande", "order"),
    'order_change_status':   ("Changement de statut", "order"),
    # Paiement
    'mark_order_paid':       ("Encaissement", "order"),
    'mark_order_unpaid':     ("Annulation d'encaissement", "order"),
    'mark_table_paid':       ("Encaissement de table", "table"),
    # Tables
    'table_create':          ("Création de table", ""),
    'table_update':          ("Modification de table", "table"),
    'table_delete':          ("Suppression de table", "table"),
    'table_toggle_active':   ("Activation/désactivation de table", "table"),
    'table_regenerate_qr':   ("Régénération QR de table", "table"),
    # Menu
    'menu_create':           ("Création de plat", ""),
    'menu_update':           ("Modification de plat", "menu"),
    'menu_delete':           ("Suppression de plat", "menu"),
    'menu_toggle_availability': ("Disponibilité de plat", "menu"),
    'create_category':       ("Création de catégorie", ""),
    'create_category_modale': ("Création de catégorie", ""),
    # Équipe
    'staff_invite':          ("Invitation d'équipier", ""),
    'staff_delete':          ("Retrait d'équipier", "staff"),
    # Restaurant / réglages
    'customization':         ("Personnalisation du thème", ""),
    'reset_customization':   ("Réinitialisation du thème", ""),
    'restaurant_settings':   ("Modification des paramètres", ""),
    'qr_settings':           ("Paramètres QR", ""),
    # Salle
    'claim_waiter_call':     ("Prise d'un appel serveur", "call"),
}

# Champs de POST jamais journalisés
_EXCLUDED_POST = ('csrf', 'password', 'token', 'key', 'secret')

ACTION_CHOICES = sorted(
    {slug: label for slug, (label, _) in AUDITED_ACTIONS.items()}.items(),
    key=lambda kv: kv[1],
)


def _order_snapshot(obj_id):
    from base.models import Order
    o = Order.objects.select_related('table').filter(id=obj_id).first()
    if not o:
        return {'target': f"Commande #{obj_id}"}
    number = (o.order_number or str(o.id))[-6:]
    return {
        'target': f"Commande #{number}",
        'amount': int(o.total or 0),
        'status_before': o.get_status_display(),
        'data': {
            'Numéro complet': o.order_number or str(o.id),
            'Table': f"Table {o.table.number}" if o.table else "À emporter",
            'Client': o.customer_name or '—',
            'Téléphone': o.customer_phone or '—',
            'Articles': ", ".join(
                f"{i.quantity}× {i.menu_item.name}"
                for i in o.items.select_related('menu_item')[:8]
            ) or '—',
            'Total': f"{int(o.total or 0)} FCFA",
            'Statut avant': o.get_status_display(),
            'Paiement avant': (
                f"Payée{' par ' + o.paid_by_name if o.paid_by_name else ''}"
                if o.is_paid else "Non payée"
            ),
            'Commande créée le': o.created_at.strftime('%d/%m/%Y %H:%M'),
        },
    }


def _table_snapshot(obj_id, url_name):
    from base.models import Table, Order
    t = Table.objects.filter(id=obj_id).first()
    if not t:
        return {'target': f"Table #{obj_id}"}
    snap = {
        'target': f"Table {t.number}",
        'data': {
            'Numéro': t.number,
            'Capacité': getattr(t, 'capacity', '') or '—',
            'Active': 'Oui' if t.is_active else 'Non',
        },
    }
    if url_name == 'mark_table_paid':
        unpaid = Order.objects.filter(
            table=t, is_paid=False,
            status__in=("pending", "confirmed", "preparing", "ready", "delivered"),
        )
        total = sum(int(o.total or 0) for o in unpaid)
        snap['amount'] = total
        snap['data']['Commandes encaissées'] = ", ".join(
            f"#{(o.order_number or str(o.id))[-6:]} ({int(o.total or 0)} FCFA)"
            for o in unpaid[:10]
        ) or '—'
        snap['data']['Total encaissé'] = f"{total} FCFA"
    return snap


def _menu_snapshot(obj_id):
    from base.models import MenuItem
    m = MenuItem.objects.select_related('category').filter(id=obj_id).first()
    if not m:
        return {'target': f"Plat #{obj_id}"}
    return {
        'target': f"Plat « {m.name} »",
        'data': {
            'Nom': m.name,
            'Catégorie': m.category.name if m.category else '—',
            'Prix': f"{int(m.price or 0)} FCFA",
            'Prix promo': f"{int(m.discount_price)} FCFA" if m.discount_price else '—',
            'Disponible avant': 'Oui' if m.is_available else 'Non',
        },
    }


def _staff_snapshot(obj_id):
    from base.models import StaffMember
    s = StaffMember.objects.select_related('user').filter(pk=obj_id).first()
    if not s:
        return {'target': f"Équipier #{obj_id}"}
    return {
        'target': f"Équipier {s.get_full_name() or s.user.email}",
        'data': {
            'Nom': s.get_full_name() or '—',
            'Email': s.user.email,
            'Rôle': s.get_role_display(),
            'Membre depuis': s.created_at.strftime('%d/%m/%Y'),
        },
    }


def _call_snapshot(obj_id):
    from base.models import WaiterCall
    c = WaiterCall.objects.select_related('table').filter(id=obj_id).first()
    if not c:
        return {'target': f"Appel #{obj_id}"}
    return {
        'target': f"Appel · Table {c.table.number}",
        'data': {
            'Table': f"Table {c.table.number}",
            'Appel reçu le': c.created_at.strftime('%d/%m/%Y %H:%M'),
        },
    }


_SNAPSHOTS = {
    'order': lambda obj_id, url_name: _order_snapshot(obj_id),
    'table': _table_snapshot,
    'menu': lambda obj_id, url_name: _menu_snapshot(obj_id),
    'staff': lambda obj_id, url_name: _staff_snapshot(obj_id),
    'call': lambda obj_id, url_name: _call_snapshot(obj_id),
}


def _clean_post(post):
    """Données envoyées, sans les champs sensibles, valeurs tronquées."""
    out = {}
    for k in list(post.keys())[:25]:
        kl = k.lower()
        if any(x in kl for x in _EXCLUDED_POST):
            continue
        v = post.get(k, '')
        if v == '':
            continue
        out[k] = v[:100]
    return out


class ActivityLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._log(request, response)
        except Exception as e:  # le journal ne doit jamais casser une requête
            logger.warning("ActivityLog error: %s", e)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Instantané AVANT la vue — l'objet peut être supprimé/modifié par elle."""
        if request.method != 'POST':
            return None
        match = getattr(request, 'resolver_match', None)
        if match is None or match.url_name not in AUDITED_ACTIONS:
            return None
        try:
            _, target_type = AUDITED_ACTIONS[match.url_name]
            if target_type and view_kwargs:
                obj_id = next(iter(view_kwargs.values()))
                request._activity_snapshot = _SNAPSHOTS[target_type](obj_id, match.url_name)
        except Exception as e:
            logger.warning("ActivityLog snapshot error: %s", e)
        return None

    def _log(self, request, response):
        if request.method != 'POST' or response.status_code >= 400:
            return
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return
        match = getattr(request, 'resolver_match', None)
        if match is None or match.url_name not in AUDITED_ACTIONS:
            return
        # request.restaurant est posé par @restaurant_required pendant la vue
        restaurant = getattr(request, 'restaurant', None)
        if restaurant is None:
            return

        url_name = match.url_name
        snapshot = getattr(request, '_activity_snapshot', None) or {}
        target = snapshot.get('target', '')
        sent = _clean_post(request.POST)

        details = self._summary(url_name, snapshot, sent)

        extra = dict(snapshot.get('data') or {})
        if sent:
            extra['Données envoyées'] = sent

        from base.models import ActivityLog
        ActivityLog.objects.create(
            restaurant=restaurant,
            user=user,
            user_name=f"{user.first_name} {user.last_name}".strip() or user.email,
            user_role=getattr(request, 'user_role', '') or '',
            action=url_name,
            target=target[:150],
            details=details[:255],
            extra=extra,
        )

    @staticmethod
    def _summary(url_name, snapshot, sent):
        """Résumé court affiché directement sous la ligne."""
        from base.models import Order
        if url_name == 'order_change_status' and sent.get('status'):
            after = dict(Order.STATUS_CHOICES).get(sent['status'], sent['status'])
            before = snapshot.get('status_before', '')
            return f"Statut : {before} → {after}" if before else f"Statut : {after}"
        if url_name in ('mark_order_paid', 'mark_table_paid') and 'amount' in snapshot:
            return f"Montant encaissé : {snapshot['amount']} FCFA"
        if url_name == 'mark_order_unpaid' and 'amount' in snapshot:
            return f"Encaissement annulé : {snapshot['amount']} FCFA"
        if url_name == 'staff_invite':
            parts = [sent.get('email', ''), sent.get('role', '')]
            return " · ".join(p for p in parts if p)
        # Générique : quelques champs envoyés parlants
        keys = ('name', 'number', 'email', 'status', 'subject')
        return " · ".join(f"{k}: {sent[k]}" for k in keys if sent.get(k))
