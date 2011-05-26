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

    def search_thread_ids(self, querystring):
        q = self.query(querystring)
        tid_list = [t.get_thread_id() for t in q.search_threads()]
        return tid_list

    def get_message(self,mid, writeable=False):
        q = self.query('id:'+mid, writeable=writeable)
        #TODO raise exceptions here in 0<case msgcount>1
        return Message(self, q.search_messages().next())

    def get_thread(self,tid, writeable=False):
        q = self.query('thread:'+tid, writeable=writeable)
        #TODO raise exceptions here in 0<case msgcount>1
        return Thread(self, q.search_threads().next())
    def get_all_tags(self):
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        tags = list()
        for t in db.get_all_tags():
            tags.append(t)
        return tags

    def query(self, querystring, writeable=False):
        if writeable:
            mode = Database.MODE.READ_WRITE
        else:
            mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return db.create_query(querystring)


class Thread:
    def __init__(self, dbman, thread):
        self.dbman = dbman
        self.tid = thread.get_thread_id()
        self.strrep = "WRAPPER:"+thread.__str__()
        self.total_messages = thread.get_total_messages()
        self.topmessages = [m.get_message_id() for m in thread.get_toplevel_messages()]
        self.authors = thread.get_authors()
        self.subject = thread.get_subject()
        self.oldest = datetime.fromtimestamp(thread.get_oldest_date())
        self.newest = datetime.fromtimestamp(thread.get_newest_date())
        self.tags = [ t.__str__() for t in thread.get_tags()]

    def add_tags(self, tags):
        q = self.dbman.query('thread:'+self.tid, writeable=True)
        for msg in q.search_messages():
            msg.freeze()
            for t in tags:
                msg.add_tag(t)
            msg.thaw()
        self.tags += [t for t in tags if t not in self.tags]

    def remove_tags(self, tags):
        q = self.dbman.query('thread:'+self.tid, writeable=True)
        for msg in q.search_messages():
            msg.freeze()
            for t in tags:
                msg.remove_tag(t)
            msg.thaw()
        self.tags = [t for t in self.tags if t in tags]

    def get_tags(self):
        return self.tags

    def get_authors(self):
        return self.authors

    def get_subject(self):
        return self.subject

    def get_toplevel_messages(self):
        tl = []
        for mid in self.topmessages:
            msg = self.dbman.get_message(mid)
            tl.append(Message(self.dbman,msg))
        return tl

    def get_newest_date(self):
        return self.newest

    def get_oldest_date(self):
        return self.oldest

    def get_total_messages(self):
        return self.total_messages

class Message:
    def __init__(self,dbman, msg):
        self.dbman = dbman
        self.mid = msg.get_message_id()
        self.strrep = msg.__str__()
        self.replies = [m.get_message_id() for m in msg.get_replies()]
        self.filename = msg.get_filename()
        self.tags = [ t.__str__() for t in msg.get_tags()]

    def get_replies(self):
        r = []
        for mid in self.replies:
            msg = self.dbman.get_message(mid)
            r.append(Message(self.dbman,msg))
        return r

    def get_tags(self):
        return self.tags

    def get_email(self):
        if not self.email:
            self.email = self.read_mail(self.filename)
        return self.email

        self.email = self.read_mail(self.filename)
    def __str__(self):
        return self.strrep

    def read_mail(self, message):
        try:
            f_mail = open(message.get_filename())
        except EnvironmentError:
            eml = email.message_from_string('Unable to open the file')
        else:
            eml = email.message_from_file(f_mail)
            f_mail.close()
        return eml

    def add_tags(self, tags, untag=False):
        msg = self.dbman.get_message(self.mid)
        msg.freeze()
        for tag in tags:
            msg.add_tag(tag)
            logging.debug('tag %s'%tags)
        msg.thaw()
        self.tags += [t for t in tags if t not in self.tags]

    def remove_tags(self, tags):
        msg = self.dbman.get_message(self.mid)
        msg.freeze()
        for tag in tags:
            msg.remove_tag(tag)
            logging.debug('untag %s'%tags)
        msg.thaw()
        self.tags = [t for t in self.tags if t in tags]
