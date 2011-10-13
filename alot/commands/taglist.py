from commands import Command, registerCommand
from twisted.internet import defer

import os
import re
import code
import glob
import logging
import threading
import subprocess
import shlex
import email
import tempfile
from email import Charset
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urwid
from twisted.internet import defer

import buffer
import settings
import widgets
import completion
import helper
from db import DatabaseROError
from db import DatabaseLockedError
from completion import ContactsCompleter
from completion import AccountCompleter
from message import decode_to_unicode
from message import decode_header
from message import encode_header
MODE = 'taglist'


@registerCommand(MODE, 'select', {})
class TaglistSelectCommand(Command):
    def apply(self, ui):
        tagstring = ui.current_buffer.get_selected_tag()
        cmd = SearchCommand(query='tag:%s' % tagstring)
        ui.apply_command(cmd)


