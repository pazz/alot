thread
------
The following commands are available in thread mode

.. index:: pipeto

pipeto
______

pipe message(s) to stdin of a shellcommand

argument
	shellcommand to pipe to

optional arguments
	:---all: pass all messages.
	:---format: output format. Valid choices are: \`raw\`,\`decoded\`,\`id\`,\`filepath\` (Defaults to: 'raw').
	:---separately: call command once for each message.
	:---background: don't stop the interface.
	:---add_tags: add 'Tags' header to the message.
	:---shell: let the shell interpret the command.
	:---notify_stdout: display command's stdout as notification message.

.. index:: editnew

editnew
_______

edit message in as new

optional arguments
	:---spawn: open editor in new window.

.. index:: toggleheaders

toggleheaders
_____________

display all headers

optional arguments
	:---all: affect all messages.

.. index:: print

print
_____

print message(s)

optional arguments
	:---all: print all messages.
	:---raw: pass raw mail string.
	:---separately: call print command once for each message.
	:---add_tags: add 'Tags' header to the message.

.. index:: remove

remove
______

remove message(s) from the index

optional arguments
	:---all: remove whole thread.

.. index:: togglesource

togglesource
____________

display message source

optional arguments
	:---all: affect all messages.

.. index:: retag

retag
_____

set message(s) tags.

argument
	comma separated list of tags

optional arguments
	:---all: tag all messages in thread.
	:---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. index:: fold

fold
____

fold message(s)

optional arguments
	:---all: fold all messages.

.. index:: tag

tag
___

add tags to message(s)

argument
	comma separated list of tags

optional arguments
	:---all: tag all messages in thread.
	:---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. index:: untag

untag
_____

remove tags from message(s)

argument
	comma separated list of tags

optional arguments
	:---all: tag all messages in thread.
	:---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. index:: unfold

unfold
______

unfold message(s)

optional arguments
	:---all: unfold all messages.

.. index:: forward

forward
_______

forward message

optional arguments
	:---attach: attach original mail.
	:---spawn: open editor in new window.

.. index:: reply

reply
_____

reply to message

optional arguments
	:---all: reply to all.
	:---spawn: open editor in new window.

.. index:: save

save
____

save attachment(s)

argument
	path to save to

optional arguments
	:---all: save all attachments.

.. index:: toggletags

toggletags
__________

flip presence of tags on message(s)

argument
	comma separated list of tags

optional arguments
	:---all: tag all messages in thread.
	:---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. index:: select

select
______

select focussed element. The fired action depends on the focus:
        - if message summary, this toggles visibility of the message,
        - if attachment line, this opens the attachment


