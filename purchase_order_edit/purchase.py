# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 credativ Ltd (<http://credativ.co.uk>).
#    All Rights Reserved
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
from tools.translate import _
import netsvc
from openerp.addons.base_order_edit.order_edit import OrderEdit

import cProfile, pstats, StringIO
import logging
_logger = logging.getLogger(__name__)

class PurchaseOrder(osv.osv, OrderEdit):
    _inherit = 'purchase.order'

    _columns = {
        'order_edit_id': fields.many2one('purchase.order', 'Edit of Order', readonly=True),
    }

    def action_run_order_edit(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        # FIXME: Hack to prevent PO or POL translations from being copied, of which there are none
        # This appears to be a core bug in OpenERP that is spends about 80% of the time
        # preparing fields for translation even though none of them are translatable!
        ctx.setdefault('__copy_translations_seen', {})
        ctx['__copy_translations_seen'].setdefault('purchase.order', [])
        ctx['__copy_translations_seen']['purchase.order'].extend(ids)

        if not ids:
            return {}
        oe_obj = self.pool.get('purchase.order.edit_wizard')

        pr = cProfile.Profile()
        pr.enable()

        ctx.update({'active_id': ids[0], 'active_ids': [ids[0]]})
        oe_id = oe_obj.create(cr, uid, {}, context=ctx)
        res = oe_obj.edit_order(cr, uid, [oe_id], context=ctx)

        pr.disable()
        s = StringIO.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats()
        _logger.warning('PO Edit IDs %s:\n%s' % (ids, s.getvalue()))

        return res

    def allocate_check_restrict(self, cr, uid, ids, context=None):
        restricted_ids = super(PurchaseOrder, self).allocate_check_restrict(cr, uid, ids, context=context)
        for purchase in self.browse(cr, uid, ids, context=context):
            if purchase.order_edit_id and purchase.state == 'draft':
                restricted_ids.append(purchase.id)
        return list(set(restricted_ids))

    def copy_data(self, cr, uid, id_, default=None, context=None):
        if not default:
            default = {}
        if 'order_edit_id' not in default:
            default['order_edit_id'] = False
        default['procurement_ids'] = []
        default['order_line_unalloc'] = []
        return super(PurchaseOrder, self).copy_data(cr, uid, id_, default, context=context)

    def action_picking_create(self, cr, uid, ids, context=None):

        pr = cProfile.Profile()
        pr.enable()

        for order in self.browse(cr, uid, ids, context=context):
            if order.order_edit_id and self.allocate_check_restrict(cr, uid, [order.order_edit_id.id], context=context):
                raise osv.except_osv(_('Error!'),
                    _('Purchase order has become restricted and it is no longer possible to edit'))
        line_moves, remain_moves = self.check_consolidation(cr, uid, ids, context)
        res = super(PurchaseOrder, self).action_picking_create(cr, uid, ids, context=context)
        self._fixup_created_picking(cr, uid, ids, line_moves, remain_moves, context)
        for order in self.browse(cr, uid, ids, context=context):
            if order.order_edit_id:
                self._edit_cancel(cr, uid, [order.order_edit_id.id], 'Edit Cancel:%s' % order.order_edit_id.name, accept_done=True, cancel_assigned=True, context=context)

        pr.disable()
        s = StringIO.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats()
        _logger.warning('PO Confirm IDs %s:\n%s' % (ids, s.getvalue()))

        return res

    def _cancel_check_order(self, purchase, cancel_assigned, accept_done, context=None):
        if purchase.state not in ('confirmed','approved'):
            raise osv.except_osv(_('Error!'), _('Purchase order being edited should be in progress.'))
        for pick in purchase.picking_ids:
            if not cancel_assigned and pick.state == 'assigned':
                raise osv.except_osv(_('Error!'),
                    _('Unable to edit order, stock has already been assigned - please cancel pickings manually'))
            if not accept_done and pick.state == 'done':
                raise osv.except_osv(_('Error!'),
                    _('Unable to edit order, stock has already been shipped - please process manually'))

    def _edit_cancel(self, cr, uid, ids, description, cancel_assigned=False, accept_done=False, return_cois=False, context=None):
        wf_service = netsvc.LocalService("workflow")
        res = {}
        for purchase in self.browse(cr, uid, ids, context=context):
            self._cancel_check_order(purchase, cancel_assigned, accept_done, context=context)
            self._cancel_pickings(cr, uid, purchase, accept_done, context=context)
            self.pool.get('purchase.order.line').write(cr, uid, [line.id for line in purchase.order_line], {'state': 'cancel'}, context=context)
            self.write(cr, uid, [purchase.id], {'state': 'cancel'}, context=context)
            wf_service.trg_write(uid, 'purchase.order', purchase.id, cr)
            self.message_post(cr, uid, [purchase.id], body=_('Purchase order %s cancelled due to order edit') % (purchase.name,), context=context)
        return res

    def _fixup_created_picking(self, cr, uid, ids, line_moves, remain_moves, context=None):
        # This is a post confirm hook
        # - post-action hook: replace new stuff generated in the action with old stuff
        # identified in the pre-action hook
        move_pool = self.pool.get('stock.move')
        pick_pool = self.pool.get('stock.picking')
        line_pool = self.pool.get('purchase.order.line')
        wf_service = netsvc.LocalService("workflow")

        if line_moves is not None:
            for line_id, old_moves in line_moves.iteritems():
                line = line_pool.browse(cr, uid, line_id)
                line_pool.write(cr, uid, [line_id], {'state': 'confirmed'}, context=context)
                created_moves = [x for x in line.move_ids]
                for old_move in old_moves:
                    try:
                        created_move = created_moves.pop()
                    except IndexError:
                        raise osv.except_osv(_('Error!'), _('The edited order must include any done or assigned moves'))
                    # Move old stock_move and stock_picking to new order
                    picking = created_move.picking_id
                    move_pool.write(cr, uid, [old_move.id], {'purchase_line_id': line_id})
                    pick_pool.write(cr, uid, old_move.picking_id.id, {'purchase_id':line.order_id.id})
                    # Cancel and remove new replaced stock_move and stock_picking
                    move_pool.write(cr, uid, created_move.id, {'purchase_line_id': False, 'picking_id': False})
                    created_move.action_cancel()
                    picking.refresh()
                    if not picking.move_lines:
                        pick_pool.write(cr, uid, picking.id, {'purchase_id': False})
                        wf_service.trg_validate(uid, 'stock.picking', picking.id, 'button_cancel', cr)
                        wf_service.trg_validate(uid, 'stock.picking', picking.id, 'button_cancel', cr)
                        pick_pool.action_cancel(cr, uid, [picking.id])
                assert(len(created_moves) == 0)

        if remain_moves is not None:
            picking = None
            old_picking_copy = None
            for line_id, old_moves in remain_moves.iteritems():
                line = line_pool.browse(cr, uid, line_id)
                line_pool.write(cr, uid, [line_id], {'state': 'confirmed'}, context=context)
                created_moves = [x for x in line.move_ids]
                if not picking and not old_picking_copy:
                    picking = old_moves and old_moves[0].picking_id or None
                    if picking:
                        old_picking_copy = pick_pool.copy(cr, uid, picking.id, {'move_lines': [], 'purchase_id': line.order_id.id, 'name': '/'})
                if not old_picking_copy or not created_moves:
                    continue
                for created_move in created_moves:
                    new_picking = created_move.picking_id
                    move_pool.write(cr, uid, created_move.id, {'purchase_line_id': line_id, 'picking_id': old_picking_copy})
                    new_picking.refresh()
                    if not new_picking.move_lines:
                        pick_pool.write(cr, uid, new_picking.id, {'purchase_id': False})
                        wf_service.trg_validate(uid, 'stock.picking', new_picking.id, 'button_cancel', cr)
                        wf_service.trg_validate(uid, 'stock.picking', new_picking.id, 'button_cancel', cr)
                        pick_pool.action_cancel(cr, uid, [new_picking.id])
            if old_picking_copy:
                wf_service.trg_validate(uid, 'stock.picking', old_picking_copy, 'button_confirm', cr)
            # Old confirmed moves get canceled during refund

        return True

class PurchaseOrderLine(osv.osv):
    _inherit = 'purchase.order.line'

    def copy_data(self, cr, uid, id_, default=None, context=None):
        if not default:
            default = {}
        default['move_dest_id'] = False
        return super(PurchaseOrderLine, self).copy_data(cr, uid, id_, default, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
