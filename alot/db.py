from notmuch import Database
import logging


class DBManager():
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
