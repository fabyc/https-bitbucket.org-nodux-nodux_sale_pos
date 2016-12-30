#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend
from trytond.const import OPERATORS
from trytond.pool import PoolMeta
from decimal import Decimal

__all__ = ['Template','Product']
__metaclass__ = PoolMeta

class Template():
    "Product Template"
    __name__ = "product.template"

    permission = fields.Function(fields.Char('State Permission',
            readonly=True), 'get_permission')

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls.cost_price.states['invisible'] = (Eval('permission') == 'no_permission')
        cls.cost_price_with_tax.states['invisible'] = (Eval('permission') == 'no_permission')

    @classmethod
    def get_permission(cls, products, names):

        origin = Transaction()

        def in_group():
            pool = Pool()
            ModelData = pool.get('ir.model.data')
            User = pool.get('res.user')
            Group = pool.get('res.group')

            group = Group(ModelData.get_id('nodux_sale_pos',
                            'group_cost_price'))

            transaction = Transaction()
            user_id = transaction.user
            if user_id == 0:
                user_id = transaction.context.get('user', user_id)
            if user_id == 0:
                return True
            user = User(user_id)

            return origin and group in user.groups

        if not in_group():
            result = {n: {p.id: Decimal(0) for p in products} for n in names}
            for name in names:
                for product in products:
                    result[name][product.id] = 'no_permission'
            return result

        result = {n: {p.id: Decimal(0) for p in products} for n in names}
        for name in names:
            for product in products:
                result[name][product.id] = 'permission'

        return result

class Product():
    "Product Variant"
    __name__ = "product.product"

    def get_rec_name(self, name):
        Shop = Pool().get('sale.shop')
        shop = Shop(Transaction().context.get('shop'))

        if self.code:
            return '[' + self.code + '] ' + self.name
        else:
            return self.name
        """
        if shop.id:
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
        else:
            return self.name
        """
