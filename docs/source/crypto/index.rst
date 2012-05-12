.. _cryptography

**********************
Cryptography (PGP/GPG)
**********************

alot aims to support GPG cryptography. Currently, only sending signed emails is
supported, but signature verification, encryption and decryption are planned.

To use GPG with alot, you need to have `gpg-agent` running. `gpg-agent` will
handle passphrase entry in a secure and configurable way, and it will cache
your passphrase for some amount of time so you don’t have to enter it over and
over again.

In case you are using alot via SSH, we recommend to use `pinentry-curses`
instead of the default graphical pinentry. You can do that by setting up your
:file:`~/.gnupg/gpg-agent.conf` like this::

    pinentry-program /usr/bin/pinentry-curses


Signing outgoing emails
=======================

After composing a message and before sending it, use the `togglesign` command
(bound to the S key in the default config) to make alot sign your email.

By default, alot will leave the selection of a suitable GPG key to GPGME (the
GPG library we use), so you can influence that by setting the `default-key`
option in :file:`~/.gnupg/gpg.conf` accordingly.

In case you want to use a specific key to sign an email, you can pass that key
id to the `togglesign` command, for example `togglesign 4AC8EE1D`.
