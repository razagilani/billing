Ext.define('DocumentTools.view.Viewport', {

    extend: 'Ext.container.Viewport',
    layout: 'fit',

    initComponent: function() {
        this.items = {
            layout: 'border',
            defaults: {
                collapsible: false,
                split: true
            },
            items: [{
                xtype: 'toolbar',
                region: 'north',
                items: ['->',{
                    xtype: 'button',
                    iconCls: 'silk-photo',
                    text: 'Images',
                    action: 'showImages'
                },{
                    xtype: 'button',
                    iconCls: 'silk-page-white-code-red',
                    text: 'Export JSON',
                    action: 'exportJSON'                    
                }]
            },{
                region: 'west',
                layout: 'border',
                width: 250,
                defaults: {
                    collapsible: false,
                    split: true
                },
                items: [{
                    xtype: 'regions',
                    id: 'regionsGrid',
                    region: 'center'
                },{
                    xtype: 'tags',
                    id: 'tagsGrid',
                    region: 'south',
                    height: 300                   
                }]
            },{
                xtype: 'viewer',
                id: 'viewerComponent',
                region: 'center',
                title: 'Document Viewer'
            }]
        };
        
        this.callParent();
    }
});