# app/projects/routes.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app.extensions import db
from app.projects.models import Project, ProjectStatus, ProjectLog, LogType

projects_bp = Blueprint('projects', __name__)

# ————————————————————————————————————————————————
# Helper: parse enum safely (accept name or value)
# ————————————————————————————————————————————————
def _parse_log_type(s: str) -> LogType:
    if s is None:
        raise ValueError("empty type")
    s = s.strip()
    # try by name (e.g., "note", "action", ...)
    try:
        return LogType[s]
    except KeyError:
        pass
    # try by value (e.g., "یادداشت", "فعالیت", ...)
    try:
        return LogType(s)
    except Exception as e:
        raise ValueError(f"invalid log type: {s}") from e


# ————————————————————————————————————————————————
# جزئیات سبک – /projects/<id>
# همچنین پذیرش POST Ajax برای افزودن لاگ
# ————————————————————————————————————————————————
@projects_bp.route('/<int:project_id>', methods=['GET', 'POST'])
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)

    # Ajax add log from detail page
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        note = request.form.get('note')
        type_ = request.form.get('type')
        created_by = request.form.get('created_by')

        if not note or not type_:
            return 'نوع یا متن لاگ نامعتبر است', 400

        try:
            log_type = _parse_log_type(type_)
            log = ProjectLog(
                project_id=project.id,
                note=note,
                type=log_type,
                created_by=created_by
            )
            db.session.add(log)
            db.session.commit()
            return 'OK', 200

        except ValueError:
            return 'نوع لاگ نامعتبر است', 400
        except Exception as e:
            return f'خطای داخلی سرور: {e}', 500

    return render_template('projects/detail.html', project=project)


