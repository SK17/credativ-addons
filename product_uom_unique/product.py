# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 credativ Ltd (<http://credativ.co.uk>).
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

class product_product(osv.osv):
    _inherit = 'product.product'

    _columns = {
                'uom_ids': fields.many2many('product.uom', 'product_uom_rel', 'uom_id', 'product_id', 'Units of Measure'),
    }

product_product()

class product_uom(osv.osv):
    _inherit = 'product.uom'

    _columns = {
                'product_ids': fields.many2many('product.product', 'product_uom_rel', 'product_id', 'uom_id', "Products"),
    }

product_uom()
