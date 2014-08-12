Ext.define('ReeBill.controller.Viewer', {
    extend: 'Ext.app.Controller',

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
                selectionchange: this.handleUtilityBillSelect
            },
            'grid[id=reebillsGrid]': {
                selectionchange: this.handleReebillSelect
            }
        });
    },

    /**
     * Handle the selection of a utility bill.
     */
    handleUtilityBillSelect: function(sm, selections) {
        var bill = selections[0];
        var viewer = this.getUtilityBillViewer();
        viewer.setSrc(window.location.origin + '/utilitybills/' + bill.get('account') + '/' + bill.get('id') + '.pdf');
    },

    /**
     * Handle the selection of a reebill.
     */
    handleReebillSelect: function() {
        var bill = selections[0];
        var s = bill.get('sequence') + '';
        while (s.length < 4) {
            s = '0' + s;
        }
        var viewer = this.getReebillViewer();
        viewer.setSrc(window.location.origin + '/reebills/' + bill.get('account') + '/' + bill.get('account') + '_' + s + '.pdf');
    }

});
