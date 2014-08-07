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
//                selectionchange: this.handleUtilityBillSelect
            },
            'grid[id=reebillsGrid]': {
//                selectionchange: this.handleReebillSelect
            }
        });
    },

    /**
     * Handle the selection of a utility bill.
     */
    handleUtilityBillSelect: function(sm, selections) {
        var viewer = this.getUtilityBillViewer();
        viewer.setSrc('http://www.scala-lang.org/docu/files/ScalaByExample.pdf');

        if (viewer.getCollapsed())
            viewer.toggleCollapse();
    },

    /**
     * Handle the selection of a reebill.
     */
    handleReebillSelect: function() {
        var viewer = this.getReebillViewer();
        viewer.setSrc('http://www.scala-lang.org/docu/files/ScalaByExample.pdf');
    }

});
