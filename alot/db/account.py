# -*- coding: utf-8 -*-

import logging
from collections import OrderedDict

from alot.db.folder import Folder
from alot.settings import settings


class Account(object):
    """
    Account represents a collection of folders defined in notmuch config at database -> path
    """

    def __init__(self, dbman):
        """
        :param dbman: db manager that is used for further lookups
        :type dbman: :class:`~alot.db.DBManager`
        """
        logging.debug("initializing Account")
        self._dbman = dbman
        self._init_vars()

        try:
            self.root_folder = Folder(self._dbman, settings.get_main_addresses()[0], '')
        except TypeError:
            self.root_folder = Folder(self._dbman, "root", '')

    def _init_vars(self):
        """ initiate variables """
        # list of paths
        self._folders_list = []
        # mapping between rel_path and class Folder
        self._folder_mapping = {}
        # class Folder -> children
        self._folders = OrderedDict()
        self._unread_folders = []

    def get_fs_folders(self):
        """
        find maildir folders on filesystem and create hierarchy out of it
        """
        all_dirs = self._dbman.get_all_folders()
        for d in all_dirs:
            try:
                basename = d.rsplit('/', 1)[1]
            except IndexError:
                basename = d
            self._folders_list.append((d, basename))
        # it could make sense to make this configurable
        self._folders_list = sorted(self._folders_list, key=lambda y: y[0].lower())

    def get_root(self):
        return self.root_folder

    def get_folder(self, rel_path):
        """ return folder specified via relative path """
        return self._folder_mapping[rel_path]

    def get_children(self, folder):
        try:
            return self._folders[folder]
        except KeyError:
            return []

    def get_folders_count(self):
        return len(self._folders)

    def get_next_unread(self, folder):
        try:
            index = self._unread_folders.index(folder)
        except ValueError:
            return self._unread_folders[0]
        try:
            return self._unread_folders[index + 1]
        except IndexError:
            return self._unread_folders[0]

    def get_previous_unread(self, folder):
        try:
            index = self._unread_folders.index(folder)
        except ValueError:
            return self._unread_folders[-1]
        try:
            return self._unread_folders[index - 1]
        except IndexError:
            return self._unread_folders[-1]

    def get_folders(self):
        """
        process folders by querying notmuch
        """
        if not self._folders:  # if not already cached
            self._folders[self.root_folder] = []
            # make inbox first
            inbox_list = [(index, item) for index, item in enumerate(self._folders_list)
                          if item[1].lower() == 'inbox']
            try:
                index, inbox = inbox_list[0]
            except IndexError:
                pass
            else:
                f = Folder(self._dbman, inbox[1], inbox[0])
                del self._folders_list[index]
                self._folders.setdefault(f, [])
                self._folder_mapping[inbox[0]] = f
                self._folders[self.root_folder].append(f)

            for rel_path, basename in self._folders_list:
                nice_name = basename[1:] if basename.startswith(".") else basename
                f = Folder(self._dbman, nice_name, rel_path)
                self._folders.setdefault(f, [])
                self._folder_mapping[rel_path] = f

                parent_path = rel_path.rsplit('/', 1)[0]
                if parent_path == rel_path:
                    self._folders[self.root_folder].append(f)
                else:
                    self._folders[self.get_folder(parent_path)].append(f)
                if f.count > 0:
                    self._unread_folders.append(f)
        return self._folders

    def refresh(self):
        """ refresh all folders """
        self._init_vars()
        self.get_fs_folders()
        return self.get_folders()

    def __str__(self):
        return "Account"
