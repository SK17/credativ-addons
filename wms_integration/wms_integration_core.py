# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2012 credativ ltd (<http://www.credativ.co.uk>). All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import osv, fields
from tools.translate import _
import wms_integration_osv

## TODO Decide whether ER_CSVFTP should be a separate addon or just a
## module in this addon
from external_referential_csvftp import Connection

import re
import logging

_logger = logging.getLogger(__name__)
DEBUG = True

class external_mapping(osv.osv):
    _inherit = 'external.mapping'

    def get_ext_column_headers(self, cr, uid, ids, context=None):
        if not isinstance(ids, list):
            ids = [ids]

        res = []
        line_ids = self.pool.get('external.mapping.line').search(cr, uid, [('mapping_id','=',ids[0])])
        for line in self.pool.get('external.mapping.line').browse(cr, uid, line_ids):
            res.append((line.sequence, line.external_field))

        return [f for s, f in sorted(res, lambda a, b: cmp(a[0], b[0]))]

    def get_oe_column_headers(self, cr, uid, ids, context=None):
        if not isinstance(ids, list):
            ids = [ids]

        res = []
        line_ids = self.pool.get('external.mapping.line').search(cr, uid, [('mapping_id','=',ids[0])])
        for line in self.pool.get('external.mapping.line').browse(cr, uid, line_ids):
            res.append(line.field_id.name)

        return res

    def oe_keys_to_ext_keys(self, cr, uid, ids, oe_rec, context=None):
        if not isinstance(ids, list):
            ids = [ids]

        line_ids = self.pool.get('external.mapping.line').search(cr, uid, [('mapping_id','=',ids[0])])
        defaults = {}
        referential_id = self.read(cr, uid, ids[0], ['referential_id'], context)['referential_id'][0]
        mapping_lines = self.pool.get('external.mapping.line').read(cr, uid, line_ids, ['external_field', 'out_function'])
        rec = self.extdata_from_oevals(cr, uid, referential_id, oe_rec, mapping_lines, defaults, context)
        
        return rec

    def ext_keys_to_oe_keys(self, cr, uid, ids, ext_rec, context=None):
        if not isinstance(ids, list):
            ids = [ids]

        rec = {}
        line_ids = self.pool.get('external.mapping.line').search(cr, uid, [('mapping_id','=',ids[0])])
        for line in self.pool.get('external.mapping.line').browse(cr, uid, line_ids):
            rec[line.field_id.name] = ext_rec[line.external_field]

        return rec

    _columns = {
        'purpose': fields.selection([('data', 'Data'), ('verification', 'Verification')], 'Mapping usage', required=True),
        'external_export_uri': fields.char('External export URI', size=200,
                                           help='For example, an FTP path pointing to a file name on the remote host.'),
        'external_import_uri': fields.char('External import URI', size=200,
                                           help='For example, an FTP path pointing to a file name on the remote host.'),
        'external_verification_mapping': fields.many2one('external.mapping','External verification data format', domain=[('purpose','=','verification')],
                                                         help='Mapping for export verification data to be imported from the remote host.'),
        'last_exported_time': fields.datetime('Last time exported')
        }

    _defaults = {
        'purpose': lambda *a: 'data'
    }

external_mapping()

class external_mapping_line(osv.osv):
    _inherit = 'external.mapping.line'

    _columns = {
        'sequence': fields.integer('Position in field order', required=True,
                                   help='Assign sequential numbers to each line to indicate their required order in the output data.')
        }

    _sql_constraints = [
        ('sequence', 'unique(mapping_id, sequence)', 'Sequence number must be unique.')
        ]

external_mapping_line()

