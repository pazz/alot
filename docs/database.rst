Email Database
==============

.. module:: alot.db

The python bindings to libnotmuch define :class:`notmuch.Thread` and 
:class:`notmuch.Message`, which unfortunately are very fragile.
Alot defines the wrapper classes :class:`Thread` and :class:`~alot.message.Message` that
use an :class:`DBManager` instance to transparently provide persistent objects.

:class:`~alot.message.Message` moreover contains convenience methods
to extract information about the message like reformated header values, a summary,
decoded and interpreted body text and a list of :class:`Attachments <alot.message.Attachment>`.

The central :class:`~alot.ui.UI` instance carries around a :class:`DBManager` object that
is used for any lookups or modifications of the email base. :class:`DBManager` can
directly look up :class:`Thread` and :class:`~alot.message.Message` objects and is able to
postpone/cache/retry writing operations in case the Xapian index is locked by another
process.


:class:`DBManager`
---------------------------
.. autoclass:: DBManager
   :members:

:class:`Thread`
---------------------------
.. autoclass:: Thread
   :members:

.. module:: alot.message

:class:`Message`
---------------------------
.. autoclass:: Message
   :members:

:class:`Attachment`
---------------------------
.. autoclass:: Attachment
   :members:
