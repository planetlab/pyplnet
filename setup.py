#!/usr/bin/python
#
# Setup script for pyplnet
#
# Daniel Hokka Zakrisson <daniel@hozac.com>
# Copyright (C) 2008 The Trustees of Princeton University
#
# $Id$
#

import os
from distutils.core import setup, Extension
from distutils.cmd import Command
from distutils.command.sdist import sdist

extra_dist = ['pyplnet.spec']

class my_sdist(sdist):
    def add_defaults(self):
        sdist.add_defaults(self)
        if self.distribution.has_data_files():
            for data in self.distribution.data_files:
                self.filelist.extend(data[1])
        self.filelist.extend(extra_dist)

class bdist_rpmspec(Command):
    user_options = [("rpmdef=", None, "define variables")]
    def initialize_options(self):
        self.rpmdef = None
    def finalize_options(self):
        pass
    def run(self):
        saved_dist_files = self.distribution.dist_files[:]
        sdist = self.reinitialize_command('sdist')
        sdist.formats = ['gztar']
        self.run_command('sdist')
        self.distribution.dist_files = saved_dist_files
        command = ["rpmbuild", "-tb"]
        if self.rpmdef is not None:
            command.extend(["--define", self.rpmdef])
        command.append(sdist.get_archive_files()[0])
        print "running '%s'" % "' '".join(command)
        if not self.dry_run:
            os.spawnvp(os.P_WAIT, "rpmbuild", command)

setup(
    name='pyplnet',
    version='4.3',
    py_modules=[
    'plnet',
    'modprobe',
    'sioc',
    ],
    cmdclass={'sdist': my_sdist, 'bdist_rpmspec': bdist_rpmspec},
    )
