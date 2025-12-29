from . import db
from flask_login import UserMixin
from datetime import datetime
import enum

# --- ÉNUMÉRATIONS ---
class UserRole(str, enum.Enum):
    USER = "USER"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"
    SOLVER = "SOLVER"

class TicketStatus(str, enum.Enum):
    DRAFT = "BROUILLON"
    VALIDATION = "EN_VALIDATION"
    PENDING = "EN_ATTENTE_SERVICE"
    IN_PROGRESS = "EN_COURS"
    REFUSED = "REFUSE"
    DONE = "TERMINE"

class ServiceType(str, enum.Enum):
    INFO = "INFORMATIQUE"
    DAF = "DAF"
    GEN = "GENERAUX"
    TECH = "TECHNIQUE"
    ENLEV = "ENLEVEMENT"

# --- MODÈLES UTILISATEURS & TICKETS ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    fullname = db.Column(db.String(120))
    email = db.Column(db.String(120))
    role = db.Column(db.Enum(UserRole), default=UserRole.USER)
    service_department = db.Column(db.Enum(ServiceType), nullable=True)
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    uid_public = db.Column(db.String(20), unique=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Relations
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = db.relationship('User', foreign_keys=[author_id], backref='my_tickets')
    target_service = db.Column(db.Enum(ServiceType), nullable=False)
    
    # Workflow
    status = db.Column(db.Enum(TicketStatus), default=TicketStatus.VALIDATION)
    solver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    solver = db.relationship('User', foreign_keys=[solver_id], backref='assigned_tickets')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    
    # --- CHAMPS SPÉCIFIQUES V2 (Nouveaux) ---
    category_ticket = db.Column(db.String(50)) # "Standard", "Nouvel Utilisateur", "Matériel"
    hostname = db.Column(db.String(64), nullable=True) # Pour incidents classiques
    
    # Pour "Nouvel Utilisateur"
    new_user_fullname = db.Column(db.String(150), nullable=True)
    new_user_service = db.Column(db.String(100), nullable=True)
    new_user_acces = db.Column(db.String(255), nullable=True) # Accès fichiers/dossiers
    new_user_date = db.Column(db.DateTime, nullable=True)
    
    # Pour "Demande Matériel"
    materiel_list = db.Column(db.Text, nullable=True) # Liste du matériel
    destinataire_materiel = db.Column(db.String(150), nullable=True)
    service_destinataire = db.Column(db.String(100), nullable=True)

class TicketMessage(db.Model):
    __tablename__ = 'ticket_messages'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'))
    ticket = db.relationship('Ticket', backref='messages')
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = db.relationship('User')

# --- MODÈLES INVENTAIRE ---
class Materiel(db.Model):
    __tablename__ = 'materiels'
    id = db.Column(db.Integer, primary_key=True)
    categorie = db.Column(db.String(50))
    modele = db.Column(db.String(100))
    sn = db.Column(db.String(100), unique=True)
    hostname = db.Column(db.String(100))
    imei = db.Column(db.String(100))
    statut = db.Column(db.String(50), default='Disponible')

class Pret(db.Model):
    __tablename__ = 'prets'
    id = db.Column(db.Integer, primary_key=True)
    materiel_id = db.Column(db.Integer, db.ForeignKey('materiels.id'))
    materiel = db.relationship('Materiel', backref='historique_prets')
    technicien_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    technicien = db.relationship('User', backref='prets_geres')
    nom_emprunteur = db.Column(db.String(100))
    prenom_emprunteur = db.Column(db.String(100))
    service_emprunteur = db.Column(db.String(100))
    date_sortie = db.Column(db.DateTime, default=datetime.utcnow)
    date_retour_prevue = db.Column(db.DateTime, nullable=True)
    date_retour_reelle = db.Column(db.DateTime, nullable=True)
    statut_dossier = db.Column(db.String(20), default='En cours')
    type_pret = db.Column(db.String(50))
    accessoires = db.Column(db.String(255))
    etat_ecran_sortie = db.Column(db.String(50))
    etat_clavier_sortie = db.Column(db.String(50))
    etat_coque_sortie = db.Column(db.String(50))
    etat_ecran_retour = db.Column(db.String(50))
    etat_clavier_retour = db.Column(db.String(50))
    etat_coque_retour = db.Column(db.String(50))

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    message = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(20), default='info')
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'message': self.message,
            'category': self.category,
            'link': self.link,
            'is_read': self.is_read,
            'timestamp': self.timestamp.isoformat()
        }
