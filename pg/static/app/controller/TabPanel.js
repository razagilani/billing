Ext.define('ReeBill.controller.TabPanel', {
    extend: 'Ext.app.Controller',

    stores: [
        'IssuableReebills',
    ],

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
            },
            'grid[id=reebillsGrid]': {
                selectionchange: this.setTabs
            }
        });

    },

});
