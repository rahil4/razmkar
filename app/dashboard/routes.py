from flask import Blueprint, render_template
from datetime import datetime, timedelta
from app.projects.models import Project
from app.razmkar.models import Razmkar
from sqlalchemy.orm import aliased
from app import db  # مطمئن شو که db از app/extensions یا __init__ وارد شده


dashboard_bp = Blueprint("dashboard", __name__, template_folder="templates")

@dashboard_bp.route("/")
def index():
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    upcoming = today + timedelta(days=7)

    # ۱. پروژه‌های فعال
    active_projects = Project.query.filter_by(status='active').order_by(Project.created_at.desc()).all()

    # ۲. ماموریت‌های نیازمند اقدام (درحال انجام یا پیش‌نویس و تاریخ گذشته)
    pending_razmkars = Razmkar.query.filter(
        Razmkar.status.in_(['pending', 'in_progress']),
        Razmkar.due_date != None,
        Razmkar.due_date < today
    ).order_by(Razmkar.due_date.asc()).all()

    # ۳. ماموریت‌های بدون زمان‌بندی
    unscheduled_razmkars = Razmkar.query.filter(
        Razmkar.due_date == None
    ).order_by(Razmkar.created_at.desc()).all()

    # ۴. ماموریت‌های نزدیک به موعد (در ۷ روز آینده)
    upcoming_razmkars = Razmkar.query.filter(
        Razmkar.due_date != None,
        Razmkar.due_date >= today,
        Razmkar.due_date <= upcoming
    ).order_by(Razmkar.due_date.asc()).all()

    return render_template(
        "dashboard/index.html",
        active_projects=active_projects,
        pending_razmkars=pending_razmkars,
        unscheduled_razmkars=unscheduled_razmkars,
        upcoming_razmkars=upcoming_razmkars
    )


@dashboard_bp.route("/today")
def today_view():
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    today_razmkars = Razmkar.query.filter(
        Razmkar.due_date != None,
        Razmkar.due_date >= today,
        Razmkar.due_date < tomorrow
    ).order_by(Razmkar.status.asc()).all()

    return render_template("dashboard/today.html", today_razmkars=today_razmkars)