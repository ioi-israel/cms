#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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

"""Constants related to Israel loader.

"""

from os import path

SYNC_DIR = path.expanduser("~/Dropbox")
SYNC_DIR_IOI = path.join(SYNC_DIR, "ioi")
SYNC_DIR_CMS = path.join(SYNC_DIR_IOI, "cms")

USERS_DIR = path.join(SYNC_DIR_CMS, "users")
USERNAME_SEP = "."
USER_HIDDEN_PREFIX = "bl0ck"

CONTESTS_DIR = path.join(SYNC_DIR_CMS, "contests")
TASKS_DIR = path.join(SYNC_DIR_CMS, "tasks")
IMPORT_TIME_FILE_PREFIX = ".import_time_"
PREPARE_TIME_FILE = ".prepare_time"
MODULE_FILE = "module.py"

TIME_FORMAT = "%Y-%m-%d-%H:%M:%S"
COMMENT_PREFIX = "#"
