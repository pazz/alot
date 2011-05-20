editor_cmd = "/usr/bin/vim -f -c 'set filetype=mail' %s"
palette = [
    ('header', 'white', 'dark blue', 'bold', '#ffa', ''),
    ('footer', 'white', 'dark blue', 'bold', '', ''),
    ('prompt', 'light gray', 'black', '', 'g50', '#60a'),
    ('threadline', 'light gray', 'black', '', 'g50', '#60a'),
    ('threadline_focus', 'white', 'dark gray', '', '#ffa', '#60d'),
    ('message', 'white', 'dark gray', '', '#ffa', '#60d'),
    ('message_focus', 'white', 'dark gray', '', '#ffa', '#60d'),
    ('bufferlist_results_even', 'light gray', 'black', '', 'g50', '#60a'),
    ('bufferlist_results_odd', 'light gray', 'black', '', 'g38', '#808'),
    ('bufferlist_focus', 'white', 'dark gray', '', '#ffa', '#60d'),
    ('background', '', 'black', '', 'g7', '#d06'),
]


hooks = {
        'pre-shutdown': lambda ui: ui.logger.info('goodbye!'),
        }
