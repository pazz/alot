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

.. index:: togglesign

togglesign
__________

toggle sign status

argument
	which key id to use


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


.. index:: sign

sign
____

mark mail to be signed before sending

argument
	which key id to use


.. index:: attach

attach
______

attach files to the mail

argument
	file(s) to attach (accepts wildcads)


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


.. index:: unsign

unsign
______

mark mail not to be signed before sending


.. index:: unset

unset
_____

remove header field

argument
	header to refine


