#This file is part sale_shop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['SaleShop']
__metaclass__ = PoolMeta

class SaleShop:
    __name__ = 'sale.shop'
    no_warehouse = fields.Integer('No. warehouse',
        help='Numero de bodegas que se mostraran en la busqueda:'
            '\nVacio: Mostrar todas las bodegas'
            '\n0: No muestra bodegas en busqueda de productos'
            '\nNumero: Muestra el total de bodegas que se indique (ej. 1)')


    @staticmethod
    def default_no_warehouse():
        return 0
