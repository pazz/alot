import tempfile
import shutil
from os import path
from subprocess import call
import atexit
import notmuch


class Corpus:
    def __init__(self):
        self.TESTDIR = tempfile.mkdtemp()
        self.TESTCORPUS = path.join(self.TESTDIR, 'corpus')
        HERE = path.dirname(path.realpath(__file__))

        # copy over corpus
        shutil.copytree(path.join(HERE,'corpus'), self.TESTCORPUS)

        # create a temporary notmuch database
        # create notmuch config file
        notmuchconfig = path.join(self.TESTDIR, 'nmconfig')
        cfile = open(notmuchconfig, 'w')
        cfile.write("""
        [database]
        path=%s/
        [new]
        tags=new;
        """ % self.TESTCORPUS)
        cfile.close()

        # index corpus
        call(["notmuch", "--config=" + notmuchconfig, "new"])

        print "CREATED %s" % self.TESTDIR

    def __del__(self):
        shutil.rmtree(self.TESTDIR)

    def get_notmuch_msg_by_id(self, mid):
        """
        returns the `notmuch.Message` with given MessageID from the corpus
        """
        db = notmuch.Database(self.TESTCORPUS)
        msgs = notmuch.Query(db, 'id:%s' % mid).search_messages()
        msg = list(msgs)[0]
        return msg
