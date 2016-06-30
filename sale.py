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
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'

    subtotal_0 = fields.Function(fields.Numeric('Subtotal 0%',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    subtotal_0_cache = fields.Numeric('Subtotal 0% Cache',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])

    subtotal_12 = fields.Function(fields.Numeric('Subtotal 12%',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    subtotal_12_cache = fields.Numeric('Subtotal 12% Cache',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])

    subtotal_14 = fields.Function(fields.Numeric('Subtotal 14%',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    subtotal_14_cache = fields.Numeric('Subtotal 14% Cache',
        digits=(16, Eval('currency_digits', 2)),
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
        termino = self.payment_term
        if self.payment_term:
            if self.party:
                if self.party.vat_code == '9999999999999':
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
                    self.payment_term = termino.id
                else:
                    self.payment_term = None
        else:
            self.payment_term = None

    @fields.depends('lines', 'currency', 'party', 'self_pick_up')
    def on_change_lines(self):
        sub14 = Decimal(0.0)
        sub12 = Decimal(0.0)
        sub0= Decimal(0.0)
        descuento_total = Decimal(0.0)
        descuento_parcial = Decimal(0.0)

        if not self.self_pick_up:
            super(Sale, self).on_change_lines()

        self.untaxed_amount= Decimal('0.0')
        self.tax_amount = Decimal('0.0')
        self.total_amount = Decimal('0.0')
        self.subtotal_12= Decimal('0.0')
        self.subtotal_14= Decimal('0.0')
        self.subtotal_0= Decimal('0.0')
        self.descuento = Decimal('0.0')

        if self.lines:
            for line in self.lines:
                if  line.taxes:
                    for t in line.taxes:
                        if str('{:.0f}'.format(t.rate*100)) == '12':
                            sub12= sub12 + (line.amount)
                        elif str('{:.0f}'.format(t.rate*100)) == '0':
                            sub0 = sub0 + (line.amount)
                        elif str('{:.0f}'.format(t.rate*100)) == '14':
                            sub14 = sub14 + (line.amount)

                if line.product:
                    descuento_parcial = Decimal(line.product.template.list_price - line.unit_price)
                    if descuento_parcial > 0:
                        descuento_total += descuento_parcial
                    else:
                        descuento_total = Decimal(0.00)

                self.subtotal_14 = sub14
                self.subtotal_12 = sub12
                self.subtotal_0 = sub0
                self.descuento = descuento_total

            self.untaxed_amount = reduce(lambda x, y: x + y,
                [(getattr(l, 'amount', None) or Decimal(0))
                    for l in self.lines if l.type == 'line'], Decimal(0)
                )
            self.total_amount = reduce(lambda x, y: x + y,
                [(getattr(l, 'amount_w_tax', None) or Decimal(0))
                    for l in self.lines if l.type == 'line'], Decimal(0)
                )
        if self.currency:
            self.untaxed_amount = self.currency.round(self.untaxed_amount)
            self.total_amount = self.currency.round(self.total_amount)
        self.tax_amount = self.total_amount - self.untaxed_amount
        if self.currency:
            self.tax_amount = self.currency.round(self.tax_amount)

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

        if {'tax_amount', 'total_amount'} & set(names):
            compute_taxes = True
        else:
            compute_taxes = False
        # Sort cached first and re-instanciate to optimize cache management
        sales = sorted(sales, key=lambda s: s.state in cls._states_cached,
            reverse=True)
        sales = cls.browse(sales)
        for sale in sales:

            for line in sale.lines:
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
                untaxed_amount[sale.id] = sum(
                    (line.amount for line in sale.lines
                        if line.type == 'line'), _ZERO)
                subtotal_0[sale.id] = sub0
                subtotal_12[sale.id] = sub12
                subtotal_14[sale.id] = sub14
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
    __metaclass__ = PoolMeta
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
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'
    _rec_name = 'description'

    @staticmethod
    def default_quantity():
        return 1
