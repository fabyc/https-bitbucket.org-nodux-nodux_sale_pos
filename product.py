#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend
from trytond.const import OPERATORS
from trytond.pool import PoolMeta

__all__ = ['Product']
__metaclass__ = PoolMeta

class Product():
    "Product Variant"
    __name__ = "product.product"

    def get_rec_name(self, name):
        print "transaction", Transaction().context
        Shop = Pool().get('sale.shop')
        shop = Shop(Transaction().context.get('shop'))
        warehouse = shop.no_warehouse
        Location = Pool().get('stock.location')
        locations = Location.search([('type','=', 'warehouse')])
        grouping=('product',)
        warehouses = ""
        qty = 0
        i = 0
        if warehouse == 0:
            if self.code:
                return '[' + self.code + '] ' + self.name
            else:
                return self.name

        elif warehouse == None:
            for l in locations:
                location_ids = [l.id]
                cantidad = self.products_by_location(location_ids=location_ids,
                    product_ids=[self.id], with_childs=True,
                    grouping=grouping)
                for clave, valor in cantidad.iteritems():
                    qty = (str(valor).split("."))[0]
                warehouses += l.name+ ':'+ str(qty)

            if self.code:
                return '[' + self.code + '] ' + self.name + ' (Precio:'+str(self.list_price)+' - '+warehouses+')'
            else:
                return self.name

        elif warehouse > 0 :
            if i < warehouse:
                location = locations[i]
                location_ids = [location.id]
                cantidad = self.products_by_location(location_ids=location_ids,
                    product_ids=[self.id], with_childs=True,
                    grouping=grouping)
                for clave, valor in cantidad.iteritems():
                    qty = (str(valor).split("."))[0]
                warehouses += location.name+ ':'+ str(qty)
                i += 1
            if self.code:
                return '[' + self.code + '] ' + self.name + ' (Precio:'+str(self.list_price)+' - '+warehouses+')'
            else:
                return self.name
