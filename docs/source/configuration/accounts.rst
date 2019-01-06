.. _config.accounts:

Accounts
========
In order to be able to send mails, you have to define at least one account subsection in your config:
There needs to be a section "accounts", and each subsection, indicated by double square brackets defines an account.

Here is an example configuration

.. code-block:: ini

    [accounts]
        [[work]]
            realname = Bruce Wayne
            address = b.wayne@wayneenterprises.com
            alias_regexp = b.wayne\+.+@wayneenterprises.com
            gpg_key = D7D6C5AA
            sendmail_command = msmtp --account=wayne -t
            sent_box = maildir:///home/bruce/mail/work/Sent
            # ~ expansion also works
            draft_box = maildir://~/mail/work/Drafts

        [[secret]]
            realname = Batman
            address = batman@batcave.org
            aliases = batman@batmobile.org,
            sendmail_command = msmtp --account=batman -t
            signature = ~/.batman.vcf
            signature_as_attachment = True

.. warning::

  Sending mails is only supported via a sendmail shell command for now. If you want
  to use a sendmail command different from `sendmail -t`, specify it as `sendmail_command`.

The following entries are interpreted at the moment:

.. include:: accounts_table
