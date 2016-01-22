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

"""Import/reimport a contest (depending whether it exists already in the DB).

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import logging
import os
import sys

from cmscontrib.israel.Constants import CONTESTS_DIR
from cms.db import SessionGen
from cms.db.util import get_contest_list, ask_for_contest


logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Prepare a contest from its module on disk.")

    parser.add_argument("-a", "--ask", action="store_true",
                        help="ask which contest to reimport into.")
    parser.add_argument("-f", "--force", action="store_true",
                        help="delete when reimporting.")
    parser.add_argument("contest_name", action="store",
                        help="name of contest in contests directory.")

    args = parser.parse_args()

    contest_dir = os.path.join(CONTESTS_DIR, args.contest_name)

    if not os.path.isdir(contest_dir):
        logger.critical("Contest directory not found: %s" % contest_dir)
        sys.exit(1)

    with SessionGen() as session:

        reimporting = False
        multiple_occs = False

        for contest in get_contest_list(session):
            if contest.name == args.contest_name:
                if reimporting:
                    multiple_occs = True
                    break
                contest_id = contest.id
                reimporting = True

    if multiple_occs:
        logger.warning("Multiple occurrences, manual choice needed.")
        args.ask = True

    if reimporting:
        if args.ask:
            contest_id = ask_for_contest()
        else:
            logger.info("Contests exists, id %s. Reimporting." % contest_id)
        os.system("cmsReimporter -c %s %s %s" %
                  (contest_id, contest_dir, ("-f" if args.force else "")))

    else:
        os.system("cmsImporter %s" % contest_dir)


if __name__ == "__main__":
    main()
