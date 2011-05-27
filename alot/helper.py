from datetime import date
from datetime import timedelta


def shorten(string, maxlen):
    if len(string) > maxlen - 3:
        string = string[:maxlen - 3] + '...'
    return string


def pretty_datetime(d):
    string = ""
    today = date.today()
    if today == d.date():
        string = d.strftime('%H:%M%P')
    elif d.date() == today - timedelta(1):
        string = 'Yest.%2d' % d.hour + d.strftime('%P')
    elif d.year != today.year:
        string = d.strftime('%b %Y')
    else:
        string = d.strftime('%b %d')
    return string.rjust(10)
