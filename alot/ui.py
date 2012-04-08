import urwid
import logging
from twisted.internet import reactor, defer
import sys

from settings import settings
from buffers import BufferlistBuffer
import commands
from commands import commandfactory
from alot.commands import CommandParseError
import widgets


class InputWrap(urwid.WidgetWrap):
    """
    This is the topmost widget used in the widget tree.
    Its purpose is to capture and interpret keypresses
    by instantiating and applying the relevant :class:`Command` objects
    or relaying them to the wrapped `rootwidget`.
    """
    def __init__(self, ui, rootwidget):
        urwid.WidgetWrap.__init__(self, rootwidget)
        self.ui = ui
        self.rootwidget = rootwidget
        self.select_cancel_only = False

    def set_root(self, w):
        self._w = w

    def get_root(self):
        return self._w

    def allowed_command(self, cmd):
        """sanity check if the given command should be applied.
        This is used in :meth:`keypress`"""
        if not self.select_cancel_only:
            return True
        elif isinstance(cmd, commands.globals.SendKeypressCommand):
            if cmd.key in ['select', 'cancel']:
                return True
        else:
            return False

    def keypress(self, size, key):
        """overwrites `urwid.WidgetWrap.keypress`"""
        mode = self.ui.mode
        if self.select_cancel_only:
            mode = 'global'
        cmdline = settings.get_keybinding(mode, key)
        if cmdline:
            try:
                cmd = commandfactory(cmdline, mode)
                if self.allowed_command(cmd):
                    self.ui.apply_command(cmd)
                    return None
            except CommandParseError, e:
                self.ui.notify(e.message, priority='error')
        return self._w.keypress(size, key)


