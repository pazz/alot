.. _cryptography

************
Cryptography
************

At the moment alot only supports signing of outgoing mails via PGP/MIME (:rfc:`3156`).

.. note:: To use GPG with alot, you need to have `gpg-agent` running.

  `gpg-agent` will handle passphrase entry in a secure and configurable way, and it will cache your passphrase for some
  amount of time so you don’t have to enter it over and over again. For details on how to set this up we refer to
  `gnupg's manual <http://www.gnupg.org/documentation/manuals/gnupg/>`_.

.. rubric:: Signing outgoing emails

You can use the commands `sign`, `unsign` and `togglesign` in envelope mode
to determine if you want this mail signed and if so, which key to use.
To specify the key to use you can pass a hint string as argument to
the `sign` or `togglesign` command. This hint would typically
be a fingerprint or an email address associated (by gnupg) with a key.

Signing (and hence passwd entry) will be done at most once shortly before
a mail is sent.

In case no key is specified, alot will leave the selection of a suitable key to gnupg
so you can influence that by setting the `default-key` option in :file:`~/.gnupg/gpg.conf`
accordingly.

You can set the default to-sign bit and the key to use for each :ref:`account <account>`
individually using the options :ref:`sign_by_default <sign-by-default>` and :ref:`gpg_key <gpg-key>`.


.. rubric:: Tips

In case you are using alot via SSH, we recommend to use `pinentry-curses`
instead of the default graphical pinentry. You can do that by setting up your
:file:`~/.gnupg/gpg-agent.conf` like this::

    pinentry-program /usr/bin/pinentry-curses


