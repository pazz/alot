.. CAUTION: THIS FILE IS AUTO-GENERATED!


Commands in 'envelope' mode
---------------------------
The following commands are available in envelope mode:

.. _cmd.envelope.attach:

.. describe:: attach

    attach files to the mail

    argument
        file(s) to attach (accepts wildcads)


.. _cmd.envelope.edit:

.. describe:: edit

    edit mail

    optional arguments
        :---spawn: spawn editor in new terminal
        :---refocus: refocus envelope after editing (defaults to: 'True')

.. _cmd.envelope.encrypt:

.. describe:: encrypt

    request encryption of message before sendout

    argument
        keyid of the key to encrypt with

    optional arguments
        :---trusted: only add trusted keys

.. _cmd.envelope.refine:

.. describe:: refine

    prompt to change the value of a header

    argument
        header to refine


.. _cmd.envelope.retag:

.. describe:: retag

    set message tags

    argument
        comma separated list of tags


.. _cmd.envelope.rmencrypt:

.. describe:: rmencrypt

    do not encrypt to given recipient key

    argument
        keyid of the key to encrypt with


.. _cmd.envelope.save:

.. describe:: save

    save draft


.. _cmd.envelope.send:

.. describe:: send

    send mail


.. _cmd.envelope.set:

.. describe:: set

    set header value

    positional arguments
        0: header to refine
        1: value


    optional arguments
        :---append: keep previous values

.. _cmd.envelope.sign:

.. describe:: sign

    mark mail to be signed before sending

    argument
        which key id to use


.. _cmd.envelope.tag:

.. describe:: tag

    add tags to message

    argument
        comma separated list of tags


.. _cmd.envelope.toggleencrypt:

.. describe:: toggleencrypt

    toggle if message should be encrypted before sendout

    argument
        keyid of the key to encrypt with

    optional arguments
        :---trusted: only add trusted keys

.. _cmd.envelope.toggleheaders:

.. describe:: toggleheaders

    toggle display of all headers


.. _cmd.envelope.togglesign:

.. describe:: togglesign

    toggle sign status

    argument
        which key id to use


.. _cmd.envelope.toggletags:

.. describe:: toggletags

    flip presence of tags on message

    argument
        comma separated list of tags


.. _cmd.envelope.unattach:

.. describe:: unattach

    remove attachments from current envelope

    argument
        which attached file to remove


.. _cmd.envelope.unencrypt:

.. describe:: unencrypt

    remove request to encrypt message before sending


.. _cmd.envelope.unset:

.. describe:: unset

    remove header field

    argument
        header to refine


.. _cmd.envelope.unsign:

.. describe:: unsign

    mark mail not to be signed before sending


.. _cmd.envelope.untag:

.. describe:: untag

    remove tags from message

    argument
        comma separated list of tags


