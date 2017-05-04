#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2015-2016 Nir Lavee <nir692007@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""IsraelLoader derived from Loader base class.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import logging
import sys

from imp import load_source
from time import mktime
from datetime import datetime

from cmscommon.datetime import make_datetime
from cmscontrib.BaseLoader import Loader
from cmscontrib.israel.Constants import MODULE_FILE, USERS_DIR, USERNAME_SEP,\
    USER_HIDDEN_PREFIX, TASKS_DIR, IMPORT_TIME_FILE_PREFIX, TIME_FORMAT,\
    COMMENT_PREFIX, CONTESTS_DIR

from cms import LANGUAGES, DEFAULT_LANGUAGES

from cmscontrib.israel.PrepareTask import PrepareTask
from cmscontrib import touch
from cms.db import Contest, User, Task, Statement, Attachment, \
    SubmissionFormatElement, Dataset, Manager, Testcase

logger = logging.getLogger(__name__)


class IsraelLoader(Loader):
    """Israel Loader.

    Each loader must extend this class and support the following
    access pattern:

      * The class method detect() can be called at any time.

      * Once a loader is instatiated, get_contest() can be called on
        it, only once.

      * After get_contest() has been called, at the caller's will,
        get_task() and get_user() can be called, in any order and for
        how many times the caller want. The resource intensive
        operations that are not needed for get_contest() are better
        left in get_task() or get_user(), so that no time is wasted if
        the caller isn't interested in users or tasks.

    """

    # Short name of this loader, meant to be a unique identifier.
    short_name = "israel_loader"

    # Description of this loader, meant to be human readable.
    description = "Israel python-based format"

    def __init__(self, path, file_cacher):
        """Initialize the Loader.

        path (str): the filesystem location given by the user.
        file_cacher (FileCacher): the file cacher to use to store
                                  files (i.e. statements, managers,
                                  testcases, etc.).

        """
        super(IsraelLoader, self).__init__(path, file_cacher)

    @classmethod
    def detect(cls, path):
        """Detect whether this loader is able to interpret a path.

        If the loader chooses to not support autodetection, just
        always return False.

        path (string): the path to scan.

        return (bool): True if the loader is able to interpret the
                       given path.

        """

        return bool(IsraelLoader.detect_full_path(path))

    @classmethod
    def detect_full_path(cls, path):
        """Given a path, return the absolute path to the contest module.

        If <workdir>/<path>/module.py exists, we choose it.
        Otherwise, try contests dir instead of workdir.
        If nothing works, return None.

        """

        module_relative = os.path.join(path, MODULE_FILE)
        module_abs = os.path.abspath(module_relative)
        if os.path.isfile(module_abs):
            return module_abs

        module_abs = os.path.join(CONTESTS_DIR, path, MODULE_FILE)
        if os.path.isfile(module_abs):
            return module_abs

        path_last_dir = os.path.split(path)[-1]
        module_abs = os.path.join(CONTESTS_DIR, path_last_dir, MODULE_FILE)
        if os.path.isfile(module_abs):
            return module_abs

        return None

    def get_contest(self):
        """Produce a Contest object.

        Do what is needed (i.e. search directories and explore files
        in the location given to the constructor) to produce a Contest
        object. Also get a minimal amount of information on tasks and
        users, at least enough to produce the list of all task names
        and the list of all usernames.

        return (tuple): the Contest object and the two lists described
                        above.

        """

        self.module_path = IsraelLoader.detect_full_path(self.path)

        if not self.module_path:
            logger.critical("Cannot find module: %s" % self.path)
            sys.exit(1)

        logger.info("Initializing loader for contest path %s." %
                    self.module_path)

        self.module = load_source(self.module_path, self.module_path)

        args = {}

        # Extract short name: the parent directory of the module.
        self.contest_dir = os.path.dirname(self.module_path)
        contest_name = os.path.split(self.contest_dir)[-1]

        self.check_accidental_import()

        logger.info("Loading parameters for contest %s." % contest_name)

        # Contest names.
        args["name"] = contest_name
        args["description"] = self.module.get_long_name()

        # Contest languages.
        args["languages"] = self.module.get_languages()

        # Contest times.
        args["start"] = make_datetime(mktime(datetime.strptime(
            self.module.get_begin_time(), TIME_FORMAT).timetuple()))

        args["stop"] = make_datetime(mktime(datetime.strptime(
            self.module.get_end_time(), TIME_FORMAT).timetuple()))

        # Languages
        try:
            self.languages = self.module.get_languages()
            logger.info("Contest languages set: %s" % self.languages)
        except:
            self.languages = DEFAULT_LANGUAGES
            logger.warning("Contest languages are default: %s" %
                           self.languages)

        args["languages"] = self.languages

        # Store users, both for this function and for future calls to get_user.
        users_file_path = os.path.join(USERS_DIR,
                                       self.module.get_users_file())

        with open(users_file_path) as f:
            users_text = f.read()

        self.users = {}
        self.hidden_users = set()

        for line in users_text.splitlines():
            line = line.strip()
            if not line or line.startswith(COMMENT_PREFIX):
                continue
            parts = line.split()
            hidden = False
            if USER_HIDDEN_PREFIX in parts:
                parts.remove(USER_HIDDEN_PREFIX)
                hidden = True
            user, password = parts
            self.users[user] = password
            if hidden:
                self.hidden_users.add(user)

        # Get task names.
        task_names = self.module.get_task_names()
        self.task_order = dict((name, i) for i, name in enumerate(task_names))

        logger.info("Contest parameters loaded.")

        # Return Contest, task list and user list.
        return Contest(**args), task_names, sorted(self.users.keys())

    def check_accidental_import(self):
        """
        Check whether the admin accidentally called import instead of reimport.
        If any .import_time files exist, ask for confirmation.
        """

        # Dirty hack to find whether we are importing or reimporting.
        # TODO improve.
        from inspect import stack
        caller_name = stack()[2][3]
        if caller_name != "do_import":
            return

        for name in os.listdir(self.contest_dir):
            if name.startswith(IMPORT_TIME_FILE_PREFIX):
                logger.warning("%s exists." % name)

                answer = raw_input(
                    "There is an .import_time file in the contest directory. "
                    "Did you mean to use reimport? Type 'force' to continue> ")

                if answer == 'force':
                    return
                else:
                    logger.critical("Aborting: suspected accidental import.")
                    sys.exit(1)

    def get_user(self, username):
        """Produce a User object.

        username (string): the username.

        return (User): the User object.

        """

        logger.info("Loading parameters for user %s." % username)

        args = {}
        args["username"] = username
        args["password"] = self.users[username]

        # Username is "first.last", title() corrects the case to First Last.
        name_parts = username.title().split(USERNAME_SEP)
        args["first_name"] = name_parts[0]
        args["last_name"] = " ".join(name_parts[1:])

        # Hidden users.
        args["hidden"] = username in self.hidden_users

        return User(**args)

    def get_task(self, name):
        """Produce a Task object.

        name (string): the task name.

        return (Task): the Task object.

        """

        prepare_task = PrepareTask(name)
        prepare_task.write_files()

        touch(self.get_import_time_path(name))

        return prepare_task.get_db_object(self.file_cacher,
                                          self.task_order[name])

    def has_changed(self, name):
        """Detect if a Task has been changed since its last import.

        This is expected to happen by saving, at every import, some
        piece of data about the last importation time. Then, when
        has_changed() is called, such time is compared with the last
        modification time of the files describing the task. Anyway,
        the Loader may choose the heuristic better suited for its
        case.

        If this task is being imported for the first time or if the
        Loader decides not to support changes detection, just return
        True.

        name (string): the task name.

        return (bool): True if the task was changed, False otherwise.

        """

        import_time_path = self.get_import_time_path(name)

        if not os.path.isfile(import_time_path):
            return True

        import_time = os.stat(import_time_path).st_mtime

        task_dir = os.path.join(TASKS_DIR, name)

        for dir_name, dirs, file_names in os.walk(task_dir):
            for file_name in file_names:
                file_path = os.path.join(dir_name, file_name)
                file_time = os.stat(file_path).st_mtime

                if file_time > import_time:
                    return True

        return False

    def get_import_time_path(self, task_name):
        return os.path.join(self.contest_dir,
                            IMPORT_TIME_FILE_PREFIX + task_name)
