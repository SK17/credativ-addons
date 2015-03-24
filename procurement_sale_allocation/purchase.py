# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 credativ ltd (<http://www.credativ.co.uk>). All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv, fields
from openerp.tools.translate import _
import netsvc

class PurchaseOrder(osv.Model):
    _inherit = 'purchase.order'

    _columns = {
            'procurement_ids': fields.one2many('procurement.order', 'purchase_id', 'Procurements', readonly=True, copy=False),
            'order_line_unalloc': fields.one2many('purchase.order.line', 'order_id', 'Order Lines', domain=[('move_dest_id', '=', False)], readonly=True, copy=False),
        }

    def allocate_check_stock(self, cr, uid, ids, proc_ids, context=None):
        assert len(ids) == 1 and len(proc_ids) == 1, "This function only supports being called with a single purchase ID"
        purchase_line_obj = self.pool.get('purchase.order.line')
        procurement_obj = self.pool.get('procurement.order')
        uom_obj = self.pool.get('product.uom')
        po = self.browse(cr, uid, ids[0], context=context)
        for proc in procurement_obj.browse(cr, uid, proc_ids, context=context):
            pol_ids = purchase_line_obj.search(cr, uid, [('move_dest_id', '=', False), ('state', '!=', 'cancel'), ('order_id', '=', po.id), ('product_id', '=', proc.product_id.id)], context=context)
            pol_assign_id = False
            for line in purchase_line_obj.browse(cr, uid, pol_ids, context=context):
                purchase_uom_qty = uom_obj._compute_qty(cr, uid, proc.product_uom.id, proc.product_qty, line.product_uom.id)
                if line.product_qty >= purchase_uom_qty:
                    pol_assign_id = line.id
                    break
            if not pol_assign_id:
                return False
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
