from notmuch import Database
from datetime import datetime
import logging
import email


class DBManager:
    def __init__(self, path=None, ro=False):
        self.ro = ro
        self.path = path

    def count_messages(self, querystring):
        q = self.query(querystring)
        return q.count_messages()

    def search_threads(self, querystring):
        q = self.query(querystring)
        return q.search_threads()

    def get_all_tags(self):
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        tags = list()
        for t in db.get_all_tags():
            tags.append(t)
        return tags

    def tag_message(self, msg, tags, untag=False):
        logging.debug('tag msg %s %s %s'%(tags,untag,msg))
        msg.freeze()
        if untag:
            for tag in tags:
                msg.remove_tag(tag)
                logging.debug('untag %s'%tags)
        else:
            for tag in tags:
                msg.add_tag(tag)
                logging.debug('tag %s'%tags)
        msg.thaw()

    def tag_thread(self, thread, tags, untag=False):
        tid = thread.get_thread_id()
        q = self.query('thread:'+tid, writeable=True)
        for msg in q.search_messages():
            msg.freeze()
            self.tag_message(msg, tags, untag=untag)
            msg.thaw()

    def untag_thread(self, thread, *tags):
        return self.tag_thread(thread, *tags, untag=True)

    def query(self, querystring, writeable=False):
        if writeable:
            mode = Database.MODE.READ_WRITE
        else:
            mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return db.create_query(querystring)

    def get_message(self,mid, writeable=False):
        q = self.query('id:'+mid, writeable=writeable)
        #TODO raise exceptions here in 0<case msgcount>1
        return q.search_messages().next()

    def get_thread(self,tid, writeable=False):
        q = self.query('thread:'+tid, writeable=writeable)
        #TODO raise exceptions here in 0<case msgcount>1
        return q.search_threads().next()

class Thread:
    def __init__(self, dbman, thread, precache=False):
        self.dbman = dbman
        self.tid = thread.get_thread_id()
        if precache:
            self.read_thread()

    def read_thread(self):
        thread = dbman.get_thread(self.tid)
        self.strrep = thread.__str__()
        self.total_messages = thread.get_total_messages()
        self.toplevel_messages = []
        for m in thread.get_toplevel_messages():
            self.toplevel_messages.append(Message(dbman,m))
        self.authors = thread.get_authors()
        self.subject = thread.get_subject()
        self.oldest = datetime.fromtimestamp(self.thread.get_oldest_date())
        self.newest = datetime.fromtimestamp(self.thread.get_newest_date())
        self.tags = []
        for t in thread.get_tags():
            self.tags.append(t.__str__())

class Message:
    def __init__(self,dbman, msg, precache=False):
        self.dbman = dbman
        self.mid = msg.get_message_id()
        if precache:
            self.read_msg()

    def read_msg(self)
        msg = self.dbman.get_msg(self.mid)
        self.strrep = msg.__str__()
        self.replies = []
        for m in msg.get_replies():
            self.replies.append(Message(dbman,m))
        self.filename = msg.get_filename()
        self.email = self.read_mail(self.filename)
        self.tags = []
        for t in thread.get_tags():
            self.tags.append(t.__str__())

    def read_mail(self, message):
        try:
            f_mail = open(message.get_filename())
        except EnvironmentError:
            eml = email.message_from_string('Unable to open the file')
        else:
            eml = email.message_from_file(f_mail)
            f_mail.close()
        return eml


