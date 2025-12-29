from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models import Notification
from app import db

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    # Récupérer les 10 dernières notifications non lues
    notifs = current_user.notifications.filter_by(is_read=False).order_by(Notification.timestamp.desc()).limit(10).all()
    count = current_user.notifications.filter_by(is_read=False).count()
    
    return jsonify({
        'count': count,
        'notifications': [n.to_dict() for n in notifs]
    })

@api_bp.route('/api/notifications/read/<int:id>', methods=['POST'])
@login_required
def mark_read(id):
    notif = Notification.query.get_or_404(id)
    if notif.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/api/notifications/read_all', methods=['POST'])
@login_required
def mark_all_read():
    current_user.notifications.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})
