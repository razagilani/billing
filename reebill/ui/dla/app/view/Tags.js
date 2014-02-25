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
            text: 'Add',
            action: 'addTag',
            iconCls: 'silk-tag-blue-add'
        },{
            text: 'Edit',
            action: 'editTag',
            iconCls: 'silk-tag-blue-edit'
        },{
            text: 'Delete',
            action: 'deleteTag',
            iconCls: 'silk-tag-blue-delete'
        }]
    }]
});

Ext.create('Ext.Window', {
    title: 'Tag',
    name: 'tagWindow',

    width: 300,
    
    closable: true,
    closeAction: 'hide',
    
    layout: {
        type: 'vbox',
        align: 'stretch'
    },
    
    items: [{
        xtype: 'form',
        layout: 'form',
        id: 'tagForm',
        bodyPadding: 10,
        fieldDefaults: {
            msgTarget: 'side',
            labelWidth: 75
        },
        defaultType: 'textfield',
        items: [{
            fieldLabel: 'Tag',
            name: 'tag',
            allowBlank: false
        },{
            xtype: 'hiddenfield',
            name: 'id'
        }],

        buttonAlign: 'center',
        buttons: [{
            text: 'Save',
            action: 'saveTag'
        },{
            text: 'Cancel',
            action: 'cancelTag'
        }]
    }] 
});