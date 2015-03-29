from openerp.osv import osv, fields
from openerp.tools.translate import _

class StockPicking(osv.osv):
    _inherit = 'stock.picking'

    def button_unlink(self, cr, uid, ids, context=None):
	self.action_unlink(cr, uid, ids)
	
	return True


    def action_unlink(self, cr, uid, ids, context=None):
	self.action_cancel(cr, uid, ids, context=context)
	pack_obj = self.pool.get('stock.pack.operation')
	for pick in self.browse(cr, uid, ids):
	    #Delete the pack operations
	    #TODO: See if there is some status or other related object to consider
	    if pick.pack_operation_ids:
		pack_obj.unlink(cr, uid, [pack.id for pack in pick.pack_operation_ids])

	    #Something to do here?
	    if pick.sale and not pick.backorder_id and pick.sale.state not in ['cancel']:
		self.pool.get('sale.order').write(cr, uid, pick.sale.id, {'state': 'shipping_except'})

	self.unlink(cr, uid, ids)	    
        return True


class StockMove(osv.osv):
    _inherit = 'stock.move'


    def action_cancel(self, cr, uid, ids, context=None):
        """ Cancels the moves and if all moves are cancelled it cancels the picking.
        @return: True
        """
        procurement_obj = self.pool.get('procurement.order')
        context = context or {}
        procs_to_check = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done':
		#TODO: Add some condition that if period closed, etc that move cannot be canceled.
		#If the move is done, unlink the quants to reverse the inventory moves
		quant_obj = self.pool.get('stock.quant')
		quant_obj.unlink(cr, uid, [quant.id for quant in move.quant_ids])
 #               raise osv.except_osv(_('Operation Forbidden!'),
  #                      _('You cannot cancel a stock move that has been set to \'Done\'.'))
            if move.reserved_quant_ids:
                self.pool.get("stock.quant").quants_unreserve(cr, uid, move, context=context)
            if context.get('cancel_procurement'):
                if move.propagate:
                    procurement_ids = procurement_obj.search(cr, uid, [('move_dest_id', '=', move.id)], context=context)
                    procurement_obj.cancel(cr, uid, procurement_ids, context=context)
            else:
                if move.move_dest_id:
                    if move.propagate:
                        self.action_cancel(cr, uid, [move.move_dest_id.id], context=context)
                    elif move.move_dest_id.state == 'waiting':
                        #If waiting, the chain will be broken and we are not sure if we can still wait for it (=> could take from stock instead)
                        self.write(cr, uid, [move.move_dest_id.id], {'state': 'confirmed'}, context=context)
                if move.procurement_id:
                    # Does the same as procurement check, only eliminating a refresh
                    procs_to_check.append(move.procurement_id.id)
                    
        res = self.write(cr, uid, ids, {'state': 'cancel', 'move_dest_id': False}, context=context)
        if procs_to_check:
            procurement_obj.check(cr, uid, procs_to_check, context=context)
        return res
