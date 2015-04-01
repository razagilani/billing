Ext.define('BillEntry.controller.Charges', {
    extend: 'Ext.app.Controller',

    stores: [
        'Charges', 'UtilityBills'
    ],
    
    views:[
        'charges.Charges'
    ],

    refs: [{
        ref: 'chargesGrid',
        selector: 'grid[id=chargesGrid]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'removeCharge',
        selector: '[action=removeCharge]'
    },{
        ref: 'newCharge',
        selector: '[action=newCharge]'
    }],

    init: function() {
        this.getChargesStore().on({
        write: this.updateUtilBillCharges,
        //update: this.updateUtilBillCharges,
        scope: this
        });


        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.handleUtilBillRowSelect
            },
            '[action=newCharge]': {
                click: this.handleNew
            },
            '[action=removeCharge]': {
                click: this.handleDelete
            }
        });

    },

    /**
     * Handle row selection in utility bills grid
     */
    handleUtilBillRowSelect: function() {
        var processed = false;
        var selections = this.getUtilityBillsGrid().getSelectionModel().getSelection();
        if (selections.length > 0){
            processed = selections[0].get('processed');
        }
        this.getRemoveCharge().setDisabled(selections.length == 0 || processed);
     },

    /**
     * Handle the new button being clicked.
     */
    handleNew: function() {
        var store = this.getChargesStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedBill || !selectedBill.length)
            return;

        store.suspendAutoSync();
        store.add({
            rsi_binding: 'New Charge',
            description: 'Enter Description',
            rate: 0,
            unit: 'dollars',
            utilbill_id: selectedBill[0].internalId
        });
        store.sync({success:function(batch){
            var record = batch.operations[0].records[0];
            var plugin = this.getChargesGrid().findPlugin('cellediting');
            plugin.startEdit(record, 0);
        }, scope: this});
        store.resumeAutoSync();

    },

    /**
     * Handle the delete button being clicked.
     */
    handleDelete: function() {
        var store = this.getChargesStore();
        var selected = this.getChargesGrid().getSelectionModel().getSelection()[0];
        store.remove(selected);
    },

    /**
     * Update the UtilBills grid charges field whenever charges
     * are added/removed from Charges grid
     */

    updateUtilBillCharges: function(charges_store)
    {
        var selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        // this is being set to 0 to trigger http PUT for supply_total
        // and the value sent is ignored by the server as it computes
        // charges by itself
        selected.set('supply_total', 0);
    }


});
