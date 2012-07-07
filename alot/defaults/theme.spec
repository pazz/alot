[global]
    # attributes used in all modi
    footer = attrtriple
    body = attrtriple
    notify_error = attrtriple
    notify_normal = attrtriple
    prompt = attrtriple
    tag = attrtriple
    tag_focus = attrtriple
[help]
    # formatting of the `help bindings` overlay
    text = attrtriple
    section = attrtriple
    title = attrtriple
# mode specific attributes
[bufferlist]
    focus = attrtriple
    results_even = attrtriple
    results_odd = attrtriple
[search]
    [[threadline]]
        normal = attrtriple
        focus = attrtriple
        # order subwidgets are displayed. subset of {date,mailcount,tags,authors,subject,count}
        # every element listed must have its own subsection below
        parts = string_list(default=None)
        [[[__many__]]]
            normal = attrtriple
            focus = attrtriple
            width = widthtuple(default=None)
            alignment = align(default='right')
    [[__many__]]
        normal = attrtriple
        focus = attrtriple
        parts = string_list(default=None)
        [[[__many__]]]
            normal = attrtriple
            focus = attrtriple
            width = widthtuple(default=None)
            alignment = align(default='right')
[thread]
    attachment = attrtriple
    attachment_focus = attrtriple
    body = attrtriple
    header = attrtriple
    header_key = attrtriple
    header_value = attrtriple
    summary_even = attrtriple
    summary_focus = attrtriple
    summary_odd = attrtriple
[envelope]
    body = attrtriple
    header = attrtriple
    header_key = attrtriple
    header_value = attrtriple
