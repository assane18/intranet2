from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.models import Ticket, ServiceType, TicketStatus, UserRole, TicketMessage, Materiel, Pret, Notification, User
from app import db
from datetime import datetime
import json
import os
from werkzeug.utils import secure_filename

tickets_bp = Blueprint('tickets', __name__)

def create_notification(user, message, category='info', link=None):
    """Crée une notification pour un utilisateur spécifique"""
    if user:
        n = Notification(user=user, message=message, category=category, link=link)
        db.session.add(n)

@tickets_bp.route('/new/<service_name>', methods=['GET', 'POST'])
@login_required
def new_ticket(service_name):
    try:
        service_enum = ServiceType[service_name.upper()]
    except KeyError:
        return redirect(url_for('main.user_portal'))

    if request.method == 'POST':
        category = request.form.get('category_ticket', 'Standard')
        service_dem = request.form.get('service_demandeur')
        tel_dem = request.form.get('tel_demandeur')
        lieu = request.form.get('lieu_installation_user') or request.form.get('lieu_installation_mat')

        title = request.form.get('title')
        if not title and service_name == 'DAF':
             title = f"Bon de Commande DAF - {service_dem}"

        today_str = datetime.now().strftime('%Y%m%d')
        count = Ticket.query.filter(Ticket.uid_public.like(f"{today_str}%")).count() + 1
        uid = f"{today_str}-{str(count).zfill(3)}"
        
        # Logique de validation
        is_vip = str(current_user.role) in ['MANAGER', 'ADMIN']
        status = TicketStatus.PENDING if is_vip else TicketStatus.VALIDATION
        
        # Gestion DAF
        daf_lignes = []
        daf_files = []
        if service_name == 'DAF':
            for i in range(1, 11):
                designation = request.form.get(f'daf_designation_{i}')
                if designation:
                    daf_lignes.append({
                        'designation': designation,
                        'ref': request.form.get(f'daf_ref_{i}'),
                        'qte': request.form.get(f'daf_qte_{i}'),
                        'pu': request.form.get(f'daf_pu_{i}'),
                        'total': request.form.get(f'daf_total_{i}')
                    })
            
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'tickets', uid)
            os.makedirs(upload_path, exist_ok=True)
            for i in range(1, 5):
                file = request.files.get(f'devis_{i}')
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(upload_path, filename))
                    daf_files.append(filename)

        t = Ticket(
            title=title if title else request.form.get('title'),
            description=request.form.get('description'),
            author=current_user,
            target_service=service_enum,
            status=status,
            uid_public=uid,
            category_ticket=category,
            service_demandeur=service_dem,
            tel_demandeur=tel_dem,
            lieu_installation=lieu,
            hostname=request.form.get('hostname'),
            new_user_fullname=f"{request.form.get('new_user_nom')} {request.form.get('new_user_prenom')}",
            new_user_service=request.form.get('new_user_service'),
            new_user_acces=request.form.get('new_user_acces'),
            materiel_list=request.form.get('materiel_list'),
            destinataire_materiel=request.form.get('destinataire_materiel'),
            service_destinataire=request.form.get('service_destinataire'),
            daf_lieu_livraison=request.form.get('daf_lieu_livraison'),
            daf_fournisseur_nom=request.form.get('daf_fournisseur_nom'),
            daf_fournisseur_tel=request.form.get('daf_fournisseur_tel'),
            daf_fournisseur_fax=request.form.get('daf_fournisseur_fax'),
            daf_fournisseur_email=request.form.get('daf_fournisseur_email'),
            daf_type_prix=request.form.get('daf_type_prix'),
            daf_lignes_json=json.dumps(daf_lignes),
            daf_files_json=json.dumps(daf_files)
        )
        if request.form.get('new_user_date'):
            try: t.new_user_date = datetime.strptime(request.form.get('new_user_date'), '%Y-%m-%d')
            except: pass

        db.session.add(t)
        
        # --- NOTIFICATIONS CRÉATION ---
        if status == TicketStatus.VALIDATION:
            # Notifier les Managers pour validation
            managers = User.query.filter((User.role == UserRole.MANAGER) | (User.role == UserRole.ADMIN)).all()
            for mgr in managers:
                create_notification(mgr, f"Validation requise : {uid}", 'warning', url_for('tickets.manager_dashboard'))
        else:
            # Si auto-validé (Manager/Admin), notifier les Techs du service concerné
            # On cherche tous les solvers qui sont du service cible (ou Admin)
            techs = User.query.filter(
                (User.role == UserRole.SOLVER) | (User.role == UserRole.ADMIN)
            ).all()
            
            for tech in techs:
                # Si c'est un Admin ou si c'est un Tech du bon service
                if tech.role == UserRole.ADMIN or tech.service_department == service_enum:
                    create_notification(tech, f"Nouveau ticket {service_name} : {uid}", 'info', url_for('tickets.solver_dashboard'))

        db.session.commit()
        flash(f'Demande {uid} enregistrée.', 'success')
        return redirect(url_for('main.user_portal'))

    return render_template('tickets/new_ticket.html', service=service_enum, service_name=service_name)

