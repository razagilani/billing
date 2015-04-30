#!/usr/bin/env python
from operator import attrgetter
import os
from argparse import ArgumentParser
from itertools import groupby
from errno import EEXIST, ENOENT

from exc import InvalidParameter

from reebill.bill_templates import ThermalBillDoc
from reebill.bill_templates import SummaryBillDoc

class ReebillFileHandler(object):
    '''Methods for working with Reebill PDF files.
    '''
    FILE_NAME_FORMAT = '%(account)s_%(sequence)04d.pdf'

    @staticmethod
    def _ensure_directory_exists(path):
        '''Create directories if necessary to ensure that the given path is
        valid.
        '''
        try:
            os.makedirs(os.path.dirname(path))
        except OSError as e:
            # makedirs fails if the directories already exist
            if e.errno == EEXIST:
                pass

    def __init__(self, output_dir_path, teva_accounts):
        '''
        :param template_dir_path: path of directory where
        "templates" and fonts are stored, RELATIVE to billing directory.
        :param output_dir_path: absolute path of directory where reebill PDF
        files are stored.
        :param teva accounts: list of customer accounts (strings) that should
        have PDFs with the "teva" PDF format instead of the normal one.
        '''
        base_path = os.path.dirname(os.path.dirname(__file__))
        template_dir_path = 'reebill/reebill_templates'
        self._template_dir_path = os.path.join(base_path, template_dir_path)
        if not os.access(self._template_dir_path, os.R_OK):
            raise InvalidParameter('Path "%s" is not readable' %
                                   self._template_dir_path)
        self._pdf_dir_path = output_dir_path
        self._teva_accounts = teva_accounts

    def get_file_name(self, reebill):
        '''Return name of the PDF file associated with the given :class:`ReeBill`
        (the file may not exist).
        '''
        return ReebillFileHandler.FILE_NAME_FORMAT % dict(
                account=reebill.get_account(), sequence=reebill.sequence)

    def get_file_contents(self, reebill):
        '''Return contents of the PDF file associated with the given
        :class:`ReeBill` (the file may not exist).
        '''
        file_path = os.path.join(self._pdf_dir_path, reebill.get_account(),
                self.get_file_name(reebill))
        file_obj = open(file_path, 'r')
        contents = file_obj.read()
        file_obj.close()
        return contents

    def get_file_path(self, reebill):
        '''Return full path to the PDF file associated with the given
        :class:`ReeBill` (the file may not exist).
        '''
        return os.path.join(self._pdf_dir_path,reebill.get_account(),
                self.get_file_name(reebill))

    def get_file(self, reebill):
        """Return the file itself opened in "rb" mode. The consumer must
        close it.
        """
        return open(self.get_file_path(reebill), 'rb')

    def delete_file(self, reebill, ignore_missing=False):
        '''Delete the file belonging to the given :class:`ReeBill`.
        If ignore_missing is True, no exception will be raised if the file to
        be deleted does not exist.
        '''
        # note that this will fail if the file does not exist. that is not
        # supposed to happen so it is not being ignored.
        path = self.get_file_path(reebill)
        try:
            os.remove(path)
        except OSError as e:
            if not ignore_missing or e.errno != ENOENT:
                raise

    def _generate_document(self, reebill):
        # charges must be sorted by type in order for 'groupby' to work below
        sorted_charges = sorted(reebill.charges, key=attrgetter('type'))

        def get_utilbill_register_data_for_reebill_reading(reading):
            utilbill = reading.reebill.utilbill
            try:
                register = next(r for r in utilbill.registers
                        if r.register_binding == reading.register_binding)
            except StopIteration:
                return '', '', ''
            return (register.meter_identifier, register.identifier,
                    register.description)
        return {
            'account': reebill.get_account(),
            'sequence': str(reebill.sequence),
            'begin_period': reebill.utilbills[0].period_start,
            'manual_adjustment': reebill.manual_adjustment,
            'balance_forward': reebill.balance_forward,
            'payment_received': reebill.payment_received,
            'balance_due': reebill.balance_due,
            'total_energy_consumed': reebill.get_total_renewable_energy() + \
                                     reebill.get_total_conventional_energy(),
            'total_re_consumed': reebill.get_total_renewable_energy(),
            'total_ce_consumed': reebill.get_total_conventional_energy(),
            'total_re_delivered_grid': 0,
            'total_re_generated': reebill.get_total_conventional_energy(),
            'due_date': reebill.due_date,
            'end_period': reebill.utilbill.period_end,
            'hypothetical_charges': reebill.get_total_hypothetical_charges(),
            'discount_rate': reebill.discount_rate,
            'issue_date': reebill.issue_date,
            'late_charge': reebill.late_charge,
            'prior_balance': reebill.prior_balance,
            'ree_charge': reebill.ree_charge,
            'neg_credit_applied': 0,
            'neg_ree_charge': 0,
            'neg_credit_balance': 0,
            'ree_savings': reebill.ree_savings,
            'neg_ree_savings': 0,
            'neg_ree_potential_savings': 0,
            'ree_value': reebill.ree_value,
            'service_addressee': reebill.service_address.addressee,
            'service_city': reebill.service_address.city,
            'service_postal_code': reebill.service_address.postal_code,
            'service_state': reebill.service_address.state,
            'service_street': reebill.service_address.street,
            'total_adjustment': reebill.total_adjustment,
            'total_utility_charges': reebill.get_total_actual_charges(),
            'payment_addressee': 'Nextility',
            'payment_city': 'Washington',
            'payment_postal_code': '20009',
            'payment_state': 'DC',
            'payment_street': '1606 20th St NW',
            'billing_addressee': reebill.billing_address.addressee,
            'billing_street': reebill.billing_address.street,
            'billing_city': reebill.billing_address.city,
            'billing_postal_code': reebill.billing_address.postal_code,
            'billing_state': reebill.billing_address.state,
            'utility_meters':  [{
                'meter_id': meter_id,
                    'registers': [{
                    'register_id': register_id,
                    'description': description,
                    'shadow_total': reading.renewable_quantity,
                    'utility_total': reading.conventional_quantity,
                    'total': (reading.conventional_quantity +
                              reading.renewable_quantity),
                    'quantity_units': reading.unit,
                } for reading in readings]
            } for (meter_id, register_id, description), readings
                    in groupby(reebill.readings, key=lambda r: \
                    get_utilbill_register_data_for_reebill_reading(r))],
            'hypothetical_chargegroups': {
                type: [{
                    'description': charge.description,
                    'quantity': charge.h_quantity,
                    'rate': charge.rate,
                    'total': charge.h_total
                } for charge in charges]
            for type, charges in groupby(sorted_charges,
                                               key=attrgetter('type'))},
        }

    def _get_skin_directory_name_for_account(self, account):
        '''Return name of the directory in which "skins" (image files) to be
        used in bill PDFs for the given account are stored.
        '''
        if account in self._teva_accounts:
            return 'teva'
        else:
            # TODO this will be set by type of energy service
            # see https://www.pivotaltracker.com/story/show/78497806
            return 'nextility_swh'

    def render(self, reebill):
        '''Create a PDF of the given :class:`ReeBill`.
        '''
        path = self.get_file_path(reebill)
        self._ensure_directory_exists(path)
        dir_path, file_name = os.path.split(path)
        document = self._generate_document(reebill)
        ThermalBillDoc().render([document], dir_path,
                file_name, self._template_dir_path,
                self._get_skin_directory_name_for_account(
                        reebill.get_account()))

    #TODO implement for summary page
    def render_summary(self, reebills):
        '''Create a summary PDF of a list of bills
        '''
        pass
        path = self.get_file_path(reebill[0])
        print path
        doc = SummaryBillDoc()
        doc.render(bill_data, args.output_directory, "%s-%s" % ("{0:02}".format(i), path), args.skin_directory, args.skin_name)



class SummaryFileGenerator(object):
    """Generates a "summary" document from multiple ReeBills.
    """
    def __init__(self, reebill_file_handler, pdf_concatenator):
        self._reebill_file_handler = reebill_file_handler
        self._pdf_concatenator = pdf_concatenator

    def generate_summary_file(self, reebills, output_file):
        """
        :param reebills: nonempty iterable of ReeBills that should be included.
        :param output_file: file where the summary will be written.
        """
        assert reebills

        # write summary to a file
        summary_file = self._reebill_file_handler.render_summary(reebills)
        summary_input_file = self._reebill_file_handler.get_file(summary_file)
        self._pdf_concatenator.append(summary_input_file)

        for reebill in reebills:
            # write every bill to a file, read it back again, and append it
            self._reebill_file_handler.render(reebill)
            input_file = self._reebill_file_handler.get_file(reebill)
            self._pdf_concatenator.append(input_file)

        # TODO: eventually there may be extra pages not taken from the bill
        # PDFs
        self._pdf_concatenator.write_result(output_file)
