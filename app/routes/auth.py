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
    'tech_info': {'fullname': 'Salim Info', 'role': UserRole.SOLVER, 'department': ServiceType.INFO},
    'tech_daf': {'fullname': 'Reda Compta', 'role': UserRole.SOLVER, 'department': ServiceType.DAF}
}

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_by_role(current_user)

    if request.method == 'POST':
        username = request.form.get('username')
        
        # LOGIQUE MOCK SIMPLIFIÉE
        if username in MOCK_USERS:
            user = User.query.filter_by(username=username).first()
            mock_data = MOCK_USERS[username]
            
            if not user:
                user = User(username=username, email=f"{username}@local.test")
            
            # Mise à jour des rôles pour être sûr
            user.fullname = mock_data['fullname']
            user.role = mock_data['role']
            user.service_department = mock_data['department']
            
            db.session.add(user)
            db.session.commit()
            
            login_user(user)
            return redirect_by_role(user)
        else:
            flash("Utilisateur inconnu.", "danger")

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

def redirect_by_role(user):
    """
    LOGIQUE DE REDIRECTION STRICTE :
    - Techs/Admins -> Dashboard Technique (V1 style)
    - Users/Managers -> Portail (Cartes)
    """
    role = str(user.role).upper()
    
    if 'SOLVER' in role or 'ADMIN' in role:
        # Les techniciens vont sur leur Dashboard de gestion
        return redirect(url_for('tickets.solver_dashboard'))
    else:
        # Les utilisateurs et managers vont sur le Portail de demande
        return redirect(url_for('main.user_portal'))
