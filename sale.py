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

__all__ = ['Sale']
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
            
    subtotal_0 = fields.Function(fields.Numeric(u'Subtotal 0%',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
            
    subtotal_12 = fields.Function(fields.Numeric(u'Subtotal 12%',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
            
    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        total_amount = cls.total_amount
        cls._buttons.update({
                'wizard_sale_payment': {
                    'invisible': Eval('invoice_state') != 'none'
                    },
                'wizard_add_product': {
                    'invisible': Eval('invoice_state') != 'none'
                    },
                })
                
        cls.payment_term.states['readonly'] |= Eval('invoice_state') != 'none'
        cls.payment_term.depends.append('invoice_state')
        cls.lines.states['readonly'] |= Eval('invoice_state') != 'none'
        cls.lines.depends.append('invoice_state')
        cls.self_pick_up.states['readonly'] |= Eval('invoice_state') != 'none'
        cls.self_pick_up.depends.append('invoice_state')
        cls.acumulativo.states['readonly'] |= Eval('invoice_state') != 'none'
        cls.sale_date.states['readonly'] |= Eval('invoice_state') != 'none'
        cls.sale_device.states['readonly'] |= Eval('invoice_state') != 'none'
        cls.party.states['readonly'] |= Eval('invoice_state') != 'none'
        cls.lines.depends.append('invoice_state')
        
    @staticmethod
    def default_sale_date():
        Date = Pool().get('ir.date')
        date = Date.today()
        print date
        return date
        
    @classmethod
    def get_amount(cls, sales, names):
        untaxed_amount = {}
        tax_amount = {}
        total_amount = {}
        pool = Pool()
        subtotal_12 = {}
        subtotal_0 = {}
        sub12= Decimal(0.0)
        sub0= Decimal(0.0)
        
        if {'tax_amount', 'total_amount'} & set(names):
            compute_taxes = True
        else:
            compute_taxes = False
        # Sort cached first and re-instanciate to optimize cache management
        sales = sorted(sales, key=lambda s: s.state in cls._states_cached,
            reverse=True)
        sales = cls.browse(sales)
        
        Taxes1 = pool.get('product.category-customer-account.tax')
        Taxes2 = pool.get('product.template-customer-account.tax')
        
        for sale in sales:
            if (sale.state in cls._states_cached
                    and sale.untaxed_amount_cache is not None
                    and sale.tax_amount_cache is not None
                    and sale.total_amount_cache is not None):
                untaxed_amount[sale.id] = sale.untaxed_amount_cache
                if compute_taxes:
                    tax_amount[sale.id] = sale.tax_amount_cache
                    total_amount[sale.id] = sale.total_amount_cache
                for line in sale.lines:
                    taxes1 = Taxes1.search([('category','=', line.product.category)])
                    taxes2 = Taxes2.search([('product','=', line.product)])
                    taxes3 = Taxes2.search([('product','=', line.product.template)])
                        
                    if taxes1:
                        for t in taxes1:
                            if str('{:.0f}'.format(t.tax.rate*100)) == '12':
                                sub12= sub12 + (line.amount)
                            elif str('{:.0f}'.format(t.tax.rate*100)) == '0':
                                sub0 = sub0 + (line.amount)
                    elif taxes2:
                        for t in taxes2:
                            if str('{:.0f}'.format(t.tax.rate*100)) == '12':
                                sub12= sub12 + (line.amount)
                            if str('{:.0f}'.format(t.tax.rate*100)) == '0':
                                sub0 = sub0 + (line.amount)
                        
                    elif taxes3:
                        for t in taxes3:
                            if str('{:.0f}'.format(t.tax.rate*100)) == '12':
                                sub12= sub12 + (line.amount)
                            if str('{:.0f}'.format(t.tax.rate*100)) == '0':
                                sub0 = sub0 + (line.amount)
                
                    subtotal_12[sale.id] = sub12
                    subtotal_0[sale.id] = sub0
            else:
                untaxed_amount[sale.id] = sum(
                    (line.amount for line in sale.lines
                        if line.type == 'line'), _ZERO)
                if compute_taxes:
                    tax_amount[sale.id] = sale.get_tax_amount()
                    total_amount[sale.id] = (
                        untaxed_amount[sale.id] + tax_amount[sale.id])
                for line in sale.lines:
                    taxes1 = Taxes1.search([('category','=', line.product.category)])
                    taxes2 = Taxes2.search([('product','=', line.product)])
                    taxes3 = Taxes2.search([('product','=', line.product.template)])
                        
                    if taxes1:
                        for t in taxes1:
                            if str('{:.0f}'.format(t.tax.rate*100)) == '12':
                                sub12= sub12 + (line.amount)
                            elif str('{:.0f}'.format(t.tax.rate*100)) == '0':
                                sub0 = sub0 + (line.amount)
                    elif taxes2:
                        for t in taxes2:
                            if str('{:.0f}'.format(t.tax.rate*100)) == '12':
                                sub12= sub12 + (line.amount)
                            if str('{:.0f}'.format(t.tax.rate*100)) == '0':
                                sub0= sub0 + (line.amount)
                        
                    elif taxes3:
                        for t in taxes3:
                            if str('{:.0f}'.format(t.tax.rate*100)) == '12':
                                sub12= sub12 + (line.amount)
                            if str('{:.0f}'.format(t.tax.rate*100)) == '0':
                                sub0= sub0 + (line.amount)
                                
                    subtotal_12[sale.id] = sub12
                    subtotal_0[sale.id] = sub0
                    
        result = {
            'untaxed_amount': untaxed_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'subtotal_0':subtotal_0,
            'subtotal_12':subtotal_12,
            }
            
        for key in result.keys():
            if key not in names:
                del result[key]
        return result
        
    @fields.depends('lines', 'currency', 'party')
    def on_change_lines(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')
        Configuration = pool.get('account.configuration')
        sub12 = Decimal(0.0)
        sub0= Decimal(0.0)
        config = Configuration(1)

        changes = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
            'subtotal_12': Decimal('0.0'),
            'subtotal_0': Decimal('0.0'),
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
                
                changes['subtotal_12'] = sub12
                changes['subtotal_0'] = sub0
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
        return changes
