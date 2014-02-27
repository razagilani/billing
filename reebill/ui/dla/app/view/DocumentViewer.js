Ext.define('DocumentTools.view.DocumentViewer', {
    extend: 'Ext.Panel',

    alias: 'widget.viewer',    
    
    html: '<div id="imageTool"><div id="imageContainer"></div></div>',

    dockedItems: [{
        xtype: 'toolbar',
        dock: 'top',
        items: [{
            text: 'Zoom In',
            action: 'zoomIn',
            iconCls: 'silk-zoom-in'
        },{
            text: 'Zoom Out',
            action: 'zoomOut',
            iconCls: 'silk-zoom-out'
        }]
    }]
});