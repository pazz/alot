
palette = [
    ('header', 'white', 'dark blue', 'bold', '#ffa', ''),
    ('footer', 'white', 'dark blue', 'bold', '', ''),
    ('threadline', 'light gray', 'black', '', 'g50', '#60a'),
    ('threadline_focus', 'white', 'dark gray', '', '#ffa', '#60d'),
    ('bufferlist_results_even', 'light gray', 'black', '', 'g50', '#60a'),
    ('bufferlist_results_odd', 'light gray', 'black', '', 'g38', '#808'),
    ('bufferlist_focus', 'white', 'dark gray', '', '#ffa', '#60d'),
    ('background', '', 'black', '', 'g7', '#d06'),
]

bindings = {
        'i': 'open_inbox',
        'u': 'open_unread',
        'x': 'buffer_close',
        'tab': 'buffer_next',
        'shift tab': 'buffer_prev',
        #'\\': 'search',
        'q': 'shutdown',
        ';': 'buffer_list',
        's': 'shell',
        'v': 'editlog',
        }

hooks = {
        'pre-shutdown': lambda ui: ui.logger.info('goodbye!'),
        }
