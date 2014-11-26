Ext.define('ReeBill.controller.TabPanel', {
    extend: 'Ext.app.Controller',

    stores: [
        'IssuableReebills',
    ],

    views: [
        'issuablereebills.IssuableReebills',
        'accounts.Accounts',
        'reebills.Reebills',
        'utilitybills.UtilityBills',
        'payments.Payments',
        'charges.Charges',
        'reebillcharges.ReebillCharges',
        'metersandregisters.UtilityBillRegisters'
    ],

    refs: [{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'utilityBillsTab',
        selector: 'panel[name=utilityBillsTab]'
    },{
        ref: 'reebillsTab',
        selector: 'panel[name=reebillsTab]'
    },{
        ref: 'metersTab',
        selector: 'panel[name=metersTab]'
    },{
        ref: 'chargesTab',
        selector: 'panel[name=chargesTab]'
    },{
        ref: 'chargesTab',
        selector: 'panel[name=chargesTab]'
    },{
        ref: 'paymentsGrid',
        selector: 'grid[id=paymentsGrid]'
    },{
        ref: 'reebillsGrid',
        selector: 'grid[id=reebillsGrid]'
    },{
        ref: 'reebillChargesTab',
        selector: 'panel[name=reebillChargesTab]'
    },{
        ref: 'issuableReebills',
        selector: 'panel[id=issuableReebillsGrid]'
    }],
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=accountsGrid]': {
                selectionchange: function(){
                    this.handleAccountSelect();
                    this.setTabs();
                }
            },
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.setTabs
            },
            'grid[id=reebillsGrid]': {
                selectionchange: this.setTabs
            }
        });

    },

    handleAccountSelect: function(){
        this.getUtilityBillsGrid().getSelectionModel().deselectAll();
    },

    /**
     * Handle the tab panel changes. 
     */
    setTabs: function() {
        var accountSelections = this.getAccountsGrid().getSelectionModel().getSelection();
        var utilityBillSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection();
        var reebillSelections = this.getReebillsGrid().getSelectionModel().getSelection();

        this.getUtilityBillsTab().setDisabled(!accountSelections || !accountSelections.length);
        this.getReebillsTab().setDisabled(!accountSelections || !accountSelections.length);
        this.getPaymentsGrid().setDisabled(!accountSelections || !accountSelections.length);

        this.getMetersTab().setDisabled(!utilityBillSelections || !utilityBillSelections.length);
        this.getChargesTab().setDisabled(!utilityBillSelections || !utilityBillSelections.length);

        this.getReebillChargesTab().setDisabled(!reebillSelections || !reebillSelections.length);
    }

});
