from notmuch import Database


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

    def query(self, querystring):
        mode = Database.MODE.READ_ONLY
        db = Database(path=self.path, mode=mode)
        return db.create_query(querystring)

    def update(self, updatestring):
        if self.ro:
            self.logger.error('I\'m in RO mode')
        else:
            self.logger.error('DB updates not implemented yet')
            mode = Database.MODE.READ_WRITE
            db = Database(path=self.path, mode=mode)
            return None  # do stuff
