global
------
The following commands are available globally

.. index:: bclose

bclose
______

close a buffer


.. index:: bprevious

bprevious
_________

focus previous buffer


.. index:: search

search
______

open a new search buffer

argument
	search string

optional arguments
	:---sort: sort order. Valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.

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

.. index:: prompt

prompt
______

prompts for commandline and interprets it upon select

argument
	initial content


.. index:: help

help
____


    display help for a command. Use 'bindings' to
    display all keybings interpreted in current mode.'
    

argument
	command or 'bindings'


.. index:: move

move
____

move focus

argument
	direction


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

.. index:: refresh

refresh
_______

refresh the current buffer


.. index:: cancel

cancel
______

send cancel event


.. index:: pyshell

pyshell
_______

open an interactive python shell for introspection


.. index:: exit

exit
____

shut down cleanly


.. index:: flush

flush
_____

flush write operations or retry until committed


.. index:: bufferlist

bufferlist
__________

open a list of active buffers


.. index:: bnext

bnext
_____

focus next buffer


.. index:: select

select
______

send select event


.. index:: taglist

taglist
_______

opens taglist buffer