# ————————————————————————————————————————————————
# حذف پروژه
# ————————————————————————————————————————————————
@projects_bp.route('/<int:project_id>/delete', methods=['POST', 'DELETE'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    try:
        # اگر cascade در مدل تنظیم شده باشد، حذف دستی لاگ‌ها لازم نیست،
        # ولی این خط مشکلی ایجاد نمی‌کند.
        ProjectLog.query.filter_by(project_id=project.id).delete()
        db.session.delete(project)
        db.session.commit()
        flash(f'پروژه "{project.goal}" با موفقیت حذف شد!', 'success')
    except Exception:
        db.session.rollback()
        flash('خطا در حذف پروژه رخ داد. لطفاً دوباره تلاش کنید.', 'danger')

    # قبلاً به list_projects می‌رفت؛ الان صفحه‌ی مدیریت اصلی است:
    return redirect(url_for('projects.manage_projects'))


# ————————————————————————————————————————————————
# ایجاد پروژه
# ————————————————————————————————————————————————
@projects_bp.route('/create', methods=['GET', 'POST'])
def create_project():
    if request.method == "POST":
        client_name = (request.form.get('client_name') or '').strip()
        goal = (request.form.get('goal') or '').strip()
        status_value = (request.form.get('status') or 'draft').strip()

        try:
            status_enum = ProjectStatus[status_value]
        except KeyError:
            flash("وضعیت نامعتبر است", "danger")
            return redirect(url_for('projects.create_project'))

        if not client_name or not goal:
            flash("همه فیلدها الزامی هستند", "warning")
            return redirect(url_for('projects.create_project'))

        new_project = Project(client_name=client_name, goal=goal, status=status_enum)
        db.session.add(new_project)
        db.session.commit()
        flash("پروژه با موفقیت ایجاد شد", "success")
        return redirect(url_for('projects.project_detail', project_id=new_project.id))

    return render_template("projects/create.html")


# ————————————————————————————————————————————————
# ویرایش پروژه (Ajax)
# ————————————————————————————————————————————————
@projects_bp.route('/<int:project_id>/edit', methods=['POST'])
def edit_project(project_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify(message="⛔ درخواست نامعتبر"), 400

    project = Project.query.get_or_404(project_id)

    client_name = (request.form.get('client_name') or '').strip()
    goal = (request.form.get('goal') or '').strip()
    status_in = (request.form.get('status') or '').strip()

    if client_name:
        project.client_name = client_name
    if goal:
        project.goal = goal

    if status_in:
        try:
            project.status = ProjectStatus[status_in]
        except Exception:
            return jsonify(message="وضعیت نامعتبر است"), 400

    db.session.commit()
    return jsonify(message="✅ پروژه با موفقیت ویرایش شد")


# ————————————————————————————————————————————————
# افزودن لاگ پروژه (Ajax)
# ————————————————————————————————————————————————
@projects_bp.route('/<int:project_id>/add-log', methods=['POST'])
def add_project_log(project_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "⛔ درخواست نامعتبر", 400

    note = request.form.get("note")
    created_by = request.form.get("created_by")
    type_ = request.form.get("type")

    if not note or not type_:
        return "مقدارهای لازم وارد نشده", 400

    try:
        type_enum = _parse_log_type(type_)
        new_log = ProjectLog(
            project_id=project_id,
            note=note,
            created_by=created_by,
            type=type_enum
        )
        db.session.add(new_log)
        db.session.commit()
        return jsonify({"message": "لاگ با موفقیت ثبت شد"})
    except ValueError:
        return "❌ نوع لاگ نامعتبر است", 400
    except Exception as e:
        return f"خطای سرور: {e}", 500


# ————————————————————————————————————————————————
# دریافت/ویرایش/حذف لاگ پروژه (Ajax)
# ————————————————————————————————————————————————
@projects_bp.route('/log/<int:log_id>')
def get_log(log_id):
    log = ProjectLog.query.get_or_404(log_id)
    return jsonify({
        "note": log.note,
        "created_by": log.created_by,
        "type": log.type.name
    })


@projects_bp.route('/log/<int:log_id>/edit', methods=['POST'])
def edit_log(log_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "⛔ درخواست نامعتبر", 400

    log = ProjectLog.query.get_or_404(log_id)

    note = request.form.get("note")
    created_by = request.form.get("created_by")
    type_ = request.form.get("type")

    if not note or not type_:
        return "❌ اطلاعات ناقص", 400

    try:
        log.type = _parse_log_type(type_)
        log.note = note
        log.created_by = created_by
        db.session.commit()
        return jsonify({"message": "ویرایش شد"})
    except Exception as e:
        return f"❌ خطا: {e}", 500


@projects_bp.route('/log/<int:log_id>/delete', methods=['POST'])
def delete_log(log_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "⛔ درخواست نامعتبر", 400

    log = ProjectLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    return jsonify({"message": "حذف شد"})


# ————————————————————————————————————————————————
# فهرست/مدیریت پروژه‌ها – /projects
# پارامترها:
# q: جستجو در client_name, goal؛ اگر با # شروع شد یعنی ID
# status: draft|active|waiting|completed|cancelled
# sort: id|client|created|status  (پیش‌فرض created)
# order: asc|desc (پیش‌فرض desc)
# page, per_page: صفحه‌بندی (پیش‌فرض per_page=50)
# selected: باز کردن Drawer/Modal جزئیات (در قالب استفاده می‌شود)
# group: 1/0 (اختیاری – گروه‌بندی بر اساس وضعیت)
# ————————————————————————————————————————————————
@projects_bp.route("/", methods=["GET"])  # /projects
def manage_projects():
    q = (request.args.get("q") or "").strip()
    status_q = (request.args.get("status") or "").strip()
    sort = (request.args.get("sort") or "created").strip()
    order = (request.args.get("order") or "desc").strip()
    page = int(request.args.get("page") or 1)
    per_page = int(request.args.get("per_page") or 50)
    group = request.args.get("group") == "1"
    selected = request.args.get("selected")

    query = Project.query

    # فیلتر جستجو
    if q:
        if q.startswith("#"):
            try:
                pid = int(q[1:])
                query = query.filter(Project.id == pid)
            except ValueError:
                pass
        else:
            like = f"%{q}%"
            query = query.filter(
                (Project.client_name.ilike(like)) | (Project.goal.ilike(like))
            )

    # فیلتر وضعیت
    if status_q:
        try:
            status_enum = ProjectStatus[status_q]
            query = query.filter(Project.status == status_enum)
        except KeyError:
            pass

    # مرتب‌سازی (بدون نیاز به asc/desc import)
    sort_map = {
        "id": Project.id,
        "client": Project.client_name,
        "created": Project.created_at,
        "status": Project.status,
    }
    sort_col = sort_map.get(sort, Project.created_at)
    query = query.order_by(sort_col.asc() if order == "asc" else sort_col.desc())

    # صفحه‌بندی
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    projects = pagination.items

    # شمارنده‌های وضعیت برای KPI کوچک
    counters = {
        name: Project.query.filter(Project.status == enum_val).count()
        for name, enum_val in {
            "draft": ProjectStatus.draft,
            "active": ProjectStatus.active,
            "waiting": ProjectStatus.waiting,
            "completed": ProjectStatus.completed,
            "cancelled": ProjectStatus.cancelled,
        }.items()
    }

    return render_template(
        "projects/manage.html",
        projects=projects,
        pagination=pagination,
        q=q,
        status_q=status_q,
        sort=sort,
        order=order,
        per_page=per_page,
        group=group,
        selected=selected,
        counters=counters,
    )


# ————————————————————————————————————————————————
# تغییر وضعیت پروژه – Ajax
# ————————————————————————————————————————————————
@projects_bp.route("/<int:project_id>/status", methods=["POST"])
def update_project_status(project_id):
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()

    if not new_status:
        return jsonify({"ok": False, "error": "status required"}), 400

    try:
        status_enum = ProjectStatus[new_status]
    except KeyError:
        return jsonify({"ok": False, "error": "invalid status"}), 400

    project = Project.query.get_or_404(project_id)
    project.status = status_enum
    db.session.commit()

    return jsonify({"ok": True, "id": project.id, "new_status": project.status.name})



# app/projects/routes.py

from flask import jsonify
from sqlalchemy import or_

try:
    from app.missions.models import Mission, MissionStatus
except Exception:
    Mission = None
    MissionStatus = None

def _ser_mission(m):
    title = getattr(m, 'title', None) or getattr(m, 'name', None) or getattr(m, 'subject', None) or f"ماموریت #{m.id}"
    due = getattr(m, 'due_date', None) or getattr(m, 'deadline', None)
    assignee = getattr(m, 'assignee', None) or getattr(m, 'owner', None) or getattr(m, 'executor', None)
    return {
        "id": m.id,
        "title": title,
        "status": m.status.name if getattr(m, 'status', None) else None,
        "status_label": m.status.value if getattr(m, 'status', None) else None,
        "due_date": (due.isoformat() if due else None),
        "assignee": assignee,
    }

# بالای فایل (ایمپورت‌ها)
from sqlalchemy import or_
from app.razmkar.models import Razmkar, RazmkarStatus  # ← این‌ها موجودند

# ...

@projects_bp.route("/<int:project_id>/missions", methods=["GET"])
def project_missions(project_id):
    try:
        project = Project.query.get_or_404(project_id)

        status_q = (request.args.get("status") or "").strip()           # pending|in_progress|done|cancelled
        q = (request.args.get("q") or "").strip()
        limit = int(request.args.get("limit") or 20)
        top_only = request.args.get("top") == "1"                        # اختیاری: فقط سطح بالا

        query = Razmkar.query.filter(Razmkar.project_id == project.id)
        if top_only and hasattr(Razmkar, "parent_id"):
            query = query.filter(Razmkar.parent_id.is_(None))

        if q:
            like = f"%{q}%"
            # جستجو در mission و note
            query = query.filter(or_(Razmkar.mission.ilike(like), Razmkar.note.ilike(like)))

        if status_q:
            try:
                st_enum = RazmkarStatus[status_q]
                query = query.filter(Razmkar.status == st_enum)
            except KeyError:
                pass

        # مرتب‌سازی: موعد نزدیک‌تر اول (nullها بعد)، سپس id نزولی
        order_cols = []
        if hasattr(Razmkar, "due_date"):
            order_cols.append(Razmkar.due_date.asc())
        order_cols.append(Razmkar.id.desc())
        items = query.order_by(*order_cols).limit(limit).all()

        def _ser(m):
            return {
                "id": m.id,
                "title": getattr(m, "mission", f"ماموریت #{m.id}"),
                "status": m.status.name if m.status else None,          # انگلیسی
                "status_label": m.status.value if m.status else None,   # فارسی
                "due_date": (m.due_date.isoformat() if getattr(m, "due_date", None) else None),
                "assignee": None,  # اگر فیلدی برای مجری دارید، اینجا بگذارید
            }

        # شمارنده‌ها
        counters = {}
        for s in RazmkarStatus:
            cnt_q = Razmkar.query.filter(Razmkar.project_id == project.id, Razmkar.status == s)
            if top_only and hasattr(Razmkar, "parent_id"):
                cnt_q = cnt_q.filter(Razmkar.parent_id.is_(None))
            counters[s.name] = cnt_q.count()

        return jsonify({"ok": True, "items": [_ser(m) for m in items], "counters": counters})
    except Exception as e:
        return jsonify({"ok": False, "error": f"server error: {e}"}), 500
