# app/projects/routes.py
from __future__ import annotations

from flask import (
    Blueprint, request, render_template, redirect, url_for, jsonify, flash
)
from datetime import datetime
import json

from app.extensions import db
from sqlalchemy import or_, asc, desc, text
from datetime import datetime, date, timedelta


# ---- مدل‌ها (مطابق پروژه ZIP) ----
# توجه: AppSetting باید تعریف شده باشد (در همین ماژول یا ماژول جدا).
# اگر در محل دیگری است، مسیر ایمپورت را مطابق پروژه‌ات اصلاح کن.
from app.projects.models import (
    Project,
    ProjectStatus,
    ProjectLog,
    LogType,
    # اگر AppSetting در فایل دیگری‌ست، ایمپورت بعدی را تغییر بده
    AppSetting,
)

# Razmkar (برای لیست مأموریت‌ها در Drawer)
try:
    from app.razmkar.models import Razmkar, RazmkarStatus
except Exception:
    Razmkar = None
    RazmkarStatus = None

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")

FILTERS_KEY = "projects_manage_filters"


# --------------------------------------------------------------------
# Helper: parse enum safely (accept name or value)  -> LogType
# --------------------------------------------------------------------
def _parse_log_type(s: str) -> LogType:
    if not s:
        raise ValueError("empty type")
    s = s.strip()
    try:
        return LogType[s]  # by name
    except KeyError:
        pass
    try:
        return LogType(s)  # by value
    except Exception as e:
        raise ValueError(f"invalid log type: {s}") from e


# ====================================================================
# روت‌های پایه
# ====================================================================

@projects_bp.route("/", strict_slashes=False)
def projects_root():
    # سازگاری با آدرس /projects/ → صفحه مدیریت
    _ensure_planning_defaults()

    return redirect(url_for("projects.manage_projects", **request.args))


# جزئیات پروژه + افزودن لاگ Ajax از همین صفحه
@projects_bp.route('/<int:project_id>', methods=['GET', 'POST'])
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)

    # Ajax: افزودن لاگ
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        note = (request.form.get('note') or '').strip()
        type_ = (request.form.get('type') or '').strip()
        created_by = (request.form.get('created_by') or '').strip()

        if not note or not type_:
            return jsonify(ok=False, error='نوع یا متن لاگ نامعتبر است'), 400

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
            return jsonify(ok=True)
        except ValueError:
            db.session.rollback()
            return jsonify(ok=False, error='نوع لاگ نامعتبر است'), 400
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=f'خطای داخلی سرور: {e}'), 500

    return render_template('projects/detail.html', project=project)