class UI(object):
    """
    This class integrates all components of alot and offers
    methods for user interaction like :meth:`prompt`, :meth:`notify` etc.
    It handles the urwid widget tree and mainloop (we use twisted) and is
    responsible for opening, closing and focussing buffers.
    """
    buffers = []
    """list of active buffers"""
    current_buffer = None
    """points to currently active :class:`~alot.buffers.Buffer`"""
    dbman = None
    """Database manager (:class:`~alot.db.DBManager`)"""

    def __init__(self, dbman, initialcmd):
        """
        :param dbman: :class:`~alot.db.DBManager`
        :param initialcmd: commandline applied after setting up interface
        :type initialcmd: str
        :param colourmode: determines which theme to chose
        :type colourmode: int in [1,16,256]
        """
        self.dbman = dbman

        colourmode = int(settings.get('colourmode'))
        logging.info('setup gui in %d colours' % colourmode)
        global_att = settings.get_theming_attribute('global', 'body')
        self.mainframe = urwid.Frame(urwid.SolidFill())
        self.mainframe_themed = urwid.AttrMap(self.mainframe, global_att)
        self.inputwrap = InputWrap(self, self.mainframe_themed)
        self.mainloop = urwid.MainLoop(self.inputwrap,
                handle_mouse=False,
                event_loop=urwid.TwistedEventLoop(),
                unhandled_input=self.unhandeled_input)
        self.mainloop.screen.set_terminal_properties(colors=colourmode)

        self.show_statusbar = settings.get('show_statusbar')
        self.notificationbar = None
        self.mode = 'global'
        self.commandprompthistory = []

        logging.debug('fire first command')
        self.apply_command(initialcmd)
        self.mainloop.run()

    def unhandeled_input(self, key):
        """called if a keypress is not handled."""
        logging.debug('unhandled input: %s' % key)

    def keypress(self, key):
        """relay all keypresses to our `InputWrap`"""
        self.inputwrap.keypress((150, 20), key)

    def show_as_root_until_keypress(self, w, key, relay_rest=True,
                                    afterwards=None):
        def oe():
            self.inputwrap.set_root(self.mainframe)
            self.inputwrap.select_cancel_only = False
            if callable(afterwards):
                logging.debug('called')
                afterwards()
        logging.debug('relay: %s' % relay_rest)
        helpwrap = widgets.CatchKeyWidgetWrap(w, key, on_catch=oe,
                                              relay_rest=relay_rest)
        self.inputwrap.set_root(helpwrap)
        self.inputwrap.select_cancel_only = not relay_rest

    def prompt(self, prefix, text=u'', completer=None, tab=0, history=[]):
        """prompt for text input

        :param prefix: text to print before the input field
        :type prefix: str
        :param text: initial content of the input field
        :type text: str
        :param completer: completion object to use
        :type completer: :meth:`alot.completion.Completer`
        :param tab: number of tabs to press initially
                    (to select completion results)
        :type tab: int
        :param history: history to be used for up/down keys
        :type history: list of str
        :returns: a :class:`twisted.defer.Deferred`
        """
        d = defer.Deferred()  # create return deferred
        oldroot = self.inputwrap.get_root()

        def select_or_cancel(text):
            # restore main screen and invoke callback
            # (delayed return) with given text
            self.inputwrap.set_root(oldroot)
            self.inputwrap.select_cancel_only = False
            d.callback(text)

        prefix = prefix + settings.get('prompt_suffix')

        #set up widgets
        leftpart = urwid.Text(prefix, align='left')
        editpart = widgets.CompleteEdit(completer, on_exit=select_or_cancel,
                                edit_text=text, history=history)

        for i in range(tab):  # hit some tabs
            editpart.keypress((0,), 'tab')

        # build promptwidget
        both = urwid.Columns(
            [
                ('fixed', len(prefix), leftpart),
                ('weight', 1, editpart),
            ])
        att = settings.get_theming_attribute('global', 'prompt')
        both = urwid.AttrMap(both, att)

        # put promptwidget as overlay on main widget
        overlay = urwid.Overlay(both, oldroot,
                                ('fixed left', 0),
                                ('fixed right', 0),
                                ('fixed bottom', 1),
                                None)
        self.inputwrap.set_root(overlay)
        self.inputwrap.select_cancel_only = True
        return d  # return deferred

    def exit(self):
        """
        shuts down user interface without cleaning up.
        Use a :class:`commands.globals.ExitCommand` for a clean shutdown.
        """
        exit_msg = None
        try:
            reactor.stop()
        except Exception as e:
            exit_msg = 'Could not stop reactor: {}.'.format(e)
            logging.error(exit_msg + '\nShutting down anyway..')

    def buffer_open(self, buf):
        """register and focus new :class:`~alot.buffers.Buffer`."""
        self.buffers.append(buf)
        self.buffer_focus(buf)

    def buffer_close(self, buf):
        """
        closes given :class:`~alot.buffers.Buffer`.

        This it removes it from the bufferlist and calls its cleanup() method.
        """

        buffers = self.buffers
        if buf not in buffers:
            string = 'tried to close unknown buffer: %s. \n\ni have:%s'
            logging.error(string % (buf, self.buffers))
        elif self.current_buffer == buf:
            logging.debug('UI: closing current buffer %s' % buf)
            index = buffers.index(buf)
            buffers.remove(buf)
            offset = settings.get('bufferclose_focus_offset')
            nextbuffer = buffers[(index + offset) % len(buffers)]
            self.buffer_focus(nextbuffer)
            buf.cleanup()
        else:
            string = 'closing buffer %d:%s'
            logging.debug(string % (buffers.index(buf), buf))
            buffers.remove(buf)
            buf.cleanup()

    def buffer_focus(self, buf):
        """focus given :class:`~alot.buffers.Buffer`."""
        if buf not in self.buffers:
            logging.error('tried to focus unknown buffer')
        else:
            if self.current_buffer != buf:
                self.current_buffer = buf
                self.inputwrap.set_root(self.mainframe_themed)
            self.mode = buf.modename
            if isinstance(self.current_buffer, BufferlistBuffer):
                self.current_buffer.rebuild()
            self.update()

    def get_deep_focus(self, startfrom=None):
        """return the bottom most focussed widget of the widget tree"""
        if not startfrom:
            startfrom = self.current_buffer
        if 'get_focus' in dir(startfrom):
            focus = startfrom.get_focus()
            if isinstance(focus, tuple):
                focus = focus[0]
            if isinstance(focus, urwid.Widget):
                return self.get_deep_focus(startfrom=focus)
        return startfrom

    def get_buffers_of_type(self, t):
        """
        returns currently open buffers for a given subclass of
        :class:`alot.buffer.Buffer`
        """
        return filter(lambda x: isinstance(x, t), self.buffers)

    def clear_notify(self, messages):
        """
        clears notification popups. Call this to ged rid of messages that don't
        time out.

        :param messages: The popups to remove. This should be exactly
                         what :meth:`notify` returned when creating the popup
        """
        newpile = self.notificationbar.widget_list
        for l in messages:
            if l in newpile:
                newpile.remove(l)
        if newpile:
            self.notificationbar = urwid.Pile(newpile)
        else:
            self.notificationbar = None
        self.update()

    def choice(self, message, choices={'y': 'yes', 'n': 'no'},
               select=None, cancel=None, msg_position='above'):
        """
        prompt user to make a choice

        :param message: string to display before list of choices
        :type message: unicode
        :param choices: dict of possible choices
        :type choices: dict: keymap->choice (both str)
        :param select: choice to return if enter/return is hit. Ignored if set
                       to `None`.
        :type select: str
        :param cancel: choice to return if escape is hit. Ignored if set to
                       `None`.
        :type cancel: str
        :param msg_position: determines if `message` is above or left of the
                             prompt. Must be `above` or `left`.
        :type msg_position: str
        :returns: a :class:`twisted.defer.Deferred`
        """
        assert select in choices.values() + [None]
        assert cancel in choices.values() + [None]
        assert msg_position in ['left', 'above']

        d = defer.Deferred()  # create return deferred
        oldroot = self.inputwrap.get_root()

        def select_or_cancel(text):
            self.inputwrap.set_root(oldroot)
            self.inputwrap.select_cancel_only = False
            d.callback(text)

        #set up widgets
        msgpart = urwid.Text(message)
        choicespart = widgets.ChoiceWidget(choices, callback=select_or_cancel,
                                           select=select, cancel=cancel)

        # build widget
        if msg_position == 'left':
            both = urwid.Columns(
                [
                    ('fixed', len(message), msgpart),
                    ('weight', 1, choicespart),
                ], dividechars=1)
        else:  # above
            both = urwid.Pile([msgpart, choicespart])
        att = settings.get_theming_attribute('global', 'prompt')
        both = urwid.AttrMap(both, att, att)

        # put promptwidget as overlay on main widget
        overlay = urwid.Overlay(both, oldroot,
                                ('fixed left', 0),
                                ('fixed right', 0),
                                ('fixed bottom', 1),
                                None)
        self.inputwrap.set_root(overlay)
        self.inputwrap.select_cancel_only = True
        return d  # return deferred

    def notify(self, message, priority='normal', timeout=0, block=False):
        """
        opens notification popup

        :param message: message to print
        :type message: str
        :param priority: priority string, used to format the popup: currently,
                         'normal' and 'error' are defined. If you use 'X' here,
                         the attribute 'global_notify_X' is used to format the
                         popup.
        :type priority: str
        :param timeout: seconds until message disappears. Defaults to the value
                        of 'notify_timeout' in the general config section.
                        A negative value means never time out.
        :type timeout: int
        :param block: this notification blocks until a keypress is made
        :type block: bool
        :returns: an urwid widget (this notification) that can be handed to
                  :meth:`clear_notify` for removal
        """
        def build_line(msg, prio):
            cols = urwid.Columns([urwid.Text(msg)])
            att = settings.get_theming_attribute('global', 'notify_' + prio)
            return urwid.AttrMap(cols, att)
        msgs = [build_line(message, priority)]

        if not self.notificationbar:
            self.notificationbar = urwid.Pile(msgs)
        else:
            newpile = self.notificationbar.widget_list + msgs
            self.notificationbar = urwid.Pile(newpile)
        self.update()

        def clear(*args):
            self.clear_notify(msgs)

        if block:
            # put "cancel to continue" widget as overlay on main widget
            txt = urwid.Text('(cancel continues)')
            overlay = urwid.Overlay(txt, self.mainframe,
                                    ('fixed left', 0),
                                    ('fixed right', 0),
                                    ('fixed bottom', 0),
                                    None)
            self.show_as_root_until_keypress(overlay, 'cancel',
                                             relay_rest=False,
                                             afterwards=clear)
        else:
            if timeout >= 0:
                if timeout == 0:
                    timeout = settings.get('notify_timeout')
                self.mainloop.set_alarm_in(timeout, clear)
        return msgs[0]

    def update(self):
        """redraw interface"""
        #who needs a header?
        #head = urwid.Text('notmuch gui')
        #h=urwid.AttrMap(head, 'header')
        #self.mainframe.set_header(h)

        # body
        if self.current_buffer:
            self.mainframe.set_body(self.current_buffer)

        # footer
        lines = []
        if self.notificationbar:  # .get_text()[0] != ' ':
            lines.append(self.notificationbar)
        if self.show_statusbar:
            lines.append(self.build_statusbar())

        if lines:
            self.mainframe.set_footer(urwid.Pile(lines))
        else:
            self.mainframe.set_footer(None)
        # force a screen redraw
        if self.mainloop.screen.started:
            self.mainloop.draw_screen()

    def build_statusbar(self):
        """construct and return statusbar widget"""
        if self.current_buffer is not None:
            idx = self.buffers.index(self.current_buffer)
            lefttxt = '%d: %s' % (idx, self.current_buffer)
        else:
            lefttxt = '[no buffers]'
        footerleft = urwid.Text(lefttxt, align='left')
        righttxt = 'total messages: %d' % self.dbman.count_messages('*')
        pending_writes = len(self.dbman.writequeue)
        if pending_writes > 0:
            righttxt = ('|' * pending_writes) + ' ' + righttxt
        footerright = urwid.Text(righttxt, align='right')
        columns = urwid.Columns([
            footerleft,
            ('fixed', len(righttxt), footerright)])
        footer_att = settings.get_theming_attribute('global', 'footer')
        return urwid.AttrMap(columns, footer_att)

    def apply_command(self, cmd):
        """
        applies a command

        This calls the pre and post hooks attached to the command,
        as well as :meth:`cmd.apply`.

        :param cmd: an applicable command
        :type cmd: :class:`~alot.commands.Command`
        """
        if cmd:
            # call pre- hook
            if cmd.prehook:
                logging.debug('calling pre-hook')
                try:
                    cmd.prehook(ui=self, dbm=self.dbman)
                except:
                    logging.exception('prehook failed')
                    return False

            # define (callback) function that invokes post-hook
            def call_posthook(retval_from_apply):
                if cmd.posthook:
                    logging.debug('calling post-hook')
                    try:
                        cmd.posthook(ui=self, dbm=self.dbman)
                    except:
                        logging.exception('posthook failed')

            # define error handler for Failures/Exceptions
            # raised in cmd.apply()
            def errorHandler(failure):
                logging.debug(failure.getTraceback())
                msg = "Error: %s,\ncheck the log for details"
                self.notify(msg % failure.getErrorMessage(), priority='error')

            # call cmd.apply
            logging.debug('apply command: %s' % cmd)
            d = defer.maybeDeferred(cmd.apply, self)
            d.addErrback(errorHandler)
            d.addCallback(call_posthook)
