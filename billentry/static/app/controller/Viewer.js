Ext.define('BillEntry.controller.Viewer', {
    extend: 'Ext.app.Controller',

    require: ['Ext.panel.PDF'],

    views: [
        'BillEntry.view.utilitybills.UtilityBills',
        'BillEntry.view.reports.BillDetails'
    ],

    refs: [{
        ref: 'utilityBillViewer',
        selector: 'pdfpanel[name=utilityBillViewer]'
    }],    
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.handleUtilityBillSelect,
                deselect: this.handleUtilityBillDeselect,
            },
            'grid[id=reportUtilityBillsGrid]': {
                selectionchange: this.handleUtilityBillSelect,
                deselect: this.handleUtilityBillDeselect,
            },
        });
    },

    /**
     * Handle the selection of a utility bill.
     */
    handleUtilityBillSelect: function(sm, selections) {
        var bill = selections[0];
        if(bill === undefined){
            return
        }
        var viewer = this.getUtilityBillViewer();
        viewer.setSrc(bill.get('pdf_url'));
    },

    handleUtilityBillDeselect: function(){
        var viewer = this.getUtilityBillViewer();
        viewer.setSrc('');
    },

});
