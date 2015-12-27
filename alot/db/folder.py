# -*- coding: utf-8 -*-


class Folder(object):
    """ wrappar on top of notmuch query for a folder """

    def __init__(self, dbman, folder_name, rel_path):
        self.dbman = dbman
        self.folder_name = folder_name
        self.query_folder_name = rel_path if not rel_path.startswith('/') else rel_path[1:]
        if rel_path:  # root folder has no relative path
            self.query = 'folder:"%s"' % self.query_folder_name
            self.unread_query = 'folder:"%s" tag:unread' % self.query_folder_name
        else:
            self.query = ''
            self.unread_query = 'tag:unread'
        self.count = 0
        self.refresh()

    def __str__(self):
        return "[%d] %s" % (self.count, self.folder_name)

    def __unicode__(self):
        return unicode(self.__str__())

    def __repr__(self):
        return "Folder([%d] %s (%s))" % (self.count, self.folder_name, self.query)

    def get_id(self):
        return self.query_folder_name

    def get_query_string(self):
        return self.query

    def remove_unread_tags(self):
        self.dbman.untag(self.unread_query, ['unread'])
        self.dbman.flush()

    def refresh(self):
        self.count = self.dbman.count_messages(self.unread_query)
        return self.count
