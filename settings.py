editor_cmd = "/usr/bin/vim -f -c 'set filetype=mail' %s"
pager_cmd = "/usr/bin/view -f -c 'set filetype=mail' %s"
palette = [
    ('header', 'white', 'dark blue', 'bold', '#ffa', ''),
    ('footer', 'white', 'dark blue', 'bold', '', ''),
    ('prompt', 'light gray', 'black', '', 'g50', '#60a'),
    ('threadline', 'light gray', 'black', '', 'g50', '#60a'),
    ('threadline_focus', 'white', 'dark gray', '', '#ffa', '#60d'),
    ('messageline_even', 'white', 'light blue', '', '#ffa', '#60d'),
    ('messageline_odd', 'white', 'dark blue', '', '#ffa', '#60d'),
    ('message_header', 'white', 'dark gray', '', '#ffa', '#60d'),
    ('message_body', 'light gray', 'black', '', '#ffa', '#60d'),
    ('bufferlist_results_even', 'light gray', 'black', '', 'g50', '#60a'),
    ('bufferlist_results_odd', 'light gray', 'black', '', 'g38', '#808'),
    ('bufferlist_focus', 'white', 'dark gray', '', '#ffa', '#60d'),
    ('background', '', 'black', '', 'g7', '#d06'),
]
displayed_headers=[
        'From',
        'To',
        'Cc',
        'Bcc',
        'Subject'
        ]

hooks = {
        'pre-shutdown': lambda ui: ui.logger.info('goodbye!'),
        }
