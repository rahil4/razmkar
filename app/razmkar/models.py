from datetime import datetime
from sqlalchemy import Enum
from sqlalchemy.orm import backref
from app.extensions import db
import enum

class RazmkarStatus(enum.Enum):
    pending = "پیش نویس"
    in_progress = "درحال انجام"
    done = "انجام شده"
    cancelled = "لغو"

class RazmkarLogType(enum.Enum):
    note = "note"
    action = "action"
    followup = "followup"
    reminder = "reminder"
    status_change = "status_change"
    file_upload = "file_upload"

class Razmkar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('razmkar.id'), nullable=True)

    mission = db.Column(db.String(255), nullable=False)
    note = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.Enum(RazmkarStatus), default=RazmkarStatus.pending)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    children = db.relationship('Razmkar',
                               backref=backref('parent', remote_side=[id]),
                               lazy=True)
    logs = db.relationship('RazmkarLog',
                           backref='razmkar',
                           cascade="all, delete-orphan")

class RazmkarLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    razmkar_id = db.Column(db.Integer, db.ForeignKey('razmkar.id'), nullable=False)

    type = db.Column(db.Enum(RazmkarLogType), nullable=False)
    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), nullable=True)
