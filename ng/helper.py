
def shorten(string,maxlen):
    if len(string)>maxlen-3:
        string = string[:maxlen-3]+'...'
    return string