class external_referential(wms_integration_osv.wms_integration_osv):
    _inherit = 'external.referential'

    def _ensure_single_referential(self, cr, uid, id, context=None):
        if context is None:
            context = {}
        if isinstance(id, (list, tuple)):
            if not len(id) == 1:
                raise osv.except_osv(_("Error"), _("External referential connection methods should only called with only one id"))
            else:
                return id[0]
        else:
            return id
    
    def _ensure_wms_integration_referential(self, cr, uid, id, context=None):
        if context is None:
            context = {}
        # FIXME What's a better way of selecting the right external referential?
        if isinstance(id, int):
            referential = self.browse(cr, uid, id, context=context)
            if 'external wms' in referential.type_id.name.lower():
                return referential
            else:
                return False

    _columns = {
        'active': fields.boolean('Active')
        }

    _defaults = {
        'active': lambda *a: 1,
    }

    def external_connection(self, cr, uid, id, DEBUG=False, context=None):
        if context is None:
            context = {}

        id = self._ensure_single_referential(cr, uid, id, context=context)
        referential = self._ensure_wms_integration_referential(cr, uid, id, context=context)
        if not referential:
            return super(external_referential, self).external_connection(cr, uid, id, DEBUG=DEBUG, context=context)

        mo = re.search(r'ftp://(.*?):([0-9]+)', referential.location)
        if not mo:
            _logger.error('Referential location could not be parsed as an FTP URI: %s' % (referential.location,))
            return False
        (host, port) = mo.groups()
        conn = Connection(username=referential.apiusername, password=referential.apipass, host=host, port=int(port), debug=DEBUG)
        return conn or False

    def connect(self, cr, uid, id, context=None):
        if context is None:
            context = {}

        id = self._ensure_single_referential(cr, uid, id, context=context)
        referential = self._ensure_wms_integration_referential(cr, uid, id, context=context)
        if not referential:
            return super(external_referential, self).external_connection(cr, uid, id, DEBUG=DEBUG, context=context)

        core_imp_conn = self.external_connection(cr, uid, id, DEBUG, context=context)
        if core_imp_conn.connect():
            return core_imp_conn
        else:
            raise osv.except_osv(_("Connection Error"), _("Could not connect to server\nCheck location, username & password."))

    def _export_all(self, cr, uid, id, model_name, context=None):
        if context is None:
            context = {}

        id = self._ensure_single_referential(cr, uid, id, context=context)
        referential = self._ensure_wms_integration_referential(cr, uid, id, context=context)

        obj = self.pool.get(model_name)
        ids = obj.search(cr, uid, []) # FIXME: This needs to be a controlled set of IDs!
        
        conn = self.external_connection(cr, uid, id, DEBUG, context=context)
        mapping_ids = self.pool.get('external.mapping').search(cr, uid, [('referential_id','=',id),('model_id','=',model_name)])
        if not mapping_ids:
            raise osv.except_osv(_('Configuration error'), _('No mappings found for the referential "%s" of type "%s"' % (referential.name, referential.type_id.name)))

        res = {}
        mapping_obj = self.pool.get('external.mapping')
        for mapping in mapping_obj.browse(cr, uid, mapping_ids):
            # export the model data
            ext_columns = mapping_obj.get_ext_column_headers(cr, uid, mapping.id, context=context)
            oe_columns = mapping_obj.get_oe_column_headers(cr, uid, mapping.id, context=context)
            conn.init_export(remote_csv_fn=mapping.external_export_uri, external_key_name=mapping.external_key_name, column_headers=ext_columns, required_fields=ext_columns)
            export_data = []
            try:
                data = mapping_obj.oe_keys_to_ext_keys(cr, uid, mapping.id, obj.read(cr, uid, id, [], context=context), context=context)
                export_data.append(data)
            except:
                pass
                # FIXME: something went wrong mapping the object - do proper log to indicate record cannot be exported and continue to the next, or should we fail completely?
                
            conn.call(mapping.external_create_method, records=export_data)
            conn.finalize_export()

            if mapping.external_verification_mapping:
                # TODO Defer the verification by some delay
                res[mapping.id] = self._verify_export(cr, uid, mapping, [res[mapping.external_key_name] for res in export_data], conn, context)
            else:
                _logger.info('CSV export: Mapping has no verification mapping defined.')

        return all(res.values())

    def _verify_export(self, cr, uid, export_mapping, export_ids, conn, context=None):
        if context is None:
            context = {}

        mapping_obj = self.pool.get('external.mapping')
        verification_mapping = mapping_obj.browse(cr, uid, export_mapping.external_verification_mapping.id, context=context)
        verification_columns = mapping_obj.get_ext_column_headers(cr, uid, verification_mapping.id)
        conn.init_import(remote_csv_fn=verification_mapping.external_import_uri, external_key_name=verification_mapping.external_key_name, column_headers=verification_columns)
        verification = conn.call(verification_mapping.external_list_method)
        conn.finalize_import()

        received_ids = [r[verification_mapping.external_key_name] for r in verification]
        if set(export_ids) == set(received_ids):
            return True
        else:
            missing = list(set(export_ids) - set(received_ids))
            _logger.error('CSV export: Verification IDs returned by server did not match sent IDs. Missing: %d.' % (len(missing),))
            # TODO Report error
            return False

    def export_products(self, cr, uid, id, context=None):
        return self._export_all(cr, uid, id, 'product.product', context=context)

external_referential()
