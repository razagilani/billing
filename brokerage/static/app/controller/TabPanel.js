Ext.define('ReeBill.controller.TabPanel', {
    extend: 'Ext.app.Controller',

    views: [
        'accounts.Accounts',
        'utilitybills.UtilityBills',
        'charges.Charges',
        'metersandregisters.UtilityBillRegisters'
    ],

    refs: [{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'utilityBillsTab',
        selector: 'panel[name=utilityBillsTab]'
    },{
        ref: 'metersTab',
        selector: 'panel[name=metersTab]'
    },{
        ref: 'chargesTab',
        selector: 'panel[name=chargesTab]'
    }],
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=accountsGrid]': {
                selectionchange: function(){
                    this.setTabs();
                }
            },
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.setTabs
            }
        });

    },

    /**
     * Handle the tab panel changes.
     */
    setTabs: function() {
        var utilityBillSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        //this.getUtilityBillsTab().setDisabled(!accountSelections || !accountSelections.length);
        //this.getReebillsTab().setDisabled(!accountSelections || !accountSelections.length);
        //this.getPaymentsGrid().setDisabled(!accountSelections || !accountSelections.length);
        //
        //this.getMetersTab().setDisabled(!utilityBillSelections || !utilityBillSelections.length);
        //this.getChargesTab().setDisabled(!utilityBillSelections || !utilityBillSelections.length);
        //
        //this.getReebillChargesTab().setDisabled(!reebillSelections || !reebillSelections.length);
    }

});
