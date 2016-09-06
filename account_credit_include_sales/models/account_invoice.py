# -*- encoding: utf-8 -*-

from openerp import models, fields


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    sale_ids = fields.Many2many('sale.order', 'sale_order_invoice_rel', 'invoice_id', 'order_id', 'Sale orders', readonly=True, copy=False, help="This is the list of sale orders that have generated this invoice. The same sales order may have been invoiced in several times (by line for example).")
