Ext.create('Ext.Window', {
    title: 'Images',
    name: 'imagesWindow',

    width: 400,
    
    closable: true,
    closeAction: 'hide',
    
    layout: {
        type: 'vbox',
        align: 'stretch'
    },
    
    items: [{
        xtype: 'form',
        layout: 'form',
        id: 'imageForm',
        bodyPadding: 10,
        fieldDefaults: {
            labelWidth: 75
        },
        items: [{
            fieldLabel: 'Image',
            xtype: 'combo',
            name: 'image',
            displayField: 'name',
            valueField: 'id',
            queryMode: 'local',
            editable: false
        }],

        buttonAlign: 'center',
        buttons: [{
            text: 'Load',
            action: 'loadImage'
        },{
            text: 'Add New',
            action: 'addImage'
        },{
            text: 'Delete',
            action: 'deleteImage'
        },{
            text: 'Close',
            action: 'closeImages'
        }]
    }]
    
});

Ext.create('Ext.Window', {
    title: 'New Image',
    name: 'newImageWindow',

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
        id: 'newImageForm',
        bodyPadding: 10,
        fieldDefaults: {
            msgTarget: 'side',
            labelWidth: 75
        },
        defaultType: 'textfield',
        items: [{
            fieldLabel: 'Name',
            name: 'name',
            allowBlank: false
        },{
            fieldLabel: 'Path',
            name: 'path',
            allowBlank: false
        }],

        buttonAlign: 'center',
        buttons: [{
            text: 'Save',
            action: 'saveNewImage'
        },{
            text: 'Cancel',
            action: 'cancelAddImage'
        }]
    }]
    
});