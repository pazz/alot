envelope
--------
The following commands are available in envelope mode

.. index:: set

set
___

set header value

positional arguments
	:0: header to refine
	:1: value


optional arguments
	:---append: keep previous values.

.. index:: toggleheaders

toggleheaders
_____________

toggle display of all headers


.. index:: edit

edit
____

edit mail

optional arguments
	:---spawn: force spawning of editor in a new terminal.
	:---no-refocus: don't refocus envelope after editing (Defaults to: 'True').

.. index:: send

send
____

send mail


.. index:: attach

attach
______

attach files to the mail

argument
	file(s) to attach (accepts wildcards)


.. index:: refine

refine
______

prompt to change the value of a header

argument
	header to refine


.. index:: save

save
____

save draft


.. index:: unset

unset
_____

remove header field

argument
	header to refine


