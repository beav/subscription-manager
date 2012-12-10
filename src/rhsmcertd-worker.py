#!/usr/bin/python
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

import sys
sys.path.append("/usr/share/rhsm")

import logging

from rhsm import connection
from rhsm import certificate
from subscription_manager import certmgr
from subscription_manager import logutil
from subscription_manager import managerlib
from subscription_manager.certlib import ConsumerIdentity, RhicCertificate
from subscription_manager.i18n_optparse import OptionParser, \
    WrappedIndentedHelpFormatter, USAGE
from subscription_manager import rhiclib
from subscription_manager.facts import Facts
from subscription_manager.certdirectory import EntitlementDirectory, ProductDirectory, Writer

import gettext
_ = gettext.gettext


def main(options, log):

    if RhicCertificate.existsAndValid():
        facts = Facts(ent_dir=EntitlementDirectory(),
                              prod_dir=ProductDirectory())
        iproducts = managerlib.getInstalledProductStatus(ProductDirectory(),
                EntitlementDirectory(), facts.get_facts())

        product_certs = []
        for product in iproducts:
            product_certs.append(product[1])

        certs = []
        try:
            certs = rhiclib.getCerts(facts.to_dict(), product_certs)
        except connection.NetworkException, e:
            if e.code == 410:
                print _("RHIC was deleted by upstream server. See rhsm.log for more detail.")
                RhicCertificate.move()
                sys.exit(-1)
            else:
                raise
        except connection.RemoteServerException, e:
            if e.code == 404:
                print _("RHIC was not found by upstream server. See rhsm.log for more detail.")
                RhicCertificate.move()
                sys.exit(-1)
            else:
                raise

        if certs:
            try:
                writer = Writer()
                cert = certificate.create_from_pem(certs['cert'])
                key = certificate.Key(certs['key'])
                writer.write(key, cert)
            except:
                raise

        rhiclib.cleanExpiredCerts(ProductDirectory(), EntitlementDirectory(), facts.to_dict())

        sys.exit(0)

    if not ConsumerIdentity.existsAndValid():
        log.error('Either the consumer is not registered or the certificates' +
                  ' are corrupted. Certificate update using daemon failed.')
        sys.exit(-1)
    print _('Updating entitlement certificates & repositories')

    try:
        uep = connection.UEPConnection(cert_file=ConsumerIdentity.certpath(),
                                       key_file=ConsumerIdentity.keypath())
        mgr = certmgr.CertManager(uep=uep)
        updates = mgr.update(options.autoheal)

        print _('%d updates required') % updates
        print _('done')
    except connection.GoneException, ge:
        uuid = ConsumerIdentity.read().getConsumerId()
        if ge.deleted_id == uuid:
            log.critical(_("This consumer's profile has been deleted from the server. It's local certificates will now be archived"))
            managerlib.clean_all_data()
            log.critical(_("Certificates archived to '/etc/pki/consumer.old'. Contact your system administrator if you need more information."))

        raise ge


if __name__ == '__main__':

    logutil.init_logger()
    log = logging.getLogger('rhsm-app.' + __name__)

    parser = OptionParser(usage=USAGE,
                          formatter=WrappedIndentedHelpFormatter())
    parser.add_option("--autoheal", dest="autoheal", action="store_true",
            default=False, help="perform an autoheal check")
    (options, args) = parser.parse_args()
    try:
        main(options, log)
    except SystemExit, se:
        # sys.exit triggers an exception in older Python versions, which
        # in this case  we can safely ignore as we do not want to log the
        # stack trace. We need to check the code, since we want to signal
        # exit with failure to the caller. Otherwise, we will exit with 0
        if se.code:
            sys.exit(-1)
        pass
    except Exception, e:
        log.error("Error while updating certificates using daemon")
        print _('Unable to update entitlement certificates and repositories')
        log.exception(e)
        sys.exit(-1)
