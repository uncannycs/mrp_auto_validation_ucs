# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def action_open_auto_confirm_wizard(self):
        """ Opens the Auto Process Order wizard for selected Manufacturing Orders """
        non_draft = self.filtered(lambda p: p.state != 'draft')
        if non_draft:
            raise UserError(_("Only Manufacturing Orders in 'Draft' state can be auto-processed.\nSelected order(s) not in draft: %s") % ', '.join(non_draft.mapped('name')))

        return {
            'name': _('Auto Process Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.auto.validation.ucs',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': self.ids,
                'active_id': self.id if len(self) == 1 else False,
            }
        }
