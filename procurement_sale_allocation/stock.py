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
import netsvc

class StockMove(osv.Model):
    _inherit = 'stock.move'

    def action_cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        procurement_obj = self.pool.get('procurement.order')
        wkf_service = netsvc.LocalService('workflow')

        # If we are cancelling a PO move, deallocate any procurements it is meant to be fulfilling
        # We need to get these IDs before the super as we lose the link to move_dest_id
        unassign_proc_ids = []
        if ids:
            cr.execute("""SELECT proc.id
                FROM stock_move sm_po
                INNER JOIN procurement_order proc ON proc.move_id = sm_po.move_dest_id
                WHERE sm_po.purchase_line_id IS NOT NULL
                AND sm_po.id IN %s""", (tuple(ids),))
            unassign_proc_ids = [x[0] for x in cr.fetchall()]

        res = super(StockMove, self).action_cancel(cr, uid, ids, context=context)
        if ids:
            # Find all procurements stuck in the purchase subflow and remove their purchase order link
            proc_ids = procurement_obj.search(cr, uid, [('move_id', 'in', ids), ('state', 'in', ('running', 'confirmed')), ('purchase_id', '!=', False)], context=context)
            if proc_ids:
                procurement_obj.write(cr, uid, proc_ids, {'purchase_id': False}, context=context)
                for proc_id in proc_ids:
                    wkf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_cancel', cr)

            # If we are in a PO and are allocated to a procurement, deallocate the procurement
            if unassign_proc_ids:
                ctx = context.copy()
                ctx['force_po_unassign'] = True
                for procurement in procurement_obj.browse(cr, uid, unassign_proc_ids, context=ctx):
                    procurement.write({'purchase_id': False}, context=ctx)
                    procurement.write({'procure_method': procurement.procure_method}, context=ctx)
        return res

class StockPicking(osv.Model):
    _inherit = 'stock.picking'

    def _get_procurement_ids(self, cr, uid, ids, field_name, arg, context=None):
        proc_obj = self.pool.get('procurement.order')
        result = {}
        for id in ids:
            proc_ids = proc_obj.search(cr, uid, [('move_id.picking_id', '=', id)])
            result[id] = proc_ids
        return result

    _columns = {
            'procurement_ids': fields.function(_get_procurement_ids, type='one2many', relation='procurement.order', string='Procurements', readonly=True, copy=False),
        }

class StockPickingOut(osv.Model):
    _inherit = 'stock.picking.out'

    def _get_procurement_ids(self, cr, uid, ids, field_name, arg, context=None):
        proc_obj = self.pool.get('procurement.order')
        result = {}
        for id in ids:
            proc_ids = proc_obj.search(cr, uid, [('move_id.picking_id', '=', id)])
            result[id] = proc_ids
        return result

    _columns = {
            'procurement_ids': fields.function(_get_procurement_ids, type='one2many', relation='procurement.order', string='Procurements', readonly=True, copy=False),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
