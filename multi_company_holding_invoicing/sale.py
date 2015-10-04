# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2015 AKRETION (<http://www.akretion.com>).
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

from openerp import models, fields, api
from openerp.exceptions import Warning as UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    holding_company_id = fields.Many2one(
        'res.company',
        related='section_id.holding_company_id',
        string='Holding Company for Invoicing',
        readonly=True)

    #TODO rethink
    holding_invoice_id = fields.Many2one(
        'account.invoice',
        string='Holding Invoice',
        readonly=True)

    holding_invoice_state = fields.Selection([
        ('invoiced', 'Invoiced'),
        ('2binvoiced', 'To Be Invoiced'),
        ('none', 'Not Applicable')
        ], string='Holding Invoice Control',
        compute='_get_holding_invoice_state',
        store=True)

    holding_company_id = fields.Many2one(
        'res.company',
        related='section_id.holding_company_id',
        string='Holding Company for Invoicing',
        readonly=True)

    @api.one
    @api.depends('state', 'holding_invoice_id')
    def _get_holding_invoice_state(self):
        for sale in self:
            if sale.holding_invoice_id:
                sale.holding_invoice_state = 'invoiced'
            elif sale.state == 'done':
                sale.holding_invoice_state = '2binvoiced'
            else:
                sale.holding_invoice_state = 'none'

    @api.onchange('section_id', 'holding_company_id')
    def onchange_section_id(self):
        if self.section_id and self.holding_company_id:
            self.order_policy = 'manual'

    @api.multi
    def _prepare_invoice_line(self):
        self.ensure_one()
        return {
            'description': self.name,
            'price_unit': self.amount_untaxed,
            'quantity': 1,
            }

    @api.multi
    def _prepare_invoice(self):
        partner_invoice = None
        for sale in self:
            print sale.name
            print sale.company_id.name
            print sale.partner_invoice_id.name

            if not partner_invoice:
                partner_invoice = sale.partner_invoice_id
            elif partner_invoice != sale.partner_invoice_id:
                raise UserError(
                    _('Error'),
                    _('Invoice partner must be the same'))
        return {
            'partner_id': partner_invoice.id,
        }

    @api.model
    def _get_holding_invoice_domain(self, domain, company):
        new_domain = domain[:] if domain is not None else []
        new_domain.extend([
            ('holding_company_id', '=', company.id),
            ('company_id', '!=', company.id),
            ('holding_invoice_state', '=', '2binvoiced'),
        ])
        return new_domain

    @api.multi
    def _scheduler_action_holding_invoice_create(self, domain=None):
        companies = self.env['res.company'].search([])
        for company in companies:
            new_domain = self._get_holding_invoice_domain(domain, company)
            sales = self.search(new_domain)
            if sales:
                sales.with_context(force_company=company.id)\
                    .action_holding_invoice()

    @api.multi
    def action_holding_invoice(self):
        invoice_vals = self._prepare_invoice()
        lines = []
        for sale in self:
            lines.append(sale._prepare_invoice_line())
        invoice_vals['invoice_line'] = [(6, 0, lines)]
        invoice = self.env['account.invoice'].create(invoice_vals)
        self.write({'holding_invoice_id': invoice.id})
        return True

    @api.multi
    def write(self, values):
        section_id = values.get('section_id', False)
        if section_id:
            section = self.env['crm.case.section'].browse(section_id)
            if section.holding_company_id:
                values.update({'order_policy': 'manual'})
        return super(SaleOrder, self).write(values)

    @api.model
    def create(self, values):
        section_id = values.get('section_id', False)
        if section_id:
            section = self.env['crm.case.section'].browse(section_id)
            if section.holding_company_id:
                values.update({'order_policy': 'manual'})
        return super(SaleOrder, self).create(values)
