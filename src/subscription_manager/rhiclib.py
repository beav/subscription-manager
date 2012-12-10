#
# common rhic calls
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
import logging
import time

log = logging.getLogger('rhsm-app.' + __name__)

from rhsm.connection import SpliceConnection, AcceptedException
from subscription_manager import managerlib
from subscription_manager import cert_sorter
from subscription_manager.certlib import RhicCertificate


import gettext
_ = gettext.gettext

LOOKUP_RETRY_DELAY = 5
LOOKUP_MAX_ATTEMPTS = 2

def cleanExpiredCerts(product_dir, entitlement_dir, facts_dict):
    # clean up expired certs
    cs = cert_sorter.CertSorter(product_dir, entitlement_dir, facts_dict)
    log.info("deleting %s expired certs" % len(cs.expired_entitlement_certs))

    for cert in cs.expired_entitlement_certs:
        log.info("deleting expired cert %s" % cert.serial)
        cert.delete()


def getCerts(facts_dict, product_certs):

    rhic = RhicCertificate.read()

    try:
        identifier = managerlib.getRhicMachineId(facts_dict)
        log.info("machine identifier is %s" % identifier)
    except:
        log.error("unable to determine machine identifier, aborting")
        raise

    results = None

    # grab the certs from RCS
    for i in range(LOOKUP_MAX_ATTEMPTS):
        try:
            results = SpliceConnection().getCerts(rhic, identifier, installed_products=product_certs, facts_dict=facts_dict)
        except AcceptedException:
            log.info("got a 202, retrying after pause of %s seconds" % LOOKUP_RETRY_DELAY)
            time.sleep(LOOKUP_RETRY_DELAY)
        else:
            break

    return results
