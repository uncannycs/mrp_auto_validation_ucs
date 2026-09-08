# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpAutoValidationUcs(models.TransientModel):
    _name = 'mrp.auto.validation.ucs'
    _description = 'Auto Process Manufacturing Order Wizard'

    process_type = fields.Selection([
        ('available_qty', 'Available Quantity'),
        ('forcefully_done', 'Forcefully Done')
    ], string='Process Option', default='available_qty', required=True)

    def _auto_assign_lots(self, production):
        """Helper to ensure lot/serial numbers exist for finished product if tracking is enabled."""
        if production.product_tracking in ('lot', 'serial') and not production.lot_producing_id:
            try:
                production.action_generate_serial()
            except Exception as e:
                _logger.debug("action_generate_serial failed for MO %s: %s", production.name, e)

            if not production.lot_producing_id:
                lot = False
                try:
                    lot_vals = production._prepare_stock_lot_values()
                    lot = self.env['stock.lot'].create(lot_vals)
                except Exception:
                    lot_name = self.env['stock.lot']._get_next_serial(
                        production.company_id, production.product_id
                    ) or f"AUTO-{production.product_id.id}-{production.id}"
                    lot = self.env['stock.lot'].create({
                        'product_id': production.product_id.id,
                        'company_id': production.company_id.id,
                        'name': lot_name,
                    })
                if lot:
                    production.lot_producing_id = lot.id

    def _auto_assign_component_lots(self, production):
        """Helper to auto-assign lots for tracked components if missing."""
        for move in production.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id.tracking in ('lot', 'serial')):
            qty_to_consume = move.quantity or move.product_uom_qty
            if not move.move_line_ids:
                lot = self.env['stock.lot'].search([
                    ('product_id', '=', move.product_id.id),
                    '|', ('company_id', '=', False), ('company_id', '=', production.company_id.id)
                ], limit=1)
                if not lot:
                    lot_name = self.env['stock.lot']._get_next_serial(
                        production.company_id, move.product_id
                    ) or f"AUTO-{move.product_id.id}-{production.id}"
                    lot = self.env['stock.lot'].create({
                        'product_id': move.product_id.id,
                        'company_id': production.company_id.id,
                        'name': lot_name,
                    })
                self.env['stock.move.line'].create({
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                    'quantity': qty_to_consume,
                    'lot_id': lot.id,
                    'picked': True,
                })
            else:
                for ml in move.move_line_ids:
                    if not ml.lot_id and not ml.lot_name:
                        lot = self.env['stock.lot'].search([
                            ('product_id', '=', ml.product_id.id),
                            '|', ('company_id', '=', False), ('company_id', '=', production.company_id.id)
                        ], limit=1)
                        if not lot:
                            lot_name = self.env['stock.lot']._get_next_serial(
                                production.company_id, ml.product_id
                            ) or f"AUTO-{ml.product_id.id}-{production.id}"
                            lot = self.env['stock.lot'].create({
                                'product_id': ml.product_id.id,
                                'company_id': production.company_id.id,
                                'name': lot_name,
                            })
                        ml.lot_id = lot.id
                    ml.picked = True
            move.picked = True

    def _process_single_production(self, production):
        """Process an individual Manufacturing Order to completion."""
        if self.process_type == 'available_qty':
            # Check availability / reserve component stock
            production.action_assign()

            # Check if stock is fully available for all raw components
            is_available = True
            if production.move_raw_ids:
                if hasattr(production, 'reservation_state') and production.reservation_state:
                    is_available = (production.reservation_state == 'assigned')
                else:
                    is_available = all(m.state in ('assigned', 'done') for m in production.move_raw_ids)

            if not is_available:
                # If stock is not available, order remains in confirmed state
                return

        elif self.process_type == 'forcefully_done':
            try:
                production.action_assign()
            except Exception:
                pass

        # Set produced quantity
        if production.product_tracking == 'serial':
            production.qty_producing = 1.0
        else:
            production.qty_producing = production.product_qty

        if hasattr(production, 'set_qty_producing'):
            production.set_qty_producing()
        elif hasattr(production, '_set_qty_producing'):
            production._set_qty_producing()

        # Ensure raw material move quantities and picked flags are set
        for move in production.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            if hasattr(move, 'quantity') and (not move.quantity or move.quantity < move.product_uom_qty):
                move.quantity = move.product_uom_qty
            move.picked = True

        # Auto-assign lots if tracking is enabled
        self._auto_assign_lots(production)
        self._auto_assign_component_lots(production)

        # Auto process work orders if any exist
        if hasattr(production, 'workorder_ids') and production.workorder_ids:
            for wo in production.workorder_ids.filtered(lambda w: w.state not in ('done', 'cancel')):
                if hasattr(wo, 'button_finish'):
                    wo.button_finish()
                else:
                    wo.state = 'done'

        # Mark MO as done via standard Odoo flow
        production.with_context(
            skip_consumption=True,
            skip_backorder=True,
            skip_redirection=True,
            skip_sms=True,
            skip_activity=True
        ).button_mark_done()

    def action_auto_process(self):
        active_ids = self._context.get('active_ids', [])
        productions = self.env['mrp.production'].browse(active_ids)

        if not productions:
            raise UserError(_("No Manufacturing Orders selected to process."))

        # Check if all selected orders are in draft state
        non_draft = productions.filtered(lambda p: p.state != 'draft')
        if non_draft:
            raise UserError(_("Only Manufacturing Orders in 'Draft' state can be auto-processed.\nSelected order(s) not in draft: %s") % ', '.join(non_draft.mapped('name')))

        errors = []

        for production in productions:
            try:
                # Step 1: Confirm the Manufacturing Order if in draft
                if production.state == 'draft':
                    production.action_confirm()

                # Step 2: Handle serial tracking with quantity > 1 (split into 1-unit MOs)
                if production.product_tracking == 'serial' and production.product_qty > 1:
                    sub_productions = production._split_productions({production: [1.0] * int(production.product_qty)})
                    for sub_mo in sub_productions:
                        self._process_single_production(sub_mo)
                else:
                    self._process_single_production(production)

            except Exception as e:
                _logger.exception("Error auto-processing MO %s: %s", production.name, e)
                errors.append(f"{production.name}: {str(e)}")

        if errors:
            raise UserError(_("The following error(s) occurred while processing Manufacturing Orders:\n\n%s") % '\n'.join(errors))

        return {'type': 'ir.actions.act_window_close'}
