Ext.define('ReeBill.controller.Viewer', {
    extend: 'Ext.app.Controller',

    require: ['Ext.panel.PDF'],

    views: [
        'utilitybills.UtilityBills',
        'reebills.Reebills'
    ],

    refs: [{
        ref: 'utilityBillViewer',
        selector: 'pdfpanel[name=utilityBillViewer]'
    },{
        ref: 'reebillViewer',
        selector: 'pdfpanel[name=reebillViewer]'
    }],    
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.handleUtilityBillSelect,
                deselect: this.handleUtilityBillDeselect
            },
            'grid[id=reebillsGrid]': {
                selectionchange: this.handleReebillSelect,
                deselect: this.handleReebillDeselect
            }
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

    /**
     * Handle the selection of a reebill.
     */
    handleReebillSelect: function(sm, selections) {
        var bill = selections[0];
        if(bill === undefined){
            return
        }
        var s = bill.get('sequence') + '';
        while (s.length < 4) {
            s = '0' + s;
        }
        var viewer = this.getReebillViewer();
        viewer.setSrc(window.location.origin + '/reebills/' + bill.get('account') + '/' + bill.get('account') + '_' + s + '.pdf');
    },

    handleReebillDeselect: function(){
        var viewer = this.getReebillViewer();
        viewer.setSrc('');
    }

});
