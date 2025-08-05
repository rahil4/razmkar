from flask import Blueprint, render_template
from datetime import datetime, timedelta
from app.projects.models import Project
from app.razmkar.models import Razmkar, RazmkarStatus

dashboard_bp = Blueprint("dashboard", __name__, template_folder="templates")


@dashboard_bp.route("/")
def index():
    # فقط پروژه‌هایی که در وضعیت فعال هستند
    active_projects = Project.query.filter_by(status='active').order_by(Project.created_at.desc()).all()

    # ماموریت‌هایی که نیازمند اقدام هستند (مثلاً وضعیت pending یا in_progress)
    pending_razmkars = Razmkar.query.filter(Razmkar.status.in_(['pending', 'in_progress'])).order_by(Razmkar.due_date.asc()).all()

    # ماموریت‌هایی که موعد آن‌ها نزدیک است (مثلاً در ۷ روز آینده)
    today = datetime.utcnow()
    upcoming = today + timedelta(days=7)
    upcoming_razmkars = Razmkar.query.filter(
        Razmkar.due_date != None,
        Razmkar.due_date >= today,
        Razmkar.due_date <= upcoming
    ).order_by(Razmkar.due_date.asc()).all()

    return render_template(
        "dashboard/index.html",
        active_projects=active_projects,
        pending_razmkars=pending_razmkars,
        upcoming_razmkars=upcoming_razmkars
    )