# حذف پروژه
@projects_bp.route('/<int:project_id>/delete', methods=['POST', 'DELETE'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    try:
        # اگر cascade داری، حذف دستی لاگ لازم نیست؛ ولی این خط مشکلی ایجاد نمی‌کند
        ProjectLog.query.filter_by(project_id=project.id).delete()
        db.session.delete(project)
        db.session.commit()
        flash(f'پروژه "{project.goal}" حذف شد.', 'success')
    except Exception:
        db.session.rollback()
        flash('خطا در حذف پروژه رخ داد.', 'danger')

    return redirect(url_for('projects.manage_projects'))


# ایجاد پروژه
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


# ویرایش پروژه (Ajax)
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
    return jsonify(message="✅ پروژه ویرایش شد")


# افزودن لاگ پروژه (Ajax)
@projects_bp.route('/<int:project_id>/add-log', methods=['POST'])
def add_project_log(project_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify(ok=False, error="⛔ درخواست نامعتبر"), 400

    note = (request.form.get("note") or '').strip()
    created_by = (request.form.get("created_by") or '').strip()
    type_ = (request.form.get("type") or '').strip()

    if not note or not type_:
        return jsonify(ok=False, error="مقدارهای لازم وارد نشده"), 400

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
        return jsonify(ok=True, message="لاگ ثبت شد")
    except ValueError:
        db.session.rollback()
        return jsonify(ok=False, error="❌ نوع لاگ نامعتبر است"), 400
    except Exception as e:
        db.session.rollback()
        return jsonify(ok=False, error=f"خطای سرور: {e}"), 500


# دریافت/ویرایش/حذف لاگ پروژه (Ajax)
@projects_bp.route('/log/<int:log_id>')
def get_log(log_id):
    log = ProjectLog.query.get_or_404(log_id)
    return jsonify({"note": log.note, "created_by": log.created_by, "type": log.type.name})


@projects_bp.route('/log/<int:log_id>/edit', methods=['POST'])
def edit_log(log_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "⛔ درخواست نامعتبر", 400

    log = ProjectLog.query.get_or_404(log_id)
    note = (request.form.get("note") or '').strip()
    created_by = (request.form.get("created_by") or '').strip()
    type_ = (request.form.get("type") or '').strip()

    if not note or not type_:
        return "❌ اطلاعات ناقص", 400

    try:
        log.type = _parse_log_type(type_)
        log.note = note
        log.created_by = created_by
        db.session.commit()
        return jsonify({"message": "ویرایش شد"})
    except Exception as e:
        db.session.rollback()
        return f"❌ خطا: {e}", 500


@projects_bp.route('/log/<int:log_id>/delete', methods=['POST'])
def delete_log(log_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "⛔ درخواست نامعتبر", 400
    log = ProjectLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    return jsonify({"message": "حذف شد"})


# ====================================================================
# صفحه مدیریت/فهرست پروژه‌ها – با فیلترهای نسخه ZIP و ماندگاری در DB
# ====================================================================
@projects_bp.route('/manage', methods=['GET'])
def manage_projects():
    _ensure_planning_defaults()
    """
    فیلترها و رفتار:
      q: جستجو در client_name, goal (اگر با # شروع شود، ID)
      status: draft|active|waiting|completed|cancelled
      sort: id|client|created|status
      order: asc|desc
      per_page: 25|50|100 (پیش‌فرض 50)
      page: عدد صفحه (پیش‌فرض 1)
      group: 1/0 (نمای گروه‌بندی‌شده)
    منطق: اگر پارامتر GET آمد، همان را ذخیره و اعمال می‌کنیم؛
          در غیر این صورت آخرین فیلتر ذخیره‌شده از DB خوانده و اعمال می‌شود.
    """

    # پاکسازی دستی با ?clear=1
    if request.args.get('clear') == '1':
        set_setting(FILTERS_KEY, _default_filters())
        return redirect(url_for('projects.manage_projects'))

    # فیلترهای ورودی GET؟
    incoming_keys = ('q', 'status', 'sort', 'order', 'per_page', 'page', 'group')
    incoming = any(k in request.args for k in incoming_keys)

    if incoming:
        filters = {
            "q": (request.args.get('q') or '').strip(),
            "status": (request.args.get('status') or '').strip(),
            "sort": (request.args.get('sort') or 'created').strip(),
            "order": (request.args.get('order') or 'desc').strip(),
            "per_page": _to_int(request.args.get('per_page'), 50, allowed={25, 50, 100}),
            "page": _to_int(request.args.get('page'), 1, min_=1),
            "group": _to_bool(request.args.get('group')),
        }
        set_setting(FILTERS_KEY, filters)
    else:
        filters = get_setting(FILTERS_KEY, fallback=_default_filters())

    # اطمینان از مقادیر معتبر
    if filters["sort"] not in {"id", "client", "created", "status"}:
        filters["sort"] = "created"
    if filters["order"] not in {"asc", "desc"}:
        filters["order"] = "desc"
    if filters["per_page"] not in (25, 50, 100):
        filters["per_page"] = 50
    if filters["page"] < 1:
        filters["page"] = 1

    # کوئری
    q = Project.query

    # فیلتر وضعیت
    status_enum = None
    if filters["status"] and filters["status"] in ProjectStatus.__members__:
        status_enum = ProjectStatus[filters["status"]]
        q = q.filter(Project.status == status_enum)

    # فیلتر جستجو
    if filters["q"]:
        raw = filters["q"]
        if raw.startswith('#') and raw[1:].isdigit():
            q = q.filter(Project.id == int(raw[1:]))
        else:
            like = f"%{raw}%"
            q = q.filter(or_(Project.client_name.ilike(like),
                             Project.goal.ilike(like)))

    # مرتب‌سازی
    order_func = asc if filters["order"] == "asc" else desc
    if filters["sort"] == "id":
        q = q.order_by(order_func(Project.id))
    elif filters["sort"] == "client":
        q = q.order_by(order_func(Project.client_name))
    elif filters["sort"] == "status":
        # اگر Enum به‌صورت رشته ذخیره می‌شود، همین کار می‌کند
        q = q.order_by(order_func(Project.status))
    else:  # created
        # اگر ستون created_at هست:
        if hasattr(Project, "created_at"):
            q = q.order_by(order_func(Project.created_at))
        else:
            q = q.order_by(order_func(Project.id))

    # صفحه‌بندی
    page = filters["page"]
    per_page = filters["per_page"]
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    projects = pagination.items

    # شمارنده‌ها برای KPI (از کل دیتابیس یا بهتر: با همان فیلتر q)
    # اینجا برای هم‌خوانی با نسخه ZIP، صرفاً شمارنده کل وضعیت‌ها را می‌آوریم.
    counters = {
        "draft": Project.query.filter(Project.status == ProjectStatus.draft).count(),
        "active": Project.query.filter(Project.status == ProjectStatus.active).count(),
        "waiting": Project.query.filter(Project.status == ProjectStatus.waiting).count(),
        "completed": Project.query.filter(Project.status == ProjectStatus.completed).count(),
        "cancelled": Project.query.filter(Project.status == ProjectStatus.cancelled).count(),
    }

    # مقادیر مورد انتظار تمپلیت نسخه ZIP
    ctx = dict(
        projects=projects,
        pagination=pagination,
        q=filters["q"],
        status_q=filters["status"],
        sort=filters["sort"],
        order=filters["order"],
        per_page=filters["per_page"],
        group=filters["group"],
        counters=counters,
    )
    return render_template('projects/manage.html', **ctx)


# تغییر وضعیت پروژه – Ajax
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


# ====================================================================
# API مأموریت‌های پروژه برای Drawer (Razmkar)
# ====================================================================
@projects_bp.route("/<int:project_id>/missions", methods=["GET"])
def project_missions(project_id):
    try:
        if Razmkar is None:
            return jsonify({"ok": False, "error": "Razmkar module not available"}), 500

        project = Project.query.get_or_404(project_id)

        status_q = (request.args.get("status") or "").strip()        # todo|in_progress|done|cancelled|...
        q_text = (request.args.get("q") or "").strip()
        limit = int(request.args.get("limit") or 20)
        top_only = request.args.get("top") == "1"
        with_category = (request.args.get("with_category") == "1")

        query = Razmkar.query.filter(Razmkar.project_id == project.id)
        if top_only and hasattr(Razmkar, "parent_id"):
            query = query.filter(Razmkar.parent_id.is_(None))

        if q_text:
            like = f"%{q_text}%"
            if hasattr(Razmkar, "note"):
                query = query.filter(or_(Razmkar.mission.ilike(like),
                                         Razmkar.note.ilike(like)))
            else:
                query = query.filter(Razmkar.mission.ilike(like))

        if status_q and RazmkarStatus:
            try:
                st_enum = RazmkarStatus[status_q]
                query = query.filter(Razmkar.status == st_enum)
            except KeyError:
                pass

        order_cols = []
        if hasattr(Razmkar, "due_date"):
            order_cols.append(Razmkar.due_date.asc())
        order_cols.append(Razmkar.id.desc())
        items = query.order_by(*order_cols).limit(limit).all()

        def _ser(m):
            base = {
                "id": m.id,
                "title": getattr(m, "mission", f"ماموریت #{m.id}"),
                "status": (m.status.name if getattr(m, "status", None) else None),
                "status_label": (m.status.value if getattr(m, "status", None) else None),
                "due_date": (m.due_date.isoformat() if getattr(m, "due_date", None) else None),
                "assignee": None,
            }
            if with_category:
                texts = [
                    getattr(m, "mission", "") or "",
                    getattr(m, "note", "") or "",
                    getattr(m, "description", "") or "",
                ]
                cat, tags = _classify_from_texts(texts)
                base["category"] = cat  # field|administrative|desk|unknown
                base["tags"] = tags
            return base

        counters = {}
        if RazmkarStatus:
            for s in RazmkarStatus:
                cnt_q = Razmkar.query.filter(Razmkar.project_id == project.id, Razmkar.status == s)
                if top_only and hasattr(Razmkar, "parent_id"):
                    cnt_q = cnt_q.filter(Razmkar.parent_id.is_(None))
                counters[s.name] = cnt_q.count()

        return jsonify({"ok": True, "items": [_ser(m) for m in items], "counters": counters})
    except Exception as e:
        return jsonify({"ok": False, "error": f"server error: {e}"}), 500


# ====================================================================
# Helpers: settings & defaults
# ====================================================================
def _default_filters() -> dict:
    return {
        "q": "",
        "status": "",
        "sort": "created",     # id|client|created|status
        "order": "desc",       # asc|desc
        "per_page": 50,        # 25|50|100
        "page": 1,
        "group": False,
    }


def _to_int(v, default: int, min_: int | None = None, max_: int | None = None, allowed: set[int] | None = None) -> int:
    try:
        iv = int(v)
        if allowed is not None and iv not in allowed:
            return default
        if min_ is not None and iv < min_:
            return default
        if max_ is not None and iv > max_:
            return default
        return iv
    except Exception:
        return default


def _to_bool(v) -> bool:
    if not v:
        return False
    return str(v).strip().lower() in {"1", "true", "on", "yes", "y", "t"}


def set_setting(key: str, value_dict: dict, scope: str = "global"):
    """ذخیره JSON در جدول app_settings"""
    raw = json.dumps(value_dict, ensure_ascii=False)
    row = AppSetting.query.filter_by(scope=scope, key=key).first()
    if row:
        row.value = raw
    else:
        row = AppSetting(scope=scope, key=key, value=raw)
        db.session.add(row)
    db.session.commit()


def get_setting(key: str, scope: str = "global", fallback: dict | None = None) -> dict:
    row = AppSetting.query.filter_by(scope=scope, key=key).first()
    if row and row.value:
        try:
            return json.loads(row.value)
        except Exception:
            return fallback or {}
    return fallback or {}

import re

TAG_MAP_KEY = "tag_category_map"
CAT_PRIORITY_KEY = "category_priority"
CAPACITY_BLOCKS_KEY = "capacity_blocks_per_day"
BLOCK_LABELS_KEY = "block_labels"

_HASHTAG_RX = re.compile(r"#([0-9A-Za-z_\u0600-\u06FF]+)")

_DEFAULT_TAG_MAP = {
    # اداری
    "اداره_ثبت": "administrative",
    "شهرداری": "administrative",
    "املاک": "administrative",
    "کمیسیون": "administrative",
    "نامه": "administrative",
    "پیگیری": "administrative",
    # میدانی
    "نقشه_برداری": "field",
    "برداشت": "field",
    "بازدید": "field",
    "میدانی": "field",
    # دفتری
    "گزارش": "desk",
    "ترسیم": "desk",
    "نقشه": "desk",
    "مستندسازی": "desk",
    "بارگذاری": "desk",
}

_DEFAULT_CAT_PRIORITY = ["administrative", "field", "desk"]  # ترتیب تقدم در تعارض تگ‌ها

_DEFAULT_BLOCKS = ["AM", "MID", "PM"]
_DEFAULT_BLOCK_LABELS = {
    "AM":  {"label":"۷–۱۳","start":"07:00","end":"13:00"},
    "MID": {"label":"۱۳–۱۶","start":"13:00","end":"16:00"},
    "PM":  {"label":"۱۶–۱۹","start":"16:00","end":"19:00"},
}

def _ensure_planning_defaults():
    """تنظیم پیش‌فرض‌ها اگر قبلاً ذخیره نشده باشند."""
    if not get_setting(TAG_MAP_KEY):
        set_setting(TAG_MAP_KEY, _DEFAULT_TAG_MAP)
    if not get_setting(CAT_PRIORITY_KEY):
        set_setting(CAT_PRIORITY_KEY, _DEFAULT_CAT_PRIORITY)
    if not get_setting(CAPACITY_BLOCKS_KEY):
        set_setting(CAPACITY_BLOCKS_KEY, _DEFAULT_BLOCKS)
    if not get_setting(BLOCK_LABELS_KEY):
        set_setting(BLOCK_LABELS_KEY, _DEFAULT_BLOCK_LABELS)

def _extract_tags(text: str) -> list[str]:
    if not text:
        return []
    return [m.group(1) for m in _HASHTAG_RX.finditer(text)]

def _classify_from_texts(texts: list[str]) -> tuple[str, list[str]]:
    """
    از مجموعه‌ای از متن‌ها (مثلاً mission، note) تگ‌ها را استخراج و بر اساس واژه‌نامه دسته تعیین می‌کند.
    خروجی: (category ∈ field|administrative|desk|unknown, tags: List[str])
    """
    tag_map: dict = get_setting(TAG_MAP_KEY, fallback=_DEFAULT_TAG_MAP)
    cat_priority: list = get_setting(CAT_PRIORITY_KEY, fallback=_DEFAULT_CAT_PRIORITY)

    seen = []
    cats = []
    for t in texts:
        for tg in _extract_tags(t):
            seen.append(tg)
            if tg in tag_map:
                cats.append(tag_map[tg])

    if not cats:
        return "unknown", seen

    # انتخاب بهترین دسته بر اساس اولویت
    for c in cat_priority:
        if c in cats:
            return c, seen

    # اگر هیچ‌کدام در اولویت نبودند، اولی
    return cats[0], seen


@projects_bp.get("/settings/tags")
def get_tag_settings():
    _ensure_planning_defaults()
    return jsonify({
        "ok": True,
        "tag_category_map": get_setting(TAG_MAP_KEY, fallback=_DEFAULT_TAG_MAP),
        "category_priority": get_setting(CAT_PRIORITY_KEY, fallback=_DEFAULT_CAT_PRIORITY),
        "capacity_blocks_per_day": get_setting(CAPACITY_BLOCKS_KEY, fallback=_DEFAULT_BLOCKS),
        "block_labels": get_setting(BLOCK_LABELS_KEY, fallback=_DEFAULT_BLOCK_LABELS),
        # NEW:
        "block_capacity_points": get_setting(BLOCK_CAPACITY_POINTS_KEY, fallback=_DEFAULT_BLOCK_CAPACITY_POINTS),
        "mission_points_by_category": get_setting(MISSION_POINTS_BY_CATEGORY_KEY, fallback=_DEFAULT_MISSION_POINTS_BY_CATEGORY),
        "capacity_allow_overflow": bool(get_setting(ALLOW_OVERFLOW_KEY, fallback=False)),
    })


@projects_bp.post("/settings/tags")
def post_tag_settings():
    data = request.get_json(silent=True) or {}
    tmap = data.get("tag_category_map")
    prio = data.get("category_priority")
    blocks = data.get("capacity_blocks_per_day")
    blabels = data.get("block_labels")

    if isinstance(tmap, dict):
        set_setting(TAG_MAP_KEY, tmap)
    if isinstance(prio, list) and all(isinstance(x, str) for x in prio):
        set_setting(CAT_PRIORITY_KEY, prio)
    if isinstance(blocks, list) and all(isinstance(x, str) for x in blocks) and len(blocks) >= 1:
        set_setting(CAPACITY_BLOCKS_KEY, blocks)
    if isinstance(blabels, dict):
        set_setting(BLOCK_LABELS_KEY, blabels)

    return jsonify({"ok": True})


# ---- Stage 2: Weekly Planning (AM/MID/PM) ----
from datetime import date, timedelta

PLANNING_PREFIX = "capacity_schedule_"  # capacity_schedule_{YYYY-WW}

def _iso_week_key(d: date) -> str:
    # سال-هفته ISO مثل 2025-34
    y, w, _ = d.isocalendar()
    return f"{y:04d}-{w:02d}"

def _iso_monday(d: date) -> date:
    # شروع هفته به روش ISO (دوشنبه)
    return d - timedelta(days=d.weekday())

def _week_span(d: date) -> tuple[date, date]:
    # دوشنبه..یکشنبه (ISO)
    mon = _iso_monday(d)
    sun = mon + timedelta(days=6)
    return mon, sun

def _get_blocks() -> list[str]:
    return get_setting(CAPACITY_BLOCKS_KEY, fallback=_DEFAULT_BLOCKS)

def _get_block_labels() -> dict:
    return get_setting(BLOCK_LABELS_KEY, fallback=_DEFAULT_BLOCK_LABELS)

def _planning_load(d: date) -> dict:
    key = PLANNING_PREFIX + _iso_week_key(d)
    return get_setting(key, fallback={})

def _planning_save(d: date, schedule: dict):
    key = PLANNING_PREFIX + _iso_week_key(d)
    set_setting(key, schedule)

def _date_str(dt: date) -> str:
    return dt.strftime("%Y-%m-%d")

def _workdays() -> list[str]:
    # پیش‌فرض هفته کاری ایران: شنبه تا پنج‌شنبه
    return get_setting("workdays", fallback=["sat","sun","mon","tue","wed","thu"])

def _dow(dt: date) -> str:
    # mon..sun
    return ["mon","tue","wed","thu","fri","sat","sun"][dt.weekday()]



@projects_bp.get("/planning/week")
def planning_week_page():
    """صفحه‌ی نمای هفته (فرم ساده‌ی افزودن/حذف مأموریت‌ها به بلوک‌ها)"""
    _ensure_planning_defaults()

    # تاریخ مبنا
    from_str = (request.args.get("date") or "").strip()
    try:
        base = datetime.strptime(from_str, "%Y-%m-%d").date() if from_str else date.today()
    except Exception:
        base = date.today()

    mon, sun = _week_span(base)
    blocks = _get_blocks()
    blabels = _get_block_labels()
    schedule = _planning_load(base)  # {"YYYY-MM-DD_AM": [ids], ...}

    # لیست روزهای نمایشی بر اساس workdays
    wd = set(_workdays())
    days = []
    cur = mon
    for _ in range(7):
        if _dow(cur) in wd:
            days.append(cur)
        cur += timedelta(days=1)

    # دسته‌ی فیلتر (all/administrative/field/desk)
    category = (request.args.get("category") or "all").strip()

    # محاسبه ظرفیت/مصرف برای هر سلول
    usage = _compute_usage(schedule)

    ctx = dict(
        week_from=_date_str(mon),
        week_to=_date_str(sun),
        base_date=_date_str(base),
        blocks=blocks,
        block_labels=blabels,
        schedule=schedule,
        days=[_date_str(d) for d in days],
        category=category,
        usage=usage,
        block_capacity_points=_get_block_capacity_points(),
    )
    return render_template("planning/week.html", **ctx)


@projects_bp.get("/planning/week/data")
def planning_week_data():
    """داده خام هفته (برای اگر جلوتر بخوای ajax کنی)"""
    _ensure_planning_defaults()

    from_str = (request.args.get("date") or "").strip()
    try:
        base = datetime.strptime(from_str, "%Y-%m-%d").date() if from_str else date.today()
    except Exception:
        base = date.today()

    mon, sun = _week_span(base)
    blocks = _get_blocks()
    blabels = _get_block_labels()
    schedule = _planning_load(base)

    wd = set(_workdays())
    out_days = []
    cur = mon
    for _ in range(7):
        if _dow(cur) in wd:
            out_days.append(_date_str(cur))
        cur += timedelta(days=1)

    usage = _compute_usage(schedule)

    return jsonify({
        "ok": True,
        "week": {"from": _date_str(mon), "to": _date_str(sun), "iso": _iso_week_key(base)},
        "blocks": blocks,
        "block_labels": blabels,
        "days": out_days,
        "schedule": schedule,
        "usage": usage,
        "block_capacity_points": _get_block_capacity_points(),
    })




@projects_bp.post("/planning/week/assign")
def planning_week_assign():
    """افزودن یک مأموریت به یک بلوک روز (با کنترل ظرفیت)"""
    data = request.get_json(silent=True) or {}
    date_str = (data.get("date") or "").strip()
    block = (data.get("block") or "").strip()
    mission_id = data.get("mission_id")
    force = bool(data.get("force"))

    if not date_str or not block or not mission_id:
        return jsonify({"ok": False, "error": "params_required"}), 400

    try:
        base = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return jsonify({"ok": False, "error": "invalid_date"}), 400

    schedule = _planning_load(base)
    key = f"{date_str}_{block}"
    arr = list(schedule.get(key, []))

    # محاسبه‌ی ظرفیت این سلول
    caps = _get_block_capacity_points()
    cap = int(caps.get(block, 1))

    pts_new = 1
    if Razmkar:
        m = Razmkar.query.get(mission_id)
        if m is None:
            return jsonify({"ok": False, "error": "mission_not_found"}), 404
        _cat, pts_new = _mission_category_and_points(m)

    # امتیاز فعلی استفاده‌شده
    used_now = 0
    if Razmkar and arr:
        mids = Razmkar.query.filter(Razmkar.id.in_(arr)).all()
        for mm in mids:
            _c, pts = _mission_category_and_points(mm)
            used_now += int(pts)
    else:
        used_now = len(arr)

    # چک ظرفیت
    allow_overflow = bool(get_setting(ALLOW_OVERFLOW_KEY, fallback=False))
    if (used_now + int(pts_new)) > cap and not (force or allow_overflow):
        return jsonify({
            "ok": False,
            "error": "over_capacity",
            "message": "ظرفیت این بلوک پر است",
            "used": used_now,
            "capacity": cap,
            "points_new": int(pts_new),
        }), 400

    if mission_id not in arr:
        arr.append(mission_id)
        schedule[key] = arr
        _planning_save(base, schedule)

    # usage تازه را محاسبه کنیم
    usage = _compute_usage(schedule)
    return jsonify({"ok": True, "schedule": schedule, "usage": usage})



@projects_bp.post("/planning/week/unassign")
def planning_week_unassign():
    """حذف یک مأموریت از یک بلوک روز"""
    data = request.get_json(silent=True) or {}
    date_str = (data.get("date") or "").strip()
    block = (data.get("block") or "").strip()
    mission_id = data.get("mission_id")

    if not date_str or not block or not mission_id:
        return jsonify({"ok": False, "error": "params required"}), 400

    try:
        base = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return jsonify({"ok": False, "error": "invalid date"}), 400

    schedule = _planning_load(base)
    key = f"{date_str}_{block}"
    changed = False
    if key in schedule:
        arr = [x for x in schedule[key] if x != mission_id]
        schedule[key] = arr
        changed = True

    if changed:
        _planning_save(base, schedule)

    return jsonify({"ok": True, "schedule": schedule})


@projects_bp.get("/planning/pool")
def planning_pool():
    """
    فهرست مأموریت‌های پروژه‌های Active برای انتخاب در نمای هفته.
    پارامترها:
      - category: administrative|field|desk|all
      - q: جستجو در عنوان مأموریت/یادداشت/نام مشتری/هدف پروژه
      - limit: پیش‌فرض 200
      - exclude_done: پیش‌فرض 1 (done/cancelled را حذف می‌کند)
    """
    _ensure_planning_defaults()

    if Razmkar is None:
        return jsonify({"ok": False, "error": "Razmkar module not available"}), 500

    category = (request.args.get("category") or "all").strip()
    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 200)
    exclude_done = (request.args.get("exclude_done") or "1").lower() in ("1","true","on","yes")

    # فقط مأموریت‌های پروژه‌های Active
    query = (
        Razmkar.query
        .join(Project, Razmkar.project_id == Project.id)
        .filter(Project.status == ProjectStatus.active)
    )

    # حذف done/cancelled مگر اینکه کاربر بخواهد
    if exclude_done and RazmkarStatus:
        query = query.filter(
            Razmkar.status != RazmkarStatus.done,
            Razmkar.status != RazmkarStatus.cancelled
        )

    # جستجو
    if q:
        like = f"%{q}%"
        parts = [Razmkar.mission.ilike(like)]
        if hasattr(Razmkar, "note"):
            parts.append(Razmkar.note.ilike(like))
        parts.append(Project.client_name.ilike(like))
        parts.append(Project.goal.ilike(like))
        query = query.filter(or_(*parts))

    # مرتب‌سازی: موعددارها اول، نزدیک‌ترها جلو
    order_cols = []
    if hasattr(Razmkar, "due_date"):
        order_cols.append(Razmkar.due_date.is_(None).asc())
        order_cols.append(Razmkar.due_date.asc())
    order_cols.append(Razmkar.id.desc())
    items = query.order_by(*order_cols).limit(limit).all()

    # سریالایزر با تشخیص دسته از روی #تگ (مرحله ۱)
    def _ser(m):
        texts = [
            getattr(m, "mission", "") or "",
            getattr(m, "note", "") or "",
            getattr(m, "description", "") or "",
        ]
        cat, tags = _classify_from_texts(texts)
        # فیلتر دسته اگر خاص انتخاب شده
        if category in ("administrative", "field", "desk") and cat != category:
            return None
        return {
            "id": m.id,
            "project_id": m.project_id,
            "project_client": (m.project.client_name if getattr(m, "project", None) else None),
            "project_goal": (m.project.goal if getattr(m, "project", None) else None),
            "title": getattr(m, "mission", f"ماموریت #{m.id}"),
            "category": cat,                                  # field|administrative|desk|unknown
            "status": (m.status.name if getattr(m, "status", None) else None),
            "status_label": (m.status.value if getattr(m, "status", None) else None),
            "due_date": (m.due_date.isoformat() if getattr(m, "due_date", None) else None),
            "tags": tags
        }

    out = []
    for m in items:
        row = _ser(m)
        if row:
            out.append(row)

    return jsonify({"ok": True, "items": out})

# ظرفیت و امتیازها
BLOCK_CAPACITY_POINTS_KEY = "block_capacity_points"
MISSION_POINTS_BY_CATEGORY_KEY = "mission_points_by_category"
ALLOW_OVERFLOW_KEY = "capacity_allow_overflow"

_DEFAULT_BLOCK_CAPACITY_POINTS = {"AM": 2, "MID": 1, "PM": 1}
_DEFAULT_MISSION_POINTS_BY_CATEGORY = {"field": 2, "administrative": 1, "desk": 1, "unknown": 1}




def _ensure_planning_defaults():
    if not get_setting(TAG_MAP_KEY):
        set_setting(TAG_MAP_KEY, _DEFAULT_TAG_MAP)
    if not get_setting(CAT_PRIORITY_KEY):
        set_setting(CAT_PRIORITY_KEY, _DEFAULT_CAT_PRIORITY)
    if not get_setting(CAPACITY_BLOCKS_KEY):
        set_setting(CAPACITY_BLOCKS_KEY, _DEFAULT_BLOCKS)
    if not get_setting(BLOCK_LABELS_KEY):
        set_setting(BLOCK_LABELS_KEY, _DEFAULT_BLOCK_LABELS)
    # NEW:
    if not get_setting(BLOCK_CAPACITY_POINTS_KEY):
        set_setting(BLOCK_CAPACITY_POINTS_KEY, _DEFAULT_BLOCK_CAPACITY_POINTS)
    if not get_setting(MISSION_POINTS_BY_CATEGORY_KEY):
        set_setting(MISSION_POINTS_BY_CATEGORY_KEY, _DEFAULT_MISSION_POINTS_BY_CATEGORY)
    if get_setting(ALLOW_OVERFLOW_KEY) is None:
        set_setting(ALLOW_OVERFLOW_KEY, False)


def _get_block_capacity_points() -> dict:
    return get_setting(BLOCK_CAPACITY_POINTS_KEY, fallback=_DEFAULT_BLOCK_CAPACITY_POINTS)

def _get_mission_points_by_category() -> dict:
    return get_setting(MISSION_POINTS_BY_CATEGORY_KEY, fallback=_DEFAULT_MISSION_POINTS_BY_CATEGORY)

def _mission_category_and_points(m) -> tuple[str, int]:
    texts = [
        getattr(m, "mission", "") or "",
        getattr(m, "note", "") or "",
        getattr(m, "description", "") or "",
    ]
    cat, _tags = _classify_from_texts(texts)
    pts = int(_get_mission_points_by_category().get(cat, 1))
    return cat, pts

def _compute_usage(schedule: dict) -> dict:
    """
    schedule: {"YYYY-MM-DD_AM":[ids], ...}
    خروجی: {key: {"used": int, "capacity": int, "over": bool}}
    """
    caps = _get_block_capacity_points()
    usage = {}
    if not Razmkar:
        # بدون Razmkar امتیازها را 0 در نظر بگیریم
        for key, arr in (schedule or {}).items():
            block = key.rsplit("_", 1)[-1]
            cap = int(caps.get(block, 1))
            used = len(arr or [])
            usage[key] = {"used": used, "capacity": cap, "over": used > cap}
        return usage

    # جمع کردن همه IDها برای یک کوئری
    all_ids = set()
    for arr in (schedule or {}).values():
        for mid in arr or []:
            all_ids.add(mid)
    missions_by_id = {}
    if all_ids:
        for m in Razmkar.query.filter(Razmkar.id.in_(all_ids)).all():
            missions_by_id[m.id] = m

    for key, arr in (schedule or {}).items():
        block = key.rsplit("_", 1)[-1]
        cap = int(caps.get(block, 1))
        used = 0
        for mid in arr or []:
            m = missions_by_id.get(mid)
            if m is not None:
                _cat, pts = _mission_category_and_points(m)
            else:
                pts = 1
            used += int(pts)
        usage[key] = {"used": used, "capacity": cap, "over": used > cap}

    return usage
