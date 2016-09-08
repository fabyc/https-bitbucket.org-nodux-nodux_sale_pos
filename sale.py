# This file is part of the sale_payment module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
#! -*- coding: utf8 -*-
from decimal import Decimal
from trytond.model import ModelView, fields, ModelSQL, Workflow
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval, Not, If, PYSONEncoder, Id
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button, StateAction
from trytond import backend
from datetime import datetime,timedelta
from dateutil.relativedelta import relativedelta
from itertools import groupby, chain
from functools import partial
from trytond.transaction import Transaction
from trytond.report import Report
import pytz

__all__ = ['Sale', 'SaleLine', 'SaleReportTicket']

__metaclass__ = PoolMeta
_ZERO = Decimal('0.0')
PRODUCT_TYPES = ['goods']


tipoPago = {
    '': '',
    'efectivo': 'Efectivo',
    'tarjeta': 'Tarjeta de Credito',
    'deposito': 'Deposito',
    'cheque': 'Cheque',
}

class Sale():
    __name__ = 'sale.sale'

    subtotal_0 = fields.Function(fields.Numeric('Subtotal 0%',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    subtotal_0_cache = fields.Numeric('Subtotal 0% Cache',
        digits=(16, Eval('currency_digits', 6)),
        readonly=True,
        depends=['currency_digits'])

    subtotal_12 = fields.Function(fields.Numeric('Subtotal 12%',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    subtotal_12_cache = fields.Numeric('Subtotal 12% Cache',
        digits=(16, Eval('currency_digits', 6)),
        readonly=True,
        depends=['currency_digits'])

    subtotal_14 = fields.Function(fields.Numeric('Subtotal 14%',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    subtotal_14_cache = fields.Numeric('Subtotal 14% Cache',
        digits=(16, Eval('currency_digits', 6)),
        readonly=True,
        depends=['currency_digits'])

    descuento = fields.Function(fields.Numeric('Descuento',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_descuento')

    #imprimir sin precio unitario componentes de computadora
    imprimir = fields.Boolean('Imprimir sin precio unitario', help='Imprimir'
                'cotizacion sin desglose de precio unitario', states={
                'invisible' : Eval('state') != 'quotation',
                })

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()

        cls._buttons.update({
                'wizard_sale_payment': {
                    'invisible': Eval('invoice_state') != 'none'
                    },
                'wizard_add_product': {
                    'invisible': Eval('invoice_state') != 'none'
                    },
                })
        del cls.party.states['readonly']
        del cls.price_list.states['readonly']
        cls.party.states['readonly'] = Eval('invoice_state') != 'none'
        cls.price_list.states['readonly'] = Eval('invoice_state') != 'none'
        cls.acumulativo.states['readonly'] |= Eval('invoice_state') != 'none'

    @classmethod
    def get_descuento(cls, sales, names):
        descuento = {}
        descuento_total = Decimal(0.00)
        descuento_parcial = Decimal(0.00)
        for sale in sales:
            if sale.lines:
                for line in sale.lines:
                    if line.product:
                        descuento_parcial = Decimal(line.product.template.list_price - line.unit_price)
                        if descuento_parcial > 0:
                            descuento_total += descuento_parcial
                        else:
                            descuento_total = Decimal(0.00)
            descuento[sale.id] = descuento_total
        result = {
            'descuento': descuento,
            }
        for key in result.keys():
            if key not in names:
                del result[key]
        return result

    @staticmethod
    def default_sale_date():
        Date = Pool().get('ir.date')
        date = Date.today()
        return date

    @fields.depends('payment_term', 'party')
    def on_change_payment_term(self):
        pool = Pool()
        res= {}
        termino = self.payment_term
        if self.payment_term:
            if self.party:
                if self.party.vat_number == '9999999999999':
                    TermLines = pool.get('account.invoice.payment_term.line')
                    Term = pool.get('account.invoice.payment_term')
                    term = Term.search([('id', '!=', None)])
                    for t in term:
                        cont = 0
                        termlines = TermLines.search([('payment', '=', t.id)])
                        for tl in termlines:
                            t_f = tl
                            cont += 1
                        if cont == 1 and t_f.days == 0:
                            termino = t
                            break
                if termino:
                    res['payment_term'] = termino.id
                else:
                    res['payment_term'] = None
        else:
            res['payment_term'] = None
        return res

    @fields.depends('lines', 'currency', 'party')
    def on_change_lines(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')
        Configuration = pool.get('account.configuration')
        sub14 = Decimal(0.0)
        sub12 = Decimal(0.0)
        sub0= Decimal(0.0)
        total_new = Decimal(0.0)
        config = Configuration(1)
        descuento_total = Decimal(0.0)
        descuento_parcial = Decimal(0.0)

        changes = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
            'subtotal_12': Decimal('0.0'),
            'subtotal_14': Decimal('0.0'),
            'subtotal_0': Decimal('0.0'),
            'descuento':Decimal('0.0')
            }

        if self.lines:
            context = self.get_tax_context()
            taxes = {}
            for line in self.lines:
                if  line.taxes:
                    for t in line.taxes:
                        if str('{:.0f}'.format(t.rate*100)) == '12':
                            sub12= sub12 + (line.amount)
                        elif str('{:.0f}'.format(t.rate*100)) == '0':
                            sub0 = sub0 + (line.amount)
                        elif str('{:.0f}'.format(t.rate*100)) == '14':
                            sub14 = sub14 + (line.amount)
                total_new += line.amount_w_tax

                if line.product:
                    descuento_parcial = Decimal(line.product.template.list_price - line.unit_price)
                    if descuento_parcial > 0:
                        descuento_total += descuento_parcial
                    else:
                        descuento_total = Decimal(0.00)

                changes['subtotal_14'] = sub14
                changes['subtotal_12'] = sub12
                changes['subtotal_0'] = sub0
                changes['descuento'] = descuento_total

            if self.currency:
                total_new = self.currency.round(total_new)

            def round_taxes():
                if self.currency:
                    for key, value in taxes.iteritems():
                        taxes[key] = self.currency.round(value)

            for line in self.lines:
                if getattr(line, 'type', 'line') != 'line':
                    continue
                changes['untaxed_amount'] += (getattr(line, 'amount', None)
                    or Decimal(0))

                with Transaction().set_context(context):
                    tax_list = Tax.compute(getattr(line, 'taxes', []),
                        getattr(line, 'unit_price', None) or Decimal('0.0'),
                        getattr(line, 'quantity', None) or 0.0)
                for tax in tax_list:
                    key, val = Invoice._compute_tax(tax, 'out_invoice')
                    if key not in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
                if config.tax_rounding == 'line':
                    round_taxes()
            if config.tax_rounding == 'document':
                round_taxes()
            changes['tax_amount'] = sum(taxes.itervalues(), Decimal('0.0'))
        if self.currency:
            changes['untaxed_amount'] = self.currency.round(
                changes['untaxed_amount'])
            changes['tax_amount'] = self.currency.round(changes['tax_amount'])
        changes['total_amount'] = (changes['untaxed_amount']
            + changes['tax_amount'])
        if self.currency:
            changes['total_amount'] = self.currency.round(
                changes['total_amount'])
        if total_new == changes['total_amount']:
            pass
        else:
            changes['total_amount'] = total_new
            changes['untaxed_amount'] = (changes['total_amount']
                - changes['tax_amount'])
        return changes

    @classmethod
    def get_amount(cls, sales, names):
        untaxed_amount = {}
        tax_amount = {}
        total_amount = {}
        sub14 = Decimal(0.0)
        sub12 = Decimal(0.0)
        sub0= Decimal(0.0)
        subtotal_14 = {}
        subtotal_12 = {}
        subtotal_0 = {}
        descuento_desglose = Decimal(0.0)
        discount = Decimal(0.0)

        if {'tax_amount', 'total_amount'} & set(names):
            compute_taxes = True
        else:
            compute_taxes = False
        # Sort cached first and re-instanciate to optimize cache management
        sales = sorted(sales, key=lambda s: s.state in cls._states_cached,
            reverse=True)
        sales = cls.browse(sales)
        for sale in sales:
            module = None
            for line in sale.lines:
                pool = Pool()

                Module = pool.get('ir.module.module')
                module = Module.search([('name', '=', 'sale_discount'), ('state', '=', 'installed')])

                if module:
                    if (line.descuento_desglose > Decimal(0.0)) | (line.discount > Decimal(0.0)):
                        descuento_desglose = line.descuento_desglose
                        discount = line.discount
                        if  line.taxes:
                            for t in line.taxes:
                                if str('{:.0f}'.format(t.rate*100)) == '12':
                                    sub12= sub12 + (line.amount)
                                elif str('{:.0f}'.format(t.rate*100)) == '14':
                                    sub14 = sub14 + (line.amount)
                                elif str('{:.0f}'.format(t.rate*100)) == '0':
                                    sub0 = sub0 + (line.amount)
                    else:
                        if  line.taxes:
                            for t in line.taxes:
                                if str('{:.0f}'.format(t.rate*100)) == '12':
                                    sub12= sub12 + (line.gross_unit_price * Decimal(line.quantity))
                                elif str('{:.0f}'.format(t.rate*100)) == '14':
                                    sub14 = sub14 + (line.gross_unit_price * Decimal(line.quantity))
                                elif str('{:.0f}'.format(t.rate*100)) == '0':
                                    sub0 = sub0 + (line.gross_unit_price * Decimal(line.quantity))
                else:
                    if  line.taxes:
                        for t in line.taxes:
                            if str('{:.0f}'.format(t.rate*100)) == '12':
                                sub12= sub12 + (line.amount)
                            elif str('{:.0f}'.format(t.rate*100)) == '14':
                                sub14 = sub14 + (line.amount)
                            elif str('{:.0f}'.format(t.rate*100)) == '0':
                                sub0 = sub0 + (line.amount)


            if (sale.state in cls._states_cached
                    and sale.untaxed_amount_cache is not None
                    and sale.tax_amount_cache is not None
                    and sale.total_amount_cache is not None
                    and sale.subtotal_0_cache is not None
                    and sale.subtotal_12_cache is not None
                    and sale.subtotal_14_cache is not None):
                untaxed_amount[sale.id] = sale.untaxed_amount_cache
                subtotal_0[sale.id] = sale.subtotal_0_cache
                subtotal_12[sale.id] = sale.subtotal_12_cache
                subtotal_14[sale.id] = sale.subtotal_14_cache
                if compute_taxes:
                    tax_amount[sale.id] = sale.tax_amount_cache
                    total_amount[sale.id] = sale.total_amount_cache
            else:
                if module:
                    if (descuento_desglose > Decimal(0.0)) | (discount > Decimal(0.0)):
                        untaxed_amount[sale.id] = sale.currency.round(sum(
                            ((line.amount) for line in sale.lines
                                if line.type == 'line'), _ZERO))
                    else:
                        untaxed_amount[sale.id] = sale.currency.round(sum(
                            ((line.gross_unit_price * Decimal(line.quantity)) for line in sale.lines
                                if line.type == 'line'), _ZERO))
                else:
                    untaxed_amount[sale.id] = sale.currency.round(sum(
                        ((line.amount) for line in sale.lines
                            if line.type == 'line'), _ZERO))

                subtotal_0[sale.id] = sale.currency.round(sub0)
                subtotal_12[sale.id] = sale.currency.round(sub12)
                subtotal_14[sale.id] = sale.currency.round(sub14)
                if compute_taxes:
                    tax_amount[sale.id] = sale.get_tax_amount()
                    total_amount[sale.id] = (
                        untaxed_amount[sale.id] + tax_amount[sale.id])
        result = {
            'untaxed_amount': untaxed_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'subtotal_0': subtotal_0,
            'subtotal_12': subtotal_12,
            'subtotal_14':subtotal_14,
            }
        for key in result.keys():
            if key not in names:
                del result[key]
        return result

    @classmethod
    def store_cache(cls, sales):
        for sale in sales:
            cls.write([sale], {
                    'untaxed_amount_cache': sale.untaxed_amount,
                    'tax_amount_cache': sale.tax_amount,
                    'total_amount_cache': sale.total_amount,
                    'subtotal_14_cache': sale.subtotal_14,
                    'subtotal_12_cache': sale.subtotal_12,
                    'subtotal_0_cache': sale.subtotal_0,

                    })

class SaleReportTicket(Report):
    __name__ = 'sale_pos.sale_pos_ticket'

    @classmethod
    def parse(cls, report, records, data, localcontext):
        User = Pool().get('res.user')
        user = User(Transaction().user)
        sale = records[0]
        Sale = Pool().get('sale.sale')
        fecha_p = None

        localcontext['fecha'] = cls._get_fecha(Sale, sale)
        localcontext['timedelta'] = timedelta
        return super(SaleReportTicket, cls).parse(report, records, data,
                localcontext=localcontext)

    @classmethod
    def _get_fecha(cls, Sale, sale):
        if sale.company.timezone:
            timezone = pytz.timezone(sale.company.timezone)
            dt = sale.create_date
            fecha = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)

        return fecha

class SaleLine(ModelSQL, ModelView):
    'Sale Line'
    __name__ = 'sale.line'
    _rec_name = 'description'

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()

    @staticmethod
    def default_quantity():
        return 1

    @staticmethod
    def default_gross_unit_price():
        return Decimal(0.0)

    @fields.depends('product', 'unit', 'quantity', 'description',
        '_parent_sale.party', '_parent_sale.currency',
        '_parent_sale.sale_date')
    def on_change_product(self):
        Product = Pool().get('product.product')

        if not self.product:
            return {}
        res = {}

        party = None
        party_context = {}
        if self.sale and self.sale.party:
            party = self.sale.party
            if party.lang:
                party_context['language'] = party.lang.code

        category = self.product.sale_uom.category
        if not self.unit or self.unit not in category.uoms:
            res['unit'] = self.product.sale_uom.id
            self.unit = self.product.sale_uom
            res['unit.rec_name'] = self.product.sale_uom.rec_name
            res['unit_digits'] = self.product.sale_uom.digits

        with Transaction().set_context(self._get_context_sale_price()):
            res['unit_price'] = Product.get_sale_price([self.product],
                    self.quantity or 0)[self.product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])
        res['taxes'] = []
        pattern = self._get_tax_rule_pattern()
        for tax in self.product.customer_taxes_used:
            if party and party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(tax, pattern)
                if tax_ids:
                    res['taxes'].extend(tax_ids)
                continue
            res['taxes'].append(tax.id)
        if party and party.customer_tax_rule:
            tax_ids = party.customer_tax_rule.apply(None, pattern)
            if tax_ids:
                res['taxes'].extend(tax_ids)

        with Transaction().set_context(party_context):
            res['description'] = Product(self.product.id).name

        self.unit_price = res['unit_price']
        self.type = 'line'
        res['amount'] = self.on_change_with_amount()
        return res
