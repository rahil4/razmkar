import jdatetime
from datetime import datetime
from dateutil.relativedelta import relativedelta

def to_jalali(value):
    """تبدیل تاریخ میلادی به شمسی (yyyy/mm/dd)"""
    if not value:
        return ''
    try:
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            date_only = value.date()
            j_date = jdatetime.date.fromgregorian(date=date_only)
            return j_date.strftime('%Y/%m/%d')
        elif hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
            j_date = jdatetime.date.fromgregorian(date=value)
            return j_date.strftime('%Y/%m/%d')
        elif isinstance(value, str):
            parsed_date = datetime.strptime(value, '%Y-%m-%d').date()
            j_date = jdatetime.date.fromgregorian(date=parsed_date)
            return j_date.strftime('%Y/%m/%d')
    except Exception as e:
        print(f"خطا در تبدیل تاریخ: {value} -> {e}")
        return str(value)
    return ''

def to_jalali_detailed(value):
    """تبدیل تاریخ میلادی به شمسی با نام ماه فارسی"""
    if not value:
        return ''
    try:
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            date_only = value.date()
            j_date = jdatetime.date.fromgregorian(date=date_only)
            months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                      'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
            return f"{j_date.day} {months[j_date.month - 1]} {j_date.year}"
    except Exception as e:
        print(f"خطا در تبدیل تاریخ تفصیلی: {value} -> {e}")
        return str(value)
    return ''

def to_jalali_with_time(value):
    """تبدیل تاریخ و زمان به شمسی همراه با ساعت"""
    if not value:
        return ''
    try:
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            j_datetime = jdatetime.datetime.fromgregorian(datetime=value)
            return j_datetime.strftime('%Y/%m/%d - %H:%M')
    except Exception as e:
        print(f"خطا در تبدیل datetime: {value} -> {e}")
        return str(value)
    return ''

def time_since(value):
    """نمایش زمان گذشته از یک تاریخ به‌صورت خوانا"""
    if not value:
        return ''
    now = datetime.now()
    diff = relativedelta(now, value)

    if diff.years == 0 and diff.months == 0 and diff.days == 0:
        return 'امروز'

    parts = []
    if diff.years:
        parts.append(f"{diff.years} سال")
    if diff.months:
        parts.append(f"{diff.months} ماه")
    if diff.days:
        parts.append(f"{diff.days} روز")

    return ' و '.join(parts) + ' پیش'

def persian_digits(value):
    """تبدیل ارقام انگلیسی به فارسی"""
    english_to_persian = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    try:
        return str(value).translate(english_to_persian)
    except:
        return value




import re
from markupsafe import Markup, escape

def highlight_tags(text):
    def replacer(match):
        tag = match.group(0)
        return f'<span class="tag">{escape(tag)}</span>'
    
    escaped = escape(text)
    highlighted = re.sub(r'#\w[\w\d_آ-ی-]*', replacer, escaped)
    return Markup(highlighted)
