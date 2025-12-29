from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Ticket, ServiceType, TicketStatus, UserRole, TicketMessage
from app import db
from datetime import datetime

tickets_bp = Blueprint('tickets', __name__)

@tickets_bp.route('/new/<service_name>', methods=['GET', 'POST'])
@login_required
def new_ticket(service_name):
    try:
        service_enum = ServiceType[service_name.upper()]
    except KeyError:
        return redirect(url_for('main.user_portal'))

    if request.method == 'POST':
        today_str = datetime.now().strftime('%Y%m%d')
        count = Ticket.query.filter(Ticket.uid_public.like(f"{today_str}%")).count() + 1
        uid = f"{today_str}-{str(count).zfill(3)}"
        
        # Les managers valident auto, les users passent en validation
        is_vip = str(current_user.role) in ['MANAGER', 'ADMIN']
        status = TicketStatus.PENDING if is_vip else TicketStatus.VALIDATION

        t = Ticket(
            title=request.form.get('title'),
            description=request.form.get('description'),
            author=current_user,
            target_service=service_enum,
            status=status,
            hostname=request.form.get('hostname'),
            uid_public=uid
        )
        db.session.add(t)
        db.session.commit()
        flash(f'Ticket {uid} créé.', 'success')
        return redirect(url_for('main.user_portal'))

    return render_template('tickets/new_ticket.html', service=service_enum, service_name=service_name)

@tickets_bp.route('/view/<string:ticket_uid>', methods=['GET', 'POST'])
@login_required
def view_ticket(ticket_uid):
    ticket = Ticket.query.filter_by(uid_public=ticket_uid).first_or_404()
    
    if request.method == 'POST' and request.form.get('message'):
        msg = TicketMessage(content=request.form.get('message'), ticket=ticket, author=current_user)
        db.session.add(msg)
        db.session.commit()
        return redirect(url_for('tickets.view_ticket', ticket_uid=ticket_uid))

    return render_template('tickets/detail.html', ticket=ticket)

# --- ROUTES DASHBOARDS ---

@tickets_bp.route('/solver/dashboard')
@login_required
def solver_dashboard():
    """
    DASHBOARD V1 RECONSTITUÉ
    Affiche : Stats, Derniers Tickets, Derniers Prêts, État Stock
    """
    # 1. Récupération des données selon le service du technicien
    my_service = current_user.service_department
    
    # Si Admin ou pas de service, on voit tout (Vue globale)
    if not my_service or 'ADMIN' in str(current_user.role):
        tickets_pool = Ticket.query.filter(Ticket.status != TicketStatus.DONE).all()
        # On suppose que Materiel et Pret sont déjà importés et utilisés
        # Pour l'instant, on met des valeurs par défaut pour éviter les erreurs si les tables sont vides
        stock_count = 0 
        prets_count = 0
        # Si les modèles sont importés, on peut faire :
        # stock_count = Materiel.query.filter_by(statut='Disponible').count()
        # prets_count = Pret.query.filter_by(statut_dossier='En cours').count()
    else:
        # Vue filtrée par service (ex: Info voit Info)
        tickets_pool = Ticket.query.filter_by(target_service=my_service).filter(Ticket.status != TicketStatus.DONE).all()
        # Seul l'info a du stock/prêts dans cette version
        if 'INFORMATIQUE' in str(my_service):
            stock_count = 0 # Placeholder
            prets_count = 0 # Placeholder
            # stock_count = Materiel.query.filter_by(statut='Disponible').count()
            # prets_count = Pret.query.filter_by(statut_dossier='En cours').count()
        else:
            stock_count = 0
            prets_count = 0

    # 2. Calcul des KPIs (Comme Dashboard V1)
    stats = {
        'nouveau': Ticket.query.filter_by(target_service=my_service, status=TicketStatus.VALIDATION).count(),
        'active': Ticket.query.filter_by(target_service=my_service, status=TicketStatus.IN_PROGRESS).count(),
        'done': Ticket.query.filter_by(target_service=my_service, status=TicketStatus.DONE).count(),
        'pending': len(tickets_pool), # Total à traiter
        'stock': stock_count,
        'prets': prets_count
    }

    # 3. Récupération des listes pour les tableaux (Limitées à 5 comme V1)
    # On sépare "File d'attente" (pool) et "Mes dossiers" (mine)
    pool = [t for t in tickets_pool if t.solver_id is None and t.status == TicketStatus.PENDING]
    mine = Ticket.query.filter_by(solver_id=current_user.id, status=TicketStatus.IN_PROGRESS).all()

    # On utilise le template V1 complet
    return render_template('tickets/service_dashboard.html', stats=stats, pool=pool, mine=mine)

@tickets_bp.route('/solver/take/<int:ticket_id>')
@login_required
def take_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.solver = current_user
    ticket.status = TicketStatus.IN_PROGRESS
    db.session.commit()
    return redirect(url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))

@tickets_bp.route('/solver/close/<int:ticket_id>')
@login_required
def close_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = TicketStatus.DONE
    ticket.closed_at = datetime.now()
    db.session.commit()
    return redirect(url_for('tickets.solver_dashboard'))

# Route Manager (Validation)
@tickets_bp.route('/manager/dashboard')
@login_required
def manager_dashboard():
    tickets = Ticket.query.filter_by(status=TicketStatus.VALIDATION).all()
    return render_template('tickets/manager_dashboard.html', tickets=tickets)

@tickets_bp.route('/manager/action/<int:ticket_id>/<action>')
@login_required
def manager_action(ticket_id, action):
    t = Ticket.query.get_or_404(ticket_id)
    if action == 'validate': t.status = TicketStatus.PENDING
    elif action == 'refuse': t.status = TicketStatus.REFUSED
    db.session.commit()
    return redirect(url_for('tickets.manager_dashboard'))
