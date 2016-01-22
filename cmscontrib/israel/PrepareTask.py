#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Nir Lavee <nir692007@gmail.com>
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

"""This script prepares a task in the Israeli format.

The task module's get_subtasks() method is called. Input and output
files are created accordingly, and written to the task's directory.

The script is used in two places:

    * By the IsraelLoader script, when a contest is loaded.

    * From the command line on the server, when one only wants to prepare
      a task without loading it into the database.

"""

import argparse
import logging
import os
import subprocess
import sys

from imp import load_source

from cms import LANGUAGES, SOURCE_EXT_TO_LANGUAGE_MAP, utf8_decoder, \
    SCORE_MODE_MAX
from cms.db import Contest, User, Task, Statement, Attachment, \
    SubmissionFormatElement, Dataset, Manager, Testcase
from cmscontrib import touch

from cmscontrib.israel.Constants import TASKS_DIR, MODULE_FILE, \
    PREPARE_TIME_FILE


logger = logging.getLogger(__name__)


class PrepareTask(object):

    def __init__(self, task_name):
        """Construct a PrepareTask object.
        """
        # Read the task's module.
        self.task_name = task_name
        self.task_dir = os.path.join(TASKS_DIR, task_name)
        self.module_path = os.path.join(self.task_dir, MODULE_FILE)

        if not os.path.isfile(self.module_path):
            logger.critical("Module not found: %s" % self.module_path)
            sys.exit(1)

        self.module = load_source(self.module_path, self.module_path)
        self.read_meta()

    def is_prepared(self):
        self.prepare_time_path = os.path.join(self.task_dir, PREPARE_TIME_FILE)

        if not os.path.isfile(self.prepare_time_path):
            return False

        prepare_time = os.stat(self.prepare_time_path).st_mtime

        for dir_name, dirs, file_names in os.walk(self.task_dir):
            for file_name in file_names:
                file_path = os.path.join(dir_name, file_name)
                file_time = os.stat(file_path).st_mtime

                if file_time > prepare_time:
                    return False

        return True

    def read_meta(self):
        logger.info("Loading parameters for task %s." % self.task_name)

        # Required properties.
        self.long_name = self.module.get_long_name()
        self.timeout = self.module.get_timeout()
        self.memory = self.module.get_memory()
        self.task_type = self.module.get_task_type()
        self.subtask_structure = self.module.get_subtask_structure()

        # Optional properties.
        self.manager = None
        self.scorer = None
        self.statement = None
        self.stubs = None
        self.attachments = None
        self.headers = None

        try:
            self.manager = self.module.get_manager()
        except Exception:
            logger.warning("Task does not specify a manager.")

        try:
            self.scorer = self.module.get_scorer()
        except Exception:
            logger.warning("Task does not specify a scorer.")

        try:
            self.statement = self.module.get_statement()
        except Exception:
            logger.warning("Task does not specify a statement.")

        try:
            self.stubs = self.module.get_stubs()
        except Exception:
            logger.warning("Task does not specify stubs.")

        try:
            self.attachments = self.module.get_attachments()
        except Exception:
            logger.warning("Task does not specify attachments.")

        try:
            self.headers = self.module.get_headers()
        except Exception:
            logger.warning("Task does not specify headers.")

        logger.info("Finished reading meta data from module.")

    def write_files(self):
        """Generate and write the input/output files of the task to disk.
        """

        # Check if writing is necessary.
        if self.is_prepared():
            logger.info("Task %s already prepared. Not writing files." %
                        self.task_name)
            return

        # Create directories if needed.
        for dir_name in ("input", "output"):
            full_dir = os.path.join(self.task_dir, dir_name)
            if not os.path.isdir(full_dir):
                os.mkdir(full_dir)

        logger.info("Getting the subtasks. This may take a while.")

        # Generate subtasks in the task's directory.
        old_cwd = os.getcwd()
        os.chdir(self.task_dir)

        count = 0
        actual_structure = []
        for subtask in self.module.get_subtasks():
            actual_structure.append([subtask.get("score"),
                                     len(subtask["testcases"])])
            for testcase in subtask["testcases"]:
                self.write_io_file(testcase, count)
                count += 1

        os.chdir(old_cwd)

        self.verify_structure(actual_structure)

        touch(os.path.join(self.task_dir, PREPARE_TIME_FILE))

    def verify_structure(self, actual_structure):
        if len(actual_structure) != len(self.subtask_structure):
            logger.critical("Number of subtasks does not match structure.")
            sys.exit(1)
        for i in xrange(len(actual_structure)):
            actual_pair = actual_structure[i]
            meta_pair = self.subtask_structure[i]
            if actual_pair[0] is not None and actual_pair[0] != meta_pair[0]:
                logger.critical("Score doesn't match in subtask %s" % i)
                sys.exit(1)
            if actual_pair[1] != meta_pair[1]:
                logger.critical("Testcase count doesn't match in subtask %s" %
                                i)
                sys.exit(1)

    def write_io_file(self, testcase, count):
        logger.info("Task %s: testcase %s." % (self.task_name, count))

        input_path = os.path.join(self.task_dir, "input/input%s.txt" % count)
        hints_path = os.path.join(self.task_dir, "output/output%s.txt" % count)

        if "data" in testcase:
            chunks = testcase["data"]
            if type(chunks) != dict:
                logger.critical("Expected data to be dictionary, it is %s" %
                                type(chunks))
                sys.exit(1)
            elif "submission_input" not in chunks:
                logger.critical("Expected 'submission_input' key in data.")
                sys.exit(1)
        else:
            if not os.path.isfile(input_path):
                logger.critical("Expected to exist: %s" % input_path)
                sys.exit(1)
            if not os.path.isfile(hints_path):
                logger.critical("Expected to exist: %s" % hints_path)
                sys.exit(1)
            return

        with open(input_path, 'w') as f:
            f.write(chunks["submission_input"])

        if "scorer_hints" in chunks:
            hints_string = chunks["scorer_hints"]
        else:
            hints_string = ""
        with open(hints_path, 'w') as f:
            f.write(hints_string)

    def get_db_object(self, file_cacher, task_num):
        self.file_cacher = file_cacher

        args = {}

        # Name.
        args["name"] = self.task_name
        args["title"] = self.long_name
        args["num"] = task_num

        # Score mode.
        args["score_mode"] = SCORE_MODE_MAX

        # Statement.
        if self.statement:
            args["statements"] = self.get_db_statement()
            args["primary_statements"] = '["he"]'

        # Submission.
        args["submission_format"] = [
            SubmissionFormatElement("Task.%l")]

        # Attachments.
        if self.attachments:
            args["attachments"] = self.get_db_attachments()

        task = Task(**args)
        task.active_dataset = self.get_db_dataset(task)

        logger.info("Task parameters loaded.")

        return task

    def get_db_statement(self):
        statement_path = os.path.join(self.task_dir, self.statement)

        if not os.path.isfile(statement_path):
            logger.critical("Statement doesn't exist: %s." %
                            statement_path)
            exit(1)

        digest = self.file_cacher.put_file_from_path(
            statement_path, "Statement for task %s (lang: he)" %
            self.task_name)

        return [Statement("he", digest)]

    def get_db_attachments(self):
        res = []

        for attachment in self.attachments:
            attachment_path = os.path.join(self.task_dir, attachment)

            if not os.path.isfile(attachment_path):
                logger.critical("Attachment missing: %s" %
                                attachment_path)
                sys.exit(1)

            digest = self.file_cacher.put_file_from_path(
                attachment_path,
                "Attachment %s for task %s" % (attachment,
                                               self.task_name))

            res += [Attachment(attachment, digest)]

        return res

    def get_db_dataset(self, task_object):
        args = {}
        args["task"] = task_object
        args["description"] = "Default"
        args["autojudge"] = False
        args["time_limit"] = float(self.timeout)
        args["memory_limit"] = self.memory
        args["managers"] = []
        args["score_type"] = "GroupMin"
        args["score_type_parameters"] = "%s" % self.subtask_structure

        score_sum = sum(st[0] for st in self.subtask_structure)
        testcase_count = sum(st[1] for st in self.subtask_structure)

        if score_sum != 100:
            logger.warning("Score sums to %s and not 100 in %s." %
                           (score_sum, self.task_name))

        if self.task_type == "output":
            args["task_type"] = "OutputOnly"
            args["time_limit"] = None
            args["memory_limit"] = None

            if self.scorer:
                args["task_type_parameters"] = '["%s"]' % "comparator"
            else:
                args["task_type_parameters"] = '["%s"]' % "diff"

            task_object.submission_format = [
                SubmissionFormatElement("output_%03d.txt" % i)
                for i in xrange(testcase_count)]

        elif self.task_type == "communication":
            args["task_type"] = "Communication"
            args["task_type_parameters"] = "[]"

            manager_path = os.path.join(self.task_dir, self.manager)

            if not os.path.isfile(manager_path):
                logger.critical("Missing manager: %s" % manager_path)
                sys.exit(1)

            digest = self.file_cacher.put_file_from_path(
                manager_path, "Manager for task %s" % self.task_name)

            args["managers"] += [Manager("manager", digest)]

        elif self.task_type == "batch":
            args["task_type"] = "Batch"
            args["task_type_parameters"] = '["%s", ["%s", "%s"], "%s"]' %\
                (("grader" if self.stubs else "alone"),
                 (""),
                 (""),
                 ("comparator" if self.scorer else "diff"))

        elif self.task_type == "twosteps":
            args["task_type"] = "TwoSteps"
            args["task_type_parameters"] = "[]"

            manager_path = os.path.join(self.task_dir, self.manager)

            if not os.path.isfile(manager_path):
                logger.critical("Missing manager: %s" % manager_path)
                sys.exit(1)

            digest = self.file_cacher.put_file_from_path(
                manager_path, "Manager for task %s" % self.task_name)

            args["managers"] += [Manager("manager.cpp", digest)]

        else:
            logger.critical("Unknown task type %s" % self.task_type)
            sys.exit(1)

        if self.stubs:
            for stub in self.stubs:
                stub_path = os.path.join(self.task_dir, stub)

                if not os.path.isfile(stub_path):
                    logger.critical("Missing stub: %s" % stub_path)
                    sys.exit(1)

                ext = os.path.splitext(stub)[1]
                lang = SOURCE_EXT_TO_LANGUAGE_MAP[ext]

                digest = self.file_cacher.put_file_from_path(
                    stub_path, "Stub for task %s and language %s" %
                    (self.task_name, lang))

                args["managers"] += [Manager("stub%s" % ext, digest)]

        if self.headers:
            for header in self.headers:
                header_path = os.path.join(self.task_dir, header)

                if not os.path.isfile(header_path):
                    logger.critical("Missing header: %s" % header_path)
                    sys.exit(1)

                ext = os.path.splitext(header)[1]

                # TODO this only supports C++.
                if ext != ".h":
                    logger.critical("Header must be .h file.")
                    sys.exit(1)

                digest = self.file_cacher.put_file_from_path(
                    header_path, "Header for task %s and language %s" %
                    (self.task_name, "cpp"))

                header_name = os.path.split(header_path)[-1]
                args["managers"] += [Manager(header_name, digest)]

        if self.scorer:
            scorer_path = os.path.join(self.task_dir, self.scorer)

            digest = self.file_cacher.put_file_from_path(
                scorer_path, "Manager for task %s" % self.task_name)

            args["managers"] += [Manager("checker", digest)]

        args["testcases"] = []

        i = 0

        for subtask in self.subtask_structure:
            for testcase in xrange(subtask[1]):
                input_path = os.path.join(self.task_dir, "input",
                                          "input%d.txt" % i)
                output_path = os.path.join(self.task_dir, "output",
                                           "output%d.txt" % i)

                input_digest = self.file_cacher.put_file_from_path(
                    input_path, "Input %d for task %s" % (i, self.task_name))
                output_digest = self.file_cacher.put_file_from_path(
                    output_path, "Output %d for task %s" % (i, self.task_name))

                args["testcases"] += [
                    Testcase("%03d" % i, False, input_digest, output_digest)]

                args["testcases"][i].public = True

                if self.task_type == "output":
                    task_object.attachments += [
                        Attachment("input_%03d.txt" % i, input_digest)]

                i += 1

        return Dataset(**args)


def main():
    """Parse arguments and start the script."""

    parser = argparse.ArgumentParser(
        description="Prepare a task from its module on disk.")

    parser.add_argument("-s", "--simulate", action="store_true",
                        help="dry run. Call the task module methods "
                        "but don't write any files.")
    parser.add_argument("task_name", action="store", type=utf8_decoder,
                        help="name of task to prepare")

    args = parser.parse_args()

    # If no task is given, try to infer it from directory.
    if args.task_name is None:
        dir_parts = os.path.split(os.getcwd())
        if dir_parts[0] == TASKS_DIR:
            args.task_name = dir_parts[1]
        else:
            logger.critical("Task name not given, and this is not a valid "
                            "task directory. Exiting.")
            return

    prepare_task = PrepareTask(args.task_name)

    if not args.simulate:
        prepare_task.write_files()

if __name__ == "__main__":
    main()
