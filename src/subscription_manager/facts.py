#
# Copyright (c) 2011 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#

import glob
import os
import simplejson as json
import logging
import gettext
_ = gettext.gettext

import rhsm.config
import certlib
from datetime import datetime

log = logging.getLogger('rhsm-app.' + __name__)


class Facts:
    """
    Manages the facts for this system, maintains a cache of the most 
    recent set sent to server, and checks for changes.
    
    Includes both those hard coded in the app itself, as well as custom 
    facts to be loaded from /etc/rhsm/facts/.
    """

    def __init__(self):
        self.facts = {}
        self.fact_cache_dir = "/var/lib/rhsm/facts"
        self.fact_cache = self.fact_cache_dir + "/facts.json"

        # see bz #627962
        # we would like to have this info, but for now, since it
        # can change constantly on laptops, it makes for a lot of
        # fact churn, so we report it, but ignore it as an indicator
        # that we need to update
        self.graylist = ['cpu.cpu_mhz']

    def delete_cache(self):
        if os.path.exists(self.fact_cache):
            log.info("Deleting facts cache: %s" % self.fact_cache)
            os.remove(self.fact_cache)

    def write_cache(self):
        if not os.access(self.fact_cache_dir, os.R_OK):
            os.makedirs(self.fact_cache_dir)
        try:
            log.info("Writing facts cache: %s" % self.fact_cache)
            f = open(self.fact_cache, "w+")
            json.dump(self.facts, f)
            f.close()
        except IOError, e:
            log.exception(e)

    def read(self):
        cached_facts = {}
        try:
            f = open(self.fact_cache)
            json_buffer = f.read()
            cached_facts = json.loads(json_buffer)
            f.close()
        except IOError:
            log.error("Unable to read %s" % self.fact_cache)
        except ValueError:
            # see bz #669208, #667953
            # ignore facts file parse errors, we are going to generate
            # a new as if it didn't exist
            pass

        return cached_facts

    def get_last_update(self):
        try:
            return datetime.fromtimestamp(os.stat(self.fact_cache).st_mtime)
        except:
            return None

    def delta(self):
        """
        return a dict of any key/values that have changed
        including new keys or deleted keys
        """
        cached_facts = self.read()
        diff = {}
        self.facts = self.get_facts()
        # compare the dicts to see if there is a diff

        for key in self.facts:
            value = self.facts[key]
            # new fact found
            if key not in cached_facts:
                diff[key] = value
            if key in cached_facts:
                # key changed values, ignore changes in graylist facts
                if value != cached_facts[key] and key not in self.graylist:
                    diff[key] = value

        # look for keys that went away
        for key  in cached_facts:
            if key not in self.facts:
                #update with new value, though it doesnt matter
                diff[key] = cached_facts[key]

        return diff

    def get_facts(self):
        if self.facts:
            # see bz #627707
            # there is a little bit of a race between when we load the facts, and when
            # we decide to save them, so delete facts out from under a Fact object means
            # it wasn't detecting it missing in that case and not writing a new one
            return self.facts
        self.facts = self._find_facts()
        return self.facts

    def _find_facts(self):
        # Load custom facts from /etc/rhsm/facts:
        facts_file_glob = "%s/facts/*.facts" % rhsm.config.DEFAULT_CONFIG_DIR
        file_facts = {}
        for file_path in glob.glob(facts_file_glob):
            if os.access(file_path, os.R_OK):
                f = open(file_path)
                json_buffer = f.read()
                file_facts.update(json.loads(json_buffer))

        facts = {}
        import hwprobe
        hw_facts = hwprobe.Hardware().getAll()

        facts.update(hw_facts)
        facts.update(file_facts)

        # fact collection should probably become "pluggable" at some
        # point

        # figure out if we think we have valid entitlements
        sorter = certlib.CertSorter(certlib.ProductDirectory(),
                                    certlib.EntitlementDirectory())

        validity_facts = {'system.entitlements_valid': True}
        if len(sorter.unentitled_products.keys()) > 0 or len(sorter.expired_products.keys()) > 0:
            validity_facts['system.entitlements_valid'] = False

        facts.update(validity_facts)

        return facts

    def update_check(self, uep, consumer_uuid, force=False):
        """
        Check if facts have changed, and push an update if so.

        force option will skip the delta check and just push up the current
        facts regardless.
        """
        if self.delta() or force:
            log.info("Updating facts.")
            facts = self.get_facts()
            uep.updateConsumerFacts(consumer_uuid, facts)
            self.write_cache()
