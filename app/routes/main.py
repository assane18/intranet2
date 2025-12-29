from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import UserRole

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    return redirect(url_for('main.user_portal'))

@main_bp.route('/portal')
@login_required
def user_portal():
    # C'est la page d'accueil des utilisateurs (Le menu avec les 4 cartes)
    return render_template('portal.html', user=current_user)

@main_bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    # Protection : Seul l'admin peut voir ça
    if current_user.role != UserRole.ADMIN:
        return redirect(url_for('main.catdance'))
    # On réutilise le template admin_users.html s'il existe, sinon un simple texte pour tester
    return "<h1>Espace Admin (En construction)</h1><a href='/auth/logout'>Déconnexion</a>"

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Aiguillage intelligent selon le rôle
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for('main.admin_dashboard'))
    elif current_user.role == UserRole.MANAGER:
        return redirect(url_for('tickets.manager_dashboard'))
    elif current_user.role == UserRole.SOLVER:
        return redirect(url_for('tickets.solver_dashboard'))
    else:
        return redirect(url_for('main.user_portal'))

@main_bp.route('/catdance')
def catdance():
    return render_template('errors/catdance.html')
