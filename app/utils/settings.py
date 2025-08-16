import json
from app.extensions import db
from app.projects.models import AppSetting  # مسیر ایمپورت را مطابق پروژه تنظیم کن

def set_setting(key: str, value_dict: dict, scope: str = "global"):
    raw = json.dumps(value_dict, ensure_ascii=False)
    row = AppSetting.query.filter_by(scope=scope, key=key).first()
    if row:
        row.value = raw
    else:
        row = AppSetting(scope=scope, key=key, value=raw)
        db.session.add(row)
    db.session.commit()
    return True

def get_setting(key: str, scope: str = "global", fallback: dict | None = None) -> dict:
    row = AppSetting.query.filter_by(scope=scope, key=key).first()
    if row and row.value:
        try:
            return json.loads(row.value)
        except Exception:
            return fallback or {}
    return fallback or {}
