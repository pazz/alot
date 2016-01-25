try:
    import vobject
except ImportError:
    raise ImportError("Failed to import vobject.  The vcard feature is only "
                      "available if you have the vobject module installed.")


import os
from . import AddressBook, AddressbookError


class VcardAddressbook(AddressBook):

    """:class:`AddressBook` that parses vcard files"""

    def __init__(self, path, **kwargs):
        """
        :param path: path to a vcard file or a directory with vcard files
        :type path: str
        """
        AddressBook.__init__(self, **kwargs)
        self._path = path

    def parse_files(self, path):
        """Read the vcard files from disk and parse them.  This can be used to
        update the loaded addresses after the files changed on disk.

        :param path: path to a vcard file or a directory with vcard files
        :type path: str
        """
        if os.path.isfile(path):
            paths = [path]
        elif os.path.isdir(path):
            paths = []
            for dirpath, dirnames, filenames in os.path.walk(path):
                for filename in filenames:
                    paths.append(os.path.join(dirpath, filename))
        else:
            raise AddressbookError("The path to the vcard addressbook must be "
                                   "a file or a directory")
        res = []
        for file in paths:
            with open(file) as vcard_file:
                for vcard in vobject.readComponents(vcard_file):
                    keys = vcard.sortChildKeys()
                    if "email" in keys:
                        email = vcard.getChildValue("email")
                        if "fn" in keys:
                            res.append((vcard.getChildValue("fn"), email))
                        elif "n" in keys:
                            name = vcard.getChildValue("n")
                            # TODO format name
                            res.append((name.given + " " + name.family, email))
                        else:
                            res.append(("", email))
                    else:
                        continue
        return res

    def get_contacts(self):
        # TODO Should the vcards be reparsed on every invocation?
        return self.parse_files(self._path)
