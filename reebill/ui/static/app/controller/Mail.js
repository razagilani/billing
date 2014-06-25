Ext.define('ReeBill.controller.Mail', {
    extend: 'Ext.app.Controller',

    stores: [
        'Reebills'
    ],
    
    refs: [{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    }],    
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=mailGrid]': {
                activate: this.handleActivate
            }
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();

        if (!selectedAccount.length)
            return;

        this.getReebillsStore().load({
            params: {
                account: selectedAccount[0].get('account')
            }
        });
    }

});
