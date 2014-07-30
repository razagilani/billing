Ext.define('ReeBill.controller.ReebillCharges', {
    extend: 'Ext.app.Controller',

    stores: [
        'ReebillCharges'
    ],
    
    refs: [{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'reebillChargesTab',
        selector: 'panel[name=reebillChargesTab]'
    },{
        ref: 'reebillsGrid',
        selector: 'grid[id=reebillsGrid]'
    }],    

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'panel[name=reebillChargesTab]': {
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
        console.log('activated', selectedReebill);
        if (!selectedReebill.length)
            return;

        store.getProxy().setExtraParam('reebill_id', selectedReebill[0].get('id'));
        store.reload();
    }

});
