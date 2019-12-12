##############################################################################
#
# Copyright (c) 2006 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Bootstrap a buildout-based project

Simply run this script in a directory containing a buildout.cfg.
The script accepts buildout command-line options, so you can
use the -c option to specify an alternate configuration file.
"""

import os, shutil, sys, tempfile
from optparse import OptionParser

tmpeggs = tempfile.mkdtemp()

from optparse import OptionParser


# parsing arguments
parser = OptionParser()
parser.add_option("-v", "--version", dest="version",
                          help="use a specific zc.buildout version")
parser.add_option("-d", "--distribute",
                   action="store_true", dest="distribute", default=False,
                   help="Use Disribute rather than Setuptools.")

options, args = parser.parse_args()
if options.version:
    print("bootstrap.py version %s" % __version__)
    sys.exit(0)


######################################################################
# load/install setuptools

try:
    import pkg_resources
    if not hasattr(pkg_resources, '_distribute'):
        to_reload = False
        raise ImportError
except ImportError:
    ez = {}

    if to_reload:
        reload(pkg_resources)
    else:
        import pkg_resources

if sys.platform == 'win32':
    def quote(c):
        if ' ' in c:
            return '"%s"' % c # work around spawn lamosity on windows
        else:
            return c
else:
    def quote (c):
        return c

ez = {}
if os.path.exists('ez_setup.py'):
    exec(open('ez_setup.py').read(), ez)
else:
    exec(urlopen('https://bootstrap.pypa.io/ez_setup.py').read(), ez)

if not options.allow_site_packages:
    # ez_setup imports site, which adds site packages
    # this will remove them from the path to ensure that incompatible versions
    # of setuptools are not in the path
    import site
    # inside a virtualenv, there is no 'getsitepackages'.
    # We can't remove these reliably
    if hasattr(site, 'getsitepackages'):
        for sitepackage_path in site.getsitepackages():
            # Strip all site-packages directories from sys.path that
            # are not sys.prefix; this is because on Windows
            # sys.prefix is a site-package directory.
            if sitepackage_path != sys.prefix:
                sys.path[:] = [x for x in sys.path
                               if sitepackage_path not in x]

setup_args = dict(to_dir=tmpeggs, download_delay=0)

if options.setuptools_version is not None:
    setup_args['version'] = options.setuptools_version
if options.setuptools_to_dir is not None:
    setup_args['to_dir'] = options.setuptools_to_dir

ez['use_setuptools'](**setup_args)
import setuptools
import pkg_resources

# This does not (always?) update the default working set.  We will
# do it.
for path in sys.path:
    if path not in pkg_resources.working_set.entries:
        pkg_resources.working_set.add_entry(path)

######################################################################
# Install buildout

ws = pkg_resources.working_set

setuptools_path = ws.find(
    pkg_resources.Requirement.parse('setuptools')).location

# Fix sys.path here as easy_install.pth added before PYTHONPATH
cmd = [sys.executable, '-c',
       'import sys; sys.path[0:0] = [%r]; ' % setuptools_path +
       'from setuptools.command.easy_install import main; main()',
       '-mZqNxd', tmpeggs]

find_links = os.environ.get(
    'bootstrap-testing-find-links',
    options.find_links or
    ('http://downloads.buildout.org/'
     if options.accept_buildout_test_releases else None)
    )
if find_links:
    cmd.extend(['-f', find_links])

requirement = 'zc.buildout'
version = options.buildout_version
if version is None and not options.accept_buildout_test_releases:
    # Figure out the most recent final version of zc.buildout.
    import setuptools.package_index
    _final_parts = '*final-', '*final'

    def _final_version(parsed_version):
        try:
            return not parsed_version.is_prerelease
        except AttributeError:
            # Older setuptools
            for part in parsed_version:
                if (part[:1] == '*') and (part not in _final_parts):
                    return False
            return True

    index = setuptools.package_index.PackageIndex(
        search_path=[setuptools_path])
    if find_links:
        index.add_find_links((find_links,))
    req = pkg_resources.Requirement.parse(requirement)
    if index.obtain(req) is not None:
        best = []
        bestv = None
        for dist in index[req.project_name]:
            distv = dist.parsed_version
            if _final_version(distv):
                if bestv is None or distv > bestv:
                    best = [dist]
                    bestv = distv
                elif distv == bestv:
                    best.append(dist)
        if best:
            best.sort()
            version = best[-1].version
if version:
    requirement = '=='.join((requirement, version))
cmd.append(requirement)

import subprocess
if subprocess.call(cmd) != 0:
    raise Exception(
        "Failed to execute command:\n%s" % repr(cmd)[1:-1])

######################################################################
# Import and run buildout

ws.add_entry(tmpeggs)
ws.require(requirement)
import zc.buildout.buildout

if not [a for a in args if '=' not in a]:
    args.append('bootstrap')

# if -c was provided, we push it back into args for buildout' main function
if options.config_file is not None:
    args[0:0] = ['-c', options.config_file]

zc.buildout.buildout.main(args)
shutil.rmtree(tmpeggs)
