import os


def touch_external_cmdlist(cmd, shell=False, spawn=False, thread=False):
    # Used to handle the case where tmux isn't running within X11
    if spawn and 'TMUX' in os.environ:
        termcmdlist = ['tmux-horizontal-split-blocking.sh']
        cmd = termcmdlist + cmd
        # Required to avoid tmux trying to nest itself.
        shell = False

    return cmd, shell, thread
