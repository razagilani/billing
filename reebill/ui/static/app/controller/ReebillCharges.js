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
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();

        if (!selectedReebill.length || !selectedAccount.length)
            return;

        this.getReebillChargesStore().load({
            params: {
                account: selectedAccount[0].get('account'),
                service: selectedReebill[0].get('services')[0],
                sequence: selectedReebill[0].get('sequence')
            }
        });
    }

});
