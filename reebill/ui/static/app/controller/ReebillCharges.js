Ext.define('ReeBill.controller.ReebillCharges', {
    extend: 'Ext.app.Controller',

    stores: [
        'ReebillCharges'
    ],
    
    refs: [{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'reebillChargesGrid',
        selector: 'grid[id=reebillChargesGrid]'
    },{
        ref: 'reebillsGrid',
        selector: 'grid[id=reebillsGrid]'
    }],    

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=reebillChargesGrid]': {
                activate: this.handleActivate
            }
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedReebill = this.getReebillsGrid().getSelectionModel().getSelection(),
            store = this.getReebillChargesStore();

        if (!selectedReebill.length)
            return;

        store.getProxy().setExtraParam('reebill_id', selectedReebill[0].get('id'));
        store.reload();
    }

});
