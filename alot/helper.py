from datetime import date
from datetime import timedelta


def shorten(string, maxlen):
    if len(string) > maxlen - 3:
        string = string[:maxlen - 3] + '...'
    return string


def pretty_datetime(d):
    s = ""
    today = date.today()
    if today == d.date():
        s = d.strftime('%H:%M%P')
    elif d.date() == today - timedelta(1):
        s = 'Yest.%2d' % d.hour + d.strftime('%P')
    elif d.year != today.year:
        s = d.strftime('%b %Y')
    else:
        s = d.strftime('%b %d')
    return s.rjust(10)