@tickets_bp.route('/solver/dashboard')
@login_required
def solver_dashboard():
    my_service = current_user.service_department
    if not my_service or 'ADMIN' in str(current_user.role).upper():
        tickets_pool = Ticket.query.filter(Ticket.status != TicketStatus.DONE).all()
        stock_count = Materiel.query.filter_by(statut='Disponible').count()
        prets_count = Pret.query.filter_by(statut_dossier='En cours').count()
    else:
        tickets_pool = Ticket.query.filter_by(target_service=my_service).filter(Ticket.status != TicketStatus.DONE).all()
        if 'INFORMATIQUE' in str(my_service).upper():
            stock_count = Materiel.query.filter_by(statut='Disponible').count()
            prets_count = Pret.query.filter_by(statut_dossier='En cours').count()
        else:
            stock_count = 0
            prets_count = 0

    pending_tickets = [t for t in tickets_pool if t.solver_id is None and t.status == TicketStatus.PENDING]
    pool_standard = [t for t in pending_tickets if not t.category_ticket or t.category_ticket == 'Standard']
    pool_users = [t for t in pending_tickets if t.category_ticket == 'Nouvel Utilisateur']
    pool_materiel = [t for t in pending_tickets if t.category_ticket == 'Matériel']
    pool_bons = [t for t in pending_tickets if t.category_ticket == 'Bon de Commande']
    
    mine = Ticket.query.filter_by(solver_id=current_user.id, status=TicketStatus.IN_PROGRESS).all()
    
    if not my_service or 'ADMIN' in str(current_user.role).upper():
        history = Ticket.query.filter_by(status=TicketStatus.DONE).order_by(Ticket.closed_at.desc()).limit(20).all()
    else:
        history = Ticket.query.filter_by(target_service=my_service, status=TicketStatus.DONE).order_by(Ticket.closed_at.desc()).limit(20).all()

    stats = {
        'active': len(mine),
        'done': Ticket.query.filter_by(target_service=my_service, status=TicketStatus.DONE).count() if my_service else 0,
        'pending': len(pending_tickets),
        'stock': stock_count,
        'prets': prets_count
    }

    return render_template('tickets/service_dashboard.html', 
                           stats=stats, 
                           pool_standard=pool_standard, 
                           pool_users=pool_users, 
                           pool_materiel=pool_materiel, 
                           pool_bons=pool_bons, 
                           mine=mine, 
                           history=history)

@tickets_bp.route('/view/<string:ticket_uid>', methods=['GET', 'POST'])
@login_required
def view_ticket(ticket_uid):
    ticket = Ticket.query.filter_by(uid_public=ticket_uid).first_or_404()
    
    if request.method == 'POST' and request.form.get('message'):
        msg = TicketMessage(content=request.form.get('message'), ticket=ticket, author=current_user)
        db.session.add(msg)
        
        # --- NOTIFICATION MESSAGE ---
        # Si je suis l'auteur, je notifie le technicien (s'il y en a un)
        if current_user.id == ticket.author_id:
            if ticket.solver:
                create_notification(ticket.solver, f"Nouveau message de {current_user.fullname} ({ticket.uid_public})", 'info', url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))
        # Si je suis le technicien (ou autre), je notifie l'auteur
        else:
            create_notification(ticket.author, f"Nouveau message du support ({ticket.uid_public})", 'info', url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))

        db.session.commit()
        return redirect(url_for('tickets.view_ticket', ticket_uid=ticket_uid))
        
    return render_template('tickets/detail.html', ticket=ticket)

