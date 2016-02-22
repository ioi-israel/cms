#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Nir Lavee <nir692007@gmail.com>
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
import random
import sys

from cmscontrib.israel.Constants import TASKS_DIR
from cms.db import SessionGen
from cms.db.util import get_contest_list, ask_for_contest


logger = logging.getLogger(__name__)


def non_existing_task(task_name):
    return not os.path.exists(os.path.join(TASKS_DIR, task_name))


def valid_type(task_type):
    return task_type in {"batch", "communication", "output", "twosteps"}


prompts = ["short_name", "long_name", "timeout", "memory", "type",
           "manager", "scorer", "stubs", "statement", "subtask_structure"]
prompts_info = {}
prompts_info["short_name"] = {"type": "string", "valid": non_existing_task}
prompts_info["long_name"] = {"type": "string"}
prompts_info["timeout"] = {"type": "number", "default": "1"}
prompts_info["memory"] = {"type": "number", "default": "256"}
prompts_info["type"] = {"type": "string", "default": "batch",
                        "valid": valid_type}
prompts_info["manager"] = {"type": "string", "default": ""}
prompts_info["scorer"] = {"type": "string", "default": ""}
prompts_info["stubs"] = {"type": "string", "default": "[]"}
prompts_info["statement"] = {"type": "string", "default": ""}
prompts_info["subtask_structure"] = {"type": "string",
                                     "default": "[[10,10],[90,10]]"}


def read_property(prompt):
    info = prompts_info[prompt]
    if "default" in info:
        text = "Enter value for %s (%s): " % (prompt, info["default"])
    else:
        text = "Enter value for %s: " % prompt

    while True:
        user_value = raw_input(text)
        if user_value == "" and "default" in info:
            user_value = info["default"]
            break
        if info["type"] == "number" and not user_value.isdigit():
            continue
        if "valid" in info and not info["valid"](user_value):
            logger.error("Validation test failed for %s" % prompt)
            continue
        break

    return user_value


def create_module(info):
    module_code = """
def get_long_name():
    return "%s"

def get_timeout():
    return %s

def get_memory():
    return %s

def get_task_type():
    return "%s"

def get_manager():
    return "%s"

def get_scorer():
    return "%s"

def get_stubs():
    return %s

def get_statement():
    return "%s"

def get_subtask_structure():
    return %s

import random, math
    """ % (info["long_name"], info["timeout"], info["memory"],
           info["type"], info["manager"], info["scorer"],
           info["stubs"], info["statement"], info["subtask_structure"])

    module_code += """
def get_subtasks():
    return [
"""

    subtask_structure = eval(info["subtask_structure"])
    total_testcases = sum(st[1] for st in subtask_structure)
    seeds = random.SystemRandom().sample(xrange(10 ** 3, 10 ** 8),
                                         total_testcases)

    testcase_index = 0
    for (score, num_cases) in subtask_structure:
        module_code += ' ' * 8 + """{"score": %s, "testcases": [\n""" % score
        for i in xrange(num_cases):
            module_code += ' ' * 8 + "get_tc(%s, n),\n" % seeds[testcase_index]
            testcase_index += 1
        module_code += ' ' * 4 + "\n]},\n"

    module_code += """
    ]

def get_tc(seed, n):
    random.seed(seed)
    l = [random.randint(0, 100) for i in xrange(n)]
    return {"data":{
        "submission_input": str(n)+"\\n"+ "\\n".join(str(i) for i in l)+"\\n",
        "scorer_hints": str(solve(l)) + "\\n",
    }}

def solve(l):
    return "0"
"""

    task_dir = os.path.join(TASKS_DIR, info["short_name"])
    os.makedirs(task_dir)
    module_path = os.path.join(task_dir, "module.py")
    with open(module_path, 'w') as f:
        f.write(module_code)


def main():
    properties = {}
    for prompt in prompts:
        properties[prompt] = read_property(prompt)

    print("Review:")
    for prompt in prompts:
        print("%s: %s" % (prompt, properties[prompt]))
    if raw_input("Proceed (yes/no): ") != "yes":
        logger.info("Module creation aborted.")
        return
    create_module(properties)


if __name__ == "__main__":
    main()
