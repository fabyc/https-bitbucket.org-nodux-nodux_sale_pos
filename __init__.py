# This file is part of the sale_payment module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .sale import *
from .product import *
from .shop import *

def register():
    Pool.register(
        Sale,
        SaleLine,
        Product,
        SaleShop,
        module='nodux_sale_pos', type_='model')
    Pool.register(
        SaleReportTicket,
        module='nodux_sale_pos', type_='report')
