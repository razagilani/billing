Ext.define('ReeBill.controller.TabPanel', {
    extend: 'Ext.app.Controller',

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
        ref: 'rateStructuresTab',
        selector: 'panel[name=rateStructuresTab]'
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
    }],
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=accountsGrid]': {
                selectionchange: this.setTabs
            },
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.setTabs
            },
            'grid[id=reebillsGrid]': {
                selectionchange: this.setTabs
            }
        });

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
        this.getRateStructuresTab().setDisabled(!utilityBillSelections || !utilityBillSelections.length);

        this.getReebillChargesTab().setDisabled(!reebillSelections || !reebillSelections.length);
    }

});
