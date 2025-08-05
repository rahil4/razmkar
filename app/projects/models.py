from datetime import datetime
from sqlalchemy import Enum
from app.extensions import db
import enum
from app.razmkar.models import Razmkar  # مطمئن شو که این import در پایین فایل انجام می‌شود

class ProjectStatus(enum.Enum):
    draft = "پیش نویس"
    active = "فعال"
    waiting = "درانتظار"
    completed = "اتمام"
    cancelled = "لغو"

class LogType(enum.Enum):
    note = "یادداشت"
    action = "فعالیت"
    followup = "پیگیری"
    reminder = "یادآوری"

    def label(self):
        return {
            "note": "یادداشت",
            "action": "اقدام",
            "followup": "پیگیری",
            "reminder": "یادآوری"
        }[self.value]

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal = db.Column(db.String(255), nullable=False)
    client_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum(ProjectStatus), default=ProjectStatus.draft)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    logs = db.relationship('ProjectLog', backref='project', cascade="all, delete-orphan")
    razmkars = db.relationship('Razmkar', backref='project', lazy=True, cascade="all, delete-orphan")

class ProjectLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    type = db.Column(db.Enum(LogType), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), nullable=True)
