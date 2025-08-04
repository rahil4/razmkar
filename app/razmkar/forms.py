from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateTimeField, SelectField, SubmitField, HiddenField
from wtforms.validators import DataRequired
from .models import RazmkarStatus, RazmkarLogType
from wtforms import StringField, TextAreaField, DateField, DateTimeField, SelectField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional



class RazmkarForm(FlaskForm):
    mission = StringField("عنوان مأموریت", validators=[DataRequired()])
    note = TextAreaField("توضیحات")
    due_date = DateField("تاریخ سررسید", format='%Y-%m-%d', validators=[Optional()])
    status = SelectField("وضعیت", choices=[(s.value, s.name) for s in RazmkarStatus])
    parent_id = HiddenField("والد (در صورت وجود)")
    submit = SubmitField("ثبت رزم‌کار")

class RazmkarLogForm(FlaskForm):
    type = SelectField("نوع لاگ", choices=[(t.value, t.name) for t in RazmkarLogType])
    content = TextAreaField("محتوا (در صورت وجود)")
    created_by = StringField("ایجادکننده")
    submit = SubmitField("افزودن لاگ")
