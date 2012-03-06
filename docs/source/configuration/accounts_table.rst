
.. _address:

.. describe:: address

    your main email address

    :type: string

.. _realname:

.. describe:: realname

    used to format the (proposed) From-header in outgoing mails

    :type: string

.. _aliases:

.. describe:: aliases

    used to clear your addresses/ match account when formatting replies

    :type: string_list
    :default: ","


.. _sendmail-command:

.. describe:: sendmail_command

    sendmail command. This is the shell command used to send out mails via the sendmail protocol

    :type: string
    :default: "sendmail"


.. _sent-box:

.. describe:: sent_box

    specifies the mailbox where you want outgoing mails to be stored after successfully sending them, e.g. 
    where to store outgoing mail, e.g. `maildir:///home/you/mail//Sent`
    You can use mbox, maildir, mh, babyl and mmdf in the protocol part of the URL.

    :type: string
    :default: None


.. _sent-tags:

.. describe:: sent_tags

    list of tags to automatically add to outgoing messages

    :type: string_list
    :default: "sent,"


.. _signature:

.. describe:: signature

    path to signature file that gets attached to all outgoing mails from this account, optionally
    renamed to ref:`signature_filename <signature-filename>`.

    :type: string
    :default: None


.. _signature-as-attachment:

.. describe:: signature_as_attachment

    attach signature file if set to True, append its content (mimetype text)
    to the body text if set to False.

    :type: boolean
    :default: False


.. _signature-filename:

.. describe:: signature_filename

    signature file's name as it appears in outgoing mails if
    :ref:`signature_as_attachment <signature-as-attachment>` is set to True

    :type: string
    :default: None

