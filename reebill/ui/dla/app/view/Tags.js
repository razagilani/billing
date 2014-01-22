Ext.define('DocumentTools.view.Tags', {
    extend: 'Ext.grid.Panel',

    title: 'Tags',
    alias: 'widget.tags',    
    store: 'Tags',
    
    viewConfig: {
        trackOver: false,
        stripeRows: false
    },
    
    columns: [
        {header: 'Tag', dataIndex: 'tag', menuDisabled: true, flex: 1}
    ],
    
    dockedItems: [{
        xtype: 'toolbar',
        dock: 'top',
        items: [{
            text: 'Edit',
            action: 'editTag'
        },{
            text: 'Delete',
            action: 'deleteTag'
        }]
    }]
});