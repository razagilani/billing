Ext.define('DocumentTools.view.DocumentViewer', {
    extend: 'Ext.Panel',

    alias: 'widget.viewer',    
    
    html: '<div id="imageTool"><div id="imageContainer"><img id="documentImage" src="images/bill.png" /> </div></div>',

    dockedItems: [{
        xtype: 'toolbar',
        dock: 'top',
        items: [{
            text: '+ Zoom In',
            action: 'zoomIn'
        },{
            text: '- Zoom Out',
            action: 'zoomOut'
        }]
    }]
});
