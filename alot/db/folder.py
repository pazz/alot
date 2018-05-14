# -*- coding: utf-8 -*-

from alot.utils import imap_utf7


class Folder(object):
    """ wrapper on top of notmuch query for a folder """

    def __init__(self, dbman, folder_name, rel_path):
        self.dbman = dbman
        self.folder_name = folder_name
        self.query_folder_name = rel_path
        if rel_path.startswith('/'):
            self.query_folder_name = rel_path[1:]
        if rel_path:  # root folder has no relative path
            self.query = 'folder:"%s"' % self.query_folder_name
            self.unread_query = 'folder:"%s" tag:unread' % \
                                self.query_folder_name
        else:
            self.query = '*'
            self.unread_query = 'tag:unread'
        self.unread_count = 0
        self.all_count = 0
        self.refresh()

    def __str__(self):
        folder_name = imap_utf7.imapUTF7Decode(str(self.folder_name))
        return " %s [%d/%d]" % (folder_name, self.unread_count, self.all_count)

    def __unicode__(self):
        return unicode(self.__str__())

    def __repr__(self):
        return "Folder([%d/%d] %s (%s))" % (self.unread_count, self.all_count,
                                            self.folder_name, self.query)

    def get_id(self):
        return self.query_folder_name

    def get_query_string(self):
        return self.query

    def refresh(self):
        self.unread_count = self.dbman.count_messages(self.unread_query)
        self.all_count = self.dbman.count_messages(self.query)
