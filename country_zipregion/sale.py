# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 credativ Ltd (<http://credativ.co.uk>).
#    All Rights Reserved
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
from util import _get_zipregion_group_names

class sale_order(osv.osv):
    _inherit = 'sale.order'

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        newargs, ids = [], []
        for arg in args:
            if arg[0] == 'region_group_id_select':
                cr.execute("""SELECT so.id FROM sale_order so
                    INNER JOIN res_partner_address rpa ON so.partner_shipping_id = rpa.id
                    INNER JOIN res_zip_region zr ON zr.country_id = rpa.country_id AND rpa.zip ~ COALESCE(zr.zip_regex, '')
                    INNER JOIN res_zip_region_rel zrr ON zrr.region_id = zr.id
                    INNER JOIN res_zip_region_group zrg ON zrr.region_group_id = zrg.id
                    WHERE zrg.id = %s GROUP BY so.id""", (arg[2],))
                ids = map(lambda x:x[0], cr.fetchall())
                if ids: newargs.append(('id', 'in', ids))
                else: newargs.append(('id', 'in', [0]))
            else:
                newargs.append(arg)
        return super(sale_order, self).search(cr, user, newargs, offset=offset, limit=limit, order=order, context=context, count=count)
    
    _columns = {
        'region_group_id_select': fields.selection(_get_zipregion_group_names, 'Zip Region Group (Shipping)'),
        }

sale_order()
