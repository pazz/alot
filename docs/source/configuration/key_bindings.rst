.. _config.key_bindings:

Key Bindings
============
If you want to bind a command to a key you can do so by adding the pair to the
`[bindings]` section. This will introduce a *global* binding, that works in
all modes. To make a binding specific to a mode you have to add the pair
under the subsection named like the mode. For instance,
if you want to bind `T` to open a new search for threads tagged with 'todo',
and be able to toggle this tag in search mode, you'd add this to your config

.. sourcecode:: ini

    [bindings]
      T = search tag:todo

      [[search]]
      t = toggletags todo

.. _modes:

Known modes are:

* bufferlist
* envelope
* namedqueries
* search
* taglist
* thread

Have a look at `the urwid User Input documentation <http://excess.org/urwid/wiki/UserInput>`_ on how key strings are formatted.

.. _config.key-bingings.defaults:

Default bindings
----------------

User-defined bindings are combined with the default bindings listed below.

.. literalinclude:: ../../../alot/defaults/default.bindings
  :language: ini

In prompts the following hardcoded bindings are available.

=========================== ========
Key                         Function
=========================== ========
Ctrl-f/b                    Moves the curser one character to the right/left
Alt-f/b Shift-right/left    Moves the cursor one word to the right/left
Ctrl-a/e                    Moves the curser to the beginning/end of the line
Ctrl-d                      Deletes the character under the cursor
Alt-d                       Deletes everything from the cursor to the end of the current or next word
Alt-Delete/Backspace Ctrl-w Deletes everything from the cursor to the beginning of the current or previous word
Ctrl-k                      Deletes everything from the cursor to the end of the line
Ctrl-u                      Deletes everything from the cursor to the beginning of the line
=========================== ========

Overwriting defaults
--------------------

To disable a global binding you can redefine it in your config to point to an empty command string.
For example, to add a new global binding for key `a`, which is bound to `toggletags inbox` in search
mode by default, you can remap it as follows.

.. sourcecode:: ini

    [bindings]
      a = NEW GLOBAL COMMAND

      [[search]]
        a =

If you omit the last two lines, `a` will still be bound to the default binding in search mode.
