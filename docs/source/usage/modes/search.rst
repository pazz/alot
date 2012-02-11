search
------
The following commands are available in search mode

.. index:: sort

sort
____

set sort order

argument
	sort order. valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.


.. index:: untag

untag
_____

remove tags from all messages in the thread

argument
	comma separated list of tags

optional arguments
	:---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. index:: retag

retag
_____

set tags of all messages in the thread

argument
	comma separated list of tags

optional arguments
	:---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. index:: refineprompt

refineprompt
____________

prompt to change this buffers querystring


.. index:: tag

tag
___

add tags to all messages in the thread

argument
	comma separated list of tags

optional arguments
	:---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. index:: refine

refine
______

refine query

argument
	search string

optional arguments
	:---sort: sort order. Valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.

.. index:: retagprompt

retagprompt
___________

prompt to retag selected threads' tags


.. index:: toggletags

toggletags
__________

flip presence of tags on this thread.
    A tag is considered present if at least one message contained in this
    thread is tagged with it. In that case this command will remove the tag
    from every message in the thread.
    

argument
	comma separated list of tags

optional arguments
	:---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. index:: select

select
______

open thread in a new buffer


