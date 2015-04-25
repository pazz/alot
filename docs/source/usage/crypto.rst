Cryptography
============

Alot has built in support for constructing signed and/or encrypted mails
according to PGP/MIME (:rfc:`3156`, :rfc:`3156`) via gnupg.
It does however rely on a running `gpg-agent` to handle password entries.

.. note:: You need to have `gpg-agent` running to use GPG with alot!

  `gpg-agent` will handle passphrase entry in a secure and configurable way, and it will cache your
  passphrase for some time so you don’t have to enter it over and over again. For details on how to
  set this up we refer to `gnupg's manual <http://www.gnupg.org/documentation/manuals/gnupg/>`_.

.. rubric:: Signing outgoing emails

You can use the commands :ref:`sign <cmd.envelope.sign>`,
:ref:`unsign <cmd.envelope.unsign>` and
:ref:`togglesign <cmd.envelope.togglesign>` in envelope mode
to determine if you want this mail signed and if so, which key to use.
To specify the key to use you may pass a hint string as argument to
the `sign` or `togglesign` command. This hint would typically
be a fingerprint or an email address associated (by gnupg) with a key.

Signing (and hence passwd entry) will be done at most once shortly before
a mail is sent.

In case no key is specified, alot will leave the selection of a suitable key to gnupg
so you can influence that by setting the `default-key` option in :file:`~/.gnupg/gpg.conf`
accordingly.

You can set the default to-sign bit and the key to use for each :ref:`account <config.accounts>`
individually using the options :ref:`sign_by_default <sign-by-default>` and :ref:`gpg_key <gpg-key>`.

.. rubric:: Encrypt outgoing emails

You can use the commands :ref:`encrypt <cmd.envelope.encrypt>`,
:ref:`unencrypt <cmd.envelope.unencrypt>` and
and :ref:`toggleencrypt <cmd.envelope.toggleencrypt>` and
in envelope mode to ask alot to encrypt the mail before sending.
The :ref:`encrypt <cmd.envelope.encrypt>` command accepts an optional
hint string as argument to determine the key of the recipient.

You can set the default to-encrypt bit for each :ref:`account <config.accounts>`
individually using the option :ref:`encrypt_by_default <encrypt-by-default>`.

.. note::
    If you want to access encrypt mail later it is useful to add yourself to the
    list of recipients when encrypting with gpg (not the recipients whom mail is
    actually send to). The simplest way to do this is to use the `encrypt-to`
    option in the :file:`~/.gnupg/gpg.conf`. But you might have to specify the
    correct encryption subkey otherwise gpg seems to throw an error.
