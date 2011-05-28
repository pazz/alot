editor_cmd = "/usr/bin/vim -f -c 'set filetype=mail' %s"
pager_cmd = "/usr/bin/view -f -c 'set filetype=mail' %s"
terminal_cmd = 'urxvt -T notmuch -e %s'
spawn_editor = True
spawn_pager = True

palette = [
    ('header', 'white', 'dark blue', 'bold', '', ''),
    ('footer', 'white', 'dark blue', 'bold', '', ''),
    ('prompt', 'light gray', 'black', '', '', ''),
    ('threadline', 'light gray', '', '', '', ''),
    ('threadline_focus', 'white', 'dark gray', '', '', ''),

    ('threadline_date', 'light gray', '', '', '', ''),
    ('threadline_mailcount', 'light gray', '', '', '', ''),
    ('threadline_tags', 'yellow', '', '', '', ''),
    ('threadline_authors', 'dark green', '', '', '', ''),
    ('threadline_subject', 'light gray', '', '', '', ''),
    ('threadline_date_linefocus', 'light gray', 'dark gray', '', '', ''),
    ('threadline_mailcount_linefocus', 'light gray', 'dark gray', '', '', ''),
    ('threadline_tags_linefocus', 'yellow,bold', 'dark gray', '', '', ''),
    ('threadline_authors_linefocus', 'dark green', 'dark gray', '', '', ''),
    ('threadline_subject_linefocus', 'light gray', 'dark gray', '', '', ''),

    ('messagesummary_even', 'white', 'light blue', '', '', ''),
    ('messagesummary_odd', 'white', 'dark blue', '', '', ''),
    ('messagesummary_focus', 'white', 'black', '', '', ''),
    ('message_header', 'white', 'dark gray', '', '', ''),
    ('message_body', 'light gray', 'black', '', '', ''),

    ('bufferlist_results_even', 'light gray', 'black', '', '', ''),
    ('bufferlist_results_odd', 'light gray', 'black', '', '', ''),
    ('bufferlist_focus', 'white', 'dark gray', '', '#ffa', ''),

    ('taglist_tag', 'light gray', 'black', '', '', ''),
    ('taglist_focus', 'white', 'dark gray', '', '', ''),
]
displayed_headers = [
    'From',
    'To',
    'Cc',
    'Bcc',
    'Subject',
]

authors_maxlength = 30


hooks = {
        'pre-shutdown': lambda ui: ui.logger.info('goodbye!'),
        }
