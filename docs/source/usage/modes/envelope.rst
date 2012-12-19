.. CAUTION: THIS FILE IS AUTO-GENERATED!


Commands in `envelope` mode
---------------------------
The following commands are available in envelope mode

.. _cmd.envelope.set:

.. describe:: set

    set header value

    positional arguments
        0: header to refine
        1: value


    optional arguments
        :---append: keep previous values.

.. _cmd.envelope.togglesign:

.. describe:: togglesign

    toggle sign status

    argument
        which key id to use


.. _cmd.envelope.toggleheaders:

.. describe:: toggleheaders

    toggle display of all headers


.. _cmd.envelope.edit:

.. describe:: edit

    edit mail

    optional arguments
        :---spawn: spawn editor in new terminal.
        :---refocus: refocus envelope after editing (Defaults to: 'True').

.. _cmd.envelope.send:

.. describe:: send

    send mail


.. _cmd.envelope.sign:

.. describe:: sign

    mark mail to be signed before sending

    argument
        which key id to use


.. _cmd.envelope.attach:

.. describe:: attach

    attach files to the mail

    argument
        file(s) to attach (accepts wildcads)


.. _cmd.envelope.refine:

.. describe:: refine

    prompt to change the value of a header

    argument
        header to refine


.. _cmd.envelope.save:

.. describe:: save

    save draft


.. _cmd.envelope.unsign:

.. describe:: unsign

    mark mail not to be signed before sending


.. _cmd.envelope.unset:

.. describe:: unset

    remove header field

    argument
        header to refine

.. _cmd.envelope.encrypt:

.. describe:: encrypt

    mark mail to be encrypted with given key before sending

    argument
        key id to sign with

.. _cmd.envelope.unencrypt:

.. describe:: unencrypt

    mark mail not to be encrypted

