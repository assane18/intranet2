from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Ticket, ServiceType, TicketStatus, UserRole, TicketMessage, Materiel, Pret, Notification, User
from app import db
from datetime import datetime

tickets_bp = Blueprint('tickets', __name__)

def create_notification(user, message, category='info', link=None):
    if user:
        n = Notification(user=user, message=message, category=category, link=link)
        db.session.add(n)

# --- NOUVELLE ROUTE : HISTORIQUE DES TICKETS ---
@tickets_bp.route('/historique', methods=['GET', 'POST'])
@login_required
def historique_tickets():
    # Sécurité : Accessible aux Techs et Admins
    user_role = str(current_user.role).upper()
    if 'SOLVER' not in user_role and 'ADMIN' not in user_role:
        return redirect(url_for('main.catdance'))

    my_service = current_user.service_department

    # Gestion de l'Ajout Manuel (POST)
    if request.method == 'POST':
        title = request.form.get('title')
        user_name = request.form.get('user_name') # Nom libre pour l'historique
        description = request.form.get('description')
        date_creation = request.form.get('date_creation')
        
        # Génération ID Rétroactif ou Actuel
        d_create = datetime.strptime(date_creation, '%Y-%m-%dT%H:%M') if date_creation else datetime.now()
        day_str = d_create.strftime('%Y%m%d')
        count = Ticket.query.filter(Ticket.uid_public.like(f"{day_str}%")).count() + 1
        uid = f"{day_str}-{str(count).zfill(3)}"

        # On crée un ticket directement "Terminé" ou "En cours"
        t = Ticket(
            title=title,
            description=f"Ticket créé manuellement pour : {user_name}\n\n{description}",
            author=current_user, # L'auteur technique est celui qui saisit
            target_service=my_service if my_service else ServiceType.INFO,
            status=TicketStatus.DONE, # On suppose que c'est de l'archivage
            uid_public=uid,
            created_at=d_create,
            closed_at=datetime.now(),
            solver=current_user
        )
        db.session.add(t)
        db.session.commit()
        flash(f'Ticket manuel {uid} ajouté à l\'historique.', 'success')
        return redirect(url_for('tickets.historique_tickets'))

    # Affichage : Liste des tickets TERMINÉS (DONE) pour mon service
    if not my_service or 'ADMIN' in user_role:
        tickets = Ticket.query.filter_by(status=TicketStatus.DONE).order_by(Ticket.closed_at.desc()).all()
    else:
        tickets = Ticket.query.filter_by(target_service=my_service, status=TicketStatus.DONE).order_by(Ticket.closed_at.desc()).all()

    return render_template('tickets/historique_tickets.html', tickets=tickets)

@tickets_bp.route('/new/<service_name>', methods=['GET', 'POST'])
@login_required
def new_ticket(service_name):
    try:
        service_enum = ServiceType[service_name.upper()]
    except KeyError:
        return redirect(url_for('main.user_portal'))

    if request.method == 'POST':
        category = request.form.get('category_ticket', 'Standard')
        
        # Construction intelligente du titre selon la catégorie
        if category == 'Nouvel Utilisateur':
            nom = request.form.get('new_user_nom', '')
            prenom = request.form.get('new_user_prenom', '')
            title = f"Nouvel Utilisateur : {nom} {prenom}"
            description = request.form.get('description', '') # Description optionnelle
        elif category == 'Matériel':
            dest = request.form.get('destinataire_materiel', '')
            title = f"Demande Matériel pour {dest}"
            description = request.form.get('description', '')
        else:
            title = request.form.get('title')
            description = request.form.get('description')

        # Génération ID
        today_str = datetime.now().strftime('%Y%m%d')
        count = Ticket.query.filter(Ticket.uid_public.like(f"{today_str}%")).count() + 1
        uid = f"{today_str}-{str(count).zfill(3)}"
        
        is_vip = str(current_user.role) in ['MANAGER', 'ADMIN']
        status = TicketStatus.PENDING if is_vip else TicketStatus.VALIDATION

        # Gestion date arrivée
        date_arr = None
        if request.form.get('new_user_date'):
            try:
                date_arr = datetime.strptime(request.form.get('new_user_date'), '%Y-%m-%d')
            except: pass

        t = Ticket(
            title=title,
            description=description,
            author=current_user,
            target_service=service_enum,
            status=status,
            uid_public=uid,
            category_ticket=category,
            hostname=request.form.get('hostname'),
            
            # Champs Nouvel User
            new_user_fullname=f"{request.form.get('new_user_nom')} {request.form.get('new_user_prenom')}",
            new_user_service=request.form.get('new_user_service'),
            new_user_acces=request.form.get('new_user_acces'),
            new_user_date=date_arr,
            
            # Champs Matériel
            materiel_list=request.form.get('materiel_list'),
            destinataire_materiel=request.form.get('destinataire_materiel'),
            service_destinataire=request.form.get('service_destinataire')
        )
        db.session.add(t)
        
        # Notifications
        if status == TicketStatus.VALIDATION:
            managers = User.query.filter((User.role == UserRole.MANAGER) | (User.role == UserRole.ADMIN)).all()
            for mgr in managers:
                create_notification(mgr, f"Validation : {uid} ({category})", 'warning', url_for('tickets.manager_dashboard'))
        
        db.session.commit()
        flash(f'Demande {uid} créée ({category}).', 'success')
        return redirect(url_for('main.user_portal'))

    return render_template('tickets/new_ticket.html', service=service_enum, service_name=service_name)

