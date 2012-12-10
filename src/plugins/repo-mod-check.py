#
# Copyright (c) 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.
#

import os
from yum.plugins import TYPE_CORE, PluginYumExit

requires_api_version = '2.6'
plugin_type = (TYPE_CORE,)

repofiles = {}

YUM_REPO_DIR = '/etc/yum.repos.d/'

ERR_MSG = """
Download errors have been detected, and one or more repo files have changed since start of download. Please re-run yum in order to finish downloads and complete transaction.
"""

def predownload_hook(conduit):
    """
    save a list of mtimes for repo files, so we can check it later
    """
    global repofiles
    for f in os.listdir(YUM_REPO_DIR):
        if f.endswith(".repo"):
	    fname = YUM_REPO_DIR + f
            repofiles[fname] = os.path.getmtime(fname)
            conduit.info(7, "last mod time of %s is %s" % (fname, repofiles[fname]))

def postdownload_hook(conduit):
    """
    check if a repo file was changed during the download. If it has, and if a
    download failed, inform the user.
    """
    global repofiles
    if (conduit.getErrors()):
        for f in os.listdir(YUM_REPO_DIR):
            if f.endswith(".repo"):
	        fname = YUM_REPO_DIR + f
                if (repofiles[fname] != os.path.getmtime(fname)):
                    raise PluginYumExit(ERR_MSG)
