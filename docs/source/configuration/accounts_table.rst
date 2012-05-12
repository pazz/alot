..
    CAUTION: THIS FILE IS AUTO-GENERATED
    from the inline comments of specfile defaults/alot.rc.spec.

    If you want to change its content make your changes
    to that spec to ensure they woun't be overwritten later.

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
    :default: `,`


.. _sendmail-command:

.. describe:: sendmail_command

    sendmail command. This is the shell command used to send out mails via the sendmail protocol

    :type: string
    :default: `sendmail -t`


.. _sent-box:

.. describe:: sent_box

    where to store outgoing mails, e.g. `maildir:///home/you/mail//Sent`
    You can use mbox, maildir, mh, babyl and mmdf in the protocol part of the URL.

    :type: mail_container
    :default: None


.. _draft-box:

.. describe:: draft_box

    where to store draft mails, see :ref:`sent_box <sent-box>` for the format

    :type: mail_container
    :default: None


.. _sent-tags:

.. describe:: sent_tags

    list of tags to automatically add to outgoing messages

    :type: string_list
    :default: `sent,`


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