# ... (Le reste du fichier view_ticket, dashboards, etc. reste inchangé, copiez-le de la version précédente) ...
@tickets_bp.route('/view/<string:ticket_uid>', methods=['GET', 'POST'])
@login_required
def view_ticket(ticket_uid):
    ticket = Ticket.query.filter_by(uid_public=ticket_uid).first_or_404()
    
    if request.method == 'POST' and request.form.get('message'):
        msg = TicketMessage(content=request.form.get('message'), ticket=ticket, author=current_user)
        db.session.add(msg)
        recipient = ticket.solver if current_user.id == ticket.author_id else ticket.author
        if recipient:
            create_notification(recipient, f"Nouveau message sur {ticket.uid_public}", 'info', url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))
        db.session.commit()
        return redirect(url_for('tickets.view_ticket', ticket_uid=ticket_uid))

    return render_template('tickets/detail.html', ticket=ticket)


@tickets_bp.route('/solver/dashboard')
@login_required
def solver_dashboard():
    # ... (Logique service inchangée) ...
    my_service = current_user.service_department
    
    # Récupération de TOUS les tickets du pool (en attente)
    if not my_service or 'ADMIN' in str(current_user.role):
        all_pool = Ticket.query.filter(Ticket.status != TicketStatus.DONE).all()
        # ... compteurs stock/prêts ...
        stock_count = 0 
        prets_count = 0
    else:
        all_pool = Ticket.query.filter_by(target_service=my_service).filter(Ticket.status != TicketStatus.DONE).all()
        if 'INFORMATIQUE' in str(my_service):
            stock_count = Materiel.query.filter_by(statut='Disponible').count()
            prets_count = Pret.query.filter_by(statut_dossier='En cours').count()
        else:
            stock_count = 0
            prets_count = 0

    # SÉPARATION PAR CATÉGORIE (Pour l'affichage "Gros Plan")
    # On filtre ceux qui n'ont pas de technicien (solver_id is None) ET qui sont PENDING
    pending_tickets = [t for t in all_pool if t.solver_id is None and t.status == TicketStatus.PENDING]
    
    pool_standard = [t for t in pending_tickets if not t.category_ticket or t.category_ticket == 'Standard']
    pool_users = [t for t in pending_tickets if t.category_ticket == 'Nouvel Utilisateur']
    pool_materiel = [t for t in pending_tickets if t.category_ticket == 'Matériel']
    
    # Mes dossiers (ceux que je traite déjà)
    mine = Ticket.query.filter_by(solver_id=current_user.id, status=TicketStatus.IN_PROGRESS).all()

    stats = {
        'nouveau': Ticket.query.filter_by(target_service=my_service, status=TicketStatus.VALIDATION).count(),
        'active': len(mine),
        'done': Ticket.query.filter_by(target_service=my_service, status=TicketStatus.DONE).count(),
        'pending': len(pending_tickets),
        'stock': stock_count,
        'prets': prets_count
    }

    return render_template('tickets/service_dashboard.html', 
                           stats=stats, 
                           pool_standard=pool_standard,
                           pool_users=pool_users,
                           pool_materiel=pool_materiel,
                           mine=mine)


@tickets_bp.route('/solver/take/<int:ticket_id>')
@login_required
def take_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.solver = current_user
    ticket.status = TicketStatus.IN_PROGRESS
    create_notification(ticket.author, f"Ticket {ticket.uid_public} pris en charge.", 'success', url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))
    db.session.commit()
    return redirect(url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))

@tickets_bp.route('/solver/close/<int:ticket_id>')
@login_required
def close_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = TicketStatus.DONE
    ticket.closed_at = datetime.now()
    create_notification(ticket.author, f"Ticket {ticket.uid_public} clôturé.", 'success', url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))
    db.session.commit()
    return redirect(url_for('tickets.solver_dashboard'))

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
    elif action == 'refuse': 
        t.status = TicketStatus.REFUSED
        create_notification(t.author, f"Refus ticket {t.uid_public}", 'danger', url_for('tickets.view_ticket', ticket_uid=t.uid_public))
    db.session.commit()
    return redirect(url_for('tickets.manager_dashboard'))
