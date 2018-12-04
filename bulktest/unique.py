#!/usr/bin/python
import re
from os import listdir
from os.path import join


Errors = {}
for f in listdir('logs'):
    with open(join('logs', f)) as fh:
        content = fh.read()
        tracebacks = re.findall('(^ERROR(\n|.)+\n\n)', content, re.M)
        for t, _ in tracebacks:
            Errors[t] = f

for ut in Errors.keys():
    f = Errors[ut]
    with open(join('traces', f), 'w') as fh:
        fh.write(ut)
