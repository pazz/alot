.. CAUTION: THIS FILE IS AUTO-GENERATED!


envelope
--------
The following commands are available in envelope mode

.. _cmd_envelope_set:
.. index:: set

set
___

set header value

positional arguments
	:0: header to refine
	:1: value


optional arguments
	:---append: keep previous values.

.. _cmd_envelope_togglesign:
.. index:: togglesign

togglesign
__________

toggle sign status

argument
	which key id to use


.. _cmd_envelope_toggleheaders:
.. index:: toggleheaders

toggleheaders
_____________

toggle display of all headers


.. _cmd_envelope_edit:
.. index:: edit

edit
____

edit mail

optional arguments
	:---spawn: spawn editor in new terminal.
	:---refocus: refocus envelope after editing (Defaults to: 'True').

.. _cmd_envelope_send:
.. index:: send

send
____

send mail


.. _cmd_envelope_sign:
.. index:: sign

sign
____

mark mail to be signed before sending

argument
	which key id to use


.. _cmd_envelope_attach:
.. index:: attach

attach
______

attach files to the mail

argument
	file(s) to attach (accepts wildcads)


.. _cmd_envelope_refine:
.. index:: refine

refine
______

prompt to change the value of a header

argument
	header to refine


.. _cmd_envelope_save:
.. index:: save

save
____

save draft


.. _cmd_envelope_unsign:
.. index:: unsign

unsign
______

mark mail not to be signed before sending


.. _cmd_envelope_unset:
.. index:: unset

unset
_____

remove header field

argument
	header to refine


