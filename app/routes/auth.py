from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, UserRole, ServiceType
from app import db

auth_bp = Blueprint('auth', __name__)

# --- PROFILS DE TEST (MOCK) ---
MOCK_USERS = {
    'user': {'fullname': 'Jean Utilisateur', 'role': UserRole.USER, 'department': None},
    'manager': {'fullname': 'Sophie Manager', 'role': UserRole.MANAGER, 'department': None},
    'admin': {'fullname': 'Admin Système', 'role': UserRole.ADMIN, 'department': None},
    
    # LES SERVICES QUI RECOIVENT DES BONS (SOLVERS)
    'tech_info': {'fullname': 'Assane Info', 'role': UserRole.SOLVER, 'department': ServiceType.INFO},
    'tech_daf': {'fullname': 'Reda Compta', 'role': UserRole.SOLVER, 'department': ServiceType.DAF},
    'tech_batiment': {'fullname': 'Bob Technique', 'role': UserRole.SOLVER, 'department': ServiceType.TECH},
    'tech_generaux': {'fullname': 'Marie SG', 'role': UserRole.SOLVER, 'department': ServiceType.GEN}
}

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_by_role(current_user)

    if request.method == 'POST':
        username = request.form.get('username')
        
        # LOGIQUE MOCK (Simulation AD)
        if username in MOCK_USERS:
            user = User.query.filter_by(username=username).first()
            mock_data = MOCK_USERS[username]
            
            if not user:
                user = User(username=username, email=f"{username}@local.test")
            
            # Mise à jour forcée des rôles pour le test
            user.fullname = mock_data['fullname']
            user.role = mock_data['role']
            user.service_department = mock_data['department']
            
            db.session.add(user)
            db.session.commit()
            
            login_user(user)
            return redirect_by_role(user)
        else:
            flash("Utilisateur inconnu. Utilisez les boutons de test.", "danger")

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

def redirect_by_role(user):
    """
    AIGUILLAGE PRINCIPAL :
    1. ADMIN / TECH (Solver) -> Dashboard de son service (Info, DAF...)
    2. MANAGER -> Page de Validation
    3. USER -> Portail de demandes
    """
    role = str(user.role).upper()
    
    if 'ADMIN' in role:
        # L'admin est souvent aussi un Tech Info, on l'envoie sur le Dashboard
        return redirect(url_for('tickets.solver_dashboard'))
    
    elif 'SOLVER' in role:
        # Les techniciens (DAF, Info, Tech...) vont sur leur Dashboard de gestion
        return redirect(url_for('tickets.solver_dashboard'))
    
    elif 'MANAGER' in role:
        # Les managers vont d'abord voir s'ils ont des trucs à valider
        return redirect(url_for('tickets.manager_dashboard'))
    
    else:
        # Les utilisateurs lambda vont sur le portail pour faire une demande
        return redirect(url_for('main.user_portal'))
