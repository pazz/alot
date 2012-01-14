search-mode
-----------

sort
____

set sort order

argument
	sort order. valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.




untag
_____

remove tags from all messages in the thread

argument
	comma separated list of tags




retag
_____

set tags of all messages in the thread

argument
	comma separated list of tags




refineprompt
____________

prompt to change this buffers querystring




tag
___

add tags to all messages in the thread

argument
	comma separated list of tags




refine
______

refine query

argument
	search string

optional arguments
	:---sort: sort order. Valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.



retagprompt
___________

prompt to retag selected threads' tags




toggletags
__________

flip presence of tags on this thread.
    A tag is considered present if at least one message contained in this
    thread is tagged with it. In that case this command will remove the tag
    from every message in the thread.
    

argument
	comma separated list of tags




select
______

open thread in a new buffer



thread-mode
-----------

pipeto
______

pipe message(s) to stdin of a shellcommand

argument
	shellcommand to pipe to

optional arguments
	:---all: pass all messages.
	:---format: output format. Valid choices are: \`raw\`,\`decoded\`,\`id\`,\`filepath\` (Defaults to: 'raw').
	:---separately: call command once for each message.
	:---background: disable stdin and ignore stdout.



editnew
_______

edit message in as new




toggleheaders
_____________

display all headers

optional arguments
	:---all: affect all messages.



print
_____

print message(s)

optional arguments
	:---all: print all messages.
	:---raw: pass raw mail string.
	:---separately: call print command once for each message.



remove
______

remove message(s) from the index

optional arguments
	:---all: remove whole thread.



togglesource
____________

display message source

optional arguments
	:---all: affect all messages.



retag
_____

set message(s) tags.

argument
	comma separated list of tags

optional arguments
	:---all: tag all messages in thread.



fold
____

fold message(s)

optional arguments
	:---all: fold all messages.



tag
___

add tags to message(s)

argument
	comma separated list of tags

optional arguments
	:---all: tag all messages in thread.



untag
_____

remove tags from message(s)

argument
	comma separated list of tags

optional arguments
	:---all: tag all messages in thread.



unfold
______

unfold message(s)

optional arguments
	:---all: unfold all messages.



forward
_______

forward message

optional arguments
	:---attach: attach original mail.



reply
_____

reply to message

optional arguments
	:---all: reply to all.



save
____

save attachment(s)

argument
	path to save to

optional arguments
	:---all: save all attachments.



toggletags
__________

flip presence of tags on message(s)

argument
	comma separated list of tags

optional arguments
	:---all: tag all messages in thread.



select
______

select focussed element. The fired action depends on the focus:
        - if message summary, this toggles visibility of the message,
        - if attachment line, this opens the attachment



global-mode
-----------

bclose
______

close current buffer




bprevious
_________

focus previous buffer




search
______

open a new search buffer

argument
	search string

optional arguments
	:---sort: sort order. Valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.



compose
_______

compose a new email

optional arguments
	:---sender: sender.
	:---template: path to a template message file.
	:---subject: subject line.
	:---to: recipients.
	:---cc: copy to.
	:---bcc: blind copy to.
	:---attach: attach files.



prompt
______

prompts for commandline and interprets it upon select

argument
	initial content




help
____


    display help for a command. Use 'bindings' to
    display all keybings interpreted in current mode.'
    

argument
	command or 'bindings'




move
____

move focus

argument
	direction




shellescape
___________

run external command

argument
	command line to execute

optional arguments
	:---spawn: run in terminal window.
	:---thread: run in separate thread.
	:---refocus: refocus current buffer                      after command has finished.



refresh
_______

refresh the current buffer




cancel
______

send cancel event




pyshell
_______

open an interactive python shell for introspection




exit
____

shut down cleanly




flush
_____

flush write operations or retry until committed




bufferlist
__________

open a list of active buffers




bnext
_____

focus next buffer




select
______

send select event




taglist
_______

opens taglist buffer



envelope-mode
-------------

set
___

set header value

positional arguments
	:0: header to refine
	:1: value


optional arguments
	:---append: keep previous values.



toggleheaders
_____________

toggle display of all headers




edit
____

edit mail




send
____

send mail




attach
______

attach files to the mail

argument
	file(s) to attach (accepts wildcads)




refine
______

prompt to change the value of a header

argument
	header to refine




save
____

save draft




unset
_____

remove header field

argument
	header to refine



bufferlist-mode
---------------

close
_____

close focussed buffer




select
______

focus selected buffer



taglist-mode
------------

select
______

search for messages with selected tag



