Email Database
==============

.. module:: alot.db

The python bindings to libnotmuch define :class:`notmuch.Thread` and
:class:`notmuch.Message`, which unfortunately are very fragile.
Alot defines the wrapper classes :class:`alot.db.Thread` and :class:`alot.db.Message` that
use an :class:`manager.DBManager` instance to transparently provide persistent objects.

:class:`alot.db.Message` moreover contains convenience methods
to extract information about the message like reformated header values, a summary,
decoded and interpreted body text and a list of :class:`Attachments <alot.db.attachment.Attachment>`.

The central :class:`~alot.ui.UI` instance carries around a :class:`~manager.DBManager` object that
is used for any lookups or modifications of the email base. :class:`~manager.DBManager` can
directly look up :class:`Thread` and :class:`~alot.db.Message` objects and is able to
postpone/cache/retry writing operations in case the Xapian index is locked by another
process.


Database Manager
-----------------
.. autoclass:: alot.db.manager.DBManager
   :members:


Errors
----------

.. module:: alot.db.errors

.. autoclass:: DatabaseError
   :members:
.. autoclass:: DatabaseROError
   :members:
.. autoclass:: DatabaseLockedError
   :members:
.. autoclass:: NonexistantObjectError
   :members:

Wrapper
-------
.. autoclass:: alot.db.Thread
   :members:


.. autoclass:: alot.db.Message
   :members:


Other Structures
----------------

.. autoclass:: alot.db.attachment.Attachment
   :members:

.. autoclass:: alot.db.envelope.Envelope
   :members:


Utilities
---------

.. automodule:: alot.db.utils
   :members:
