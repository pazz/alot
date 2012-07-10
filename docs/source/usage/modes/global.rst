.. CAUTION: THIS FILE IS AUTO-GENERATED!


global
------
The following commands are available globally

.. _cmd_global_bclose:
.. index:: bclose

bclose
______

close a buffer


.. _cmd_global_bprevious:
.. index:: bprevious

bprevious
_________

focus previous buffer


.. _cmd_global_search:
.. index:: search

search
______

open a new search buffer

argument
	search string

optional arguments
	:---sort: sort order. Valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.

.. _cmd_global_compose:
.. index:: compose

compose
_______

compose a new email

optional arguments
	:---sender: sender.
	:---template: path to a template message file.
	:---subject: subject line.
	:---to: recipients.
	:---cc: copy to.
	:---bcc: blind copy to.
	:---attach: attach files.
	:---omit_signature: do not add signature.
	:---spawn: spawn editor in new terminal.

.. _cmd_global_prompt:
.. index:: prompt

prompt
______

prompts for commandline and interprets it upon select

argument
	initial content


.. _cmd_global_help:
.. index:: help

help
____


    display help for a command. Use 'bindings' to
    display all keybings interpreted in current mode.'
    

argument
	command or 'bindings'


.. _cmd_global_move:
.. index:: move

move
____

move focus

argument
	direction


.. _cmd_global_shellescape:
.. index:: shellescape

shellescape
___________

run external command

argument
	command line to execute

optional arguments
	:---spawn: run in terminal window.
	:---thread: run in separate thread.
	:---refocus: refocus current buffer                      after command has finished.

.. _cmd_global_refresh:
.. index:: refresh

refresh
_______

refresh the current buffer


.. _cmd_global_cancel:
.. index:: cancel

cancel
______

send cancel event


.. _cmd_global_pyshell:
.. index:: pyshell

pyshell
_______

open an interactive python shell for introspection


.. _cmd_global_exit:
.. index:: exit

exit
____

shut down cleanly


.. _cmd_global_flush:
.. index:: flush

flush
_____

flush write operations or retry until committed


.. _cmd_global_bufferlist:
.. index:: bufferlist

bufferlist
__________

open a list of active buffers


.. _cmd_global_bnext:
.. index:: bnext

bnext
_____

focus next buffer


.. _cmd_global_select:
.. index:: select

select
______

send select event


.. _cmd_global_taglist:
.. index:: taglist

taglist
_______

opens taglist buffer