@tickets_bp.route('/solver/take/<int:ticket_id>')
@login_required
def take_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.solver = current_user
    ticket.status = TicketStatus.IN_PROGRESS
    
    # --- NOTIFICATION PRISE EN CHARGE ---
    # Notifier le demandeur
    create_notification(ticket.author, f"Votre ticket {ticket.uid_public} est pris en charge par {current_user.fullname}.", 'success', url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))
    
    db.session.commit()
    return redirect(url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))

@tickets_bp.route('/solver/close/<int:ticket_id>')
@login_required
def close_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = TicketStatus.DONE
    ticket.closed_at = datetime.now()
    
    # --- NOTIFICATION CLOTURE ---
    # Notifier le demandeur
    create_notification(ticket.author, f"Ticket {ticket.uid_public} résolu et clôturé.", 'success', url_for('tickets.view_ticket', ticket_uid=ticket.uid_public))
    
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
    if action == 'validate': 
        t.status = TicketStatus.PENDING
        
        # --- NOTIFICATION VALIDATION ---
        # 1. Notifier le demandeur que c'est validé
        create_notification(t.author, f"Votre demande {t.uid_public} a été validée par le manager.", 'success', url_for('tickets.view_ticket', ticket_uid=t.uid_public))
        
        # 2. Notifier les techs du service concerné
        techs = User.query.filter((User.role == UserRole.SOLVER) | (User.role == UserRole.ADMIN)).all()
        for tech in techs:
            if tech.role == UserRole.ADMIN or tech.service_department == t.target_service:
                create_notification(tech, f"Nouvelle demande validée : {t.uid_public} ({t.target_service.value})", 'info', url_for('tickets.solver_dashboard'))

    elif action == 'refuse': 
        t.status = TicketStatus.REFUSED
        
        # --- NOTIFICATION REFUS ---
        # Notifier le demandeur
        create_notification(t.author, f"Demande {t.uid_public} refusée par le manager.", 'danger', url_for('tickets.view_ticket', ticket_uid=t.uid_public))
        
    db.session.commit()
    return redirect(url_for('tickets.manager_dashboard'))
    
@tickets_bp.route('/historique', methods=['GET', 'POST'])
@login_required
def historique_tickets():
    user_role = str(current_user.role).upper()
    my_service = current_user.service_department
    if request.method == 'POST':
        title = request.form.get('title')
        user_name = request.form.get('user_name')
        description = request.form.get('description')
        date_creation = request.form.get('date_creation')
        d_create = datetime.strptime(date_creation, '%Y-%m-%dT%H:%M') if date_creation else datetime.now()
        day_str = d_create.strftime('%Y%m%d')
        count = Ticket.query.filter(Ticket.uid_public.like(f"{day_str}%")).count() + 1
        uid = f"{day_str}-{str(count).zfill(3)}"
        t = Ticket(title=title, description=f"Ticket manuel pour : {user_name}\n\n{description}", author=current_user, target_service=my_service if my_service else ServiceType.INFO, status=TicketStatus.DONE, uid_public=uid, created_at=d_create, closed_at=datetime.now(), solver=current_user)
        db.session.add(t)
        db.session.commit()
        return redirect(url_for('tickets.historique_tickets'))
        
    if not my_service or 'ADMIN' in user_role:
        tickets = Ticket.query.filter_by(status=TicketStatus.DONE).order_by(Ticket.closed_at.desc()).all()
    else:
        tickets = Ticket.query.filter_by(target_service=my_service, status=TicketStatus.DONE).order_by(Ticket.closed_at.desc()).all()
    return render_template('tickets/historique_tickets.html', tickets=tickets)
