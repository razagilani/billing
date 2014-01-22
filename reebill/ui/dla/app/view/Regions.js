Ext.define('DocumentTools.view.Regions', {
    extend: 'Ext.grid.Panel',

    title: 'Regions',
    alias: 'widget.regions',    
    store: 'Regions',
    
    viewConfig: {
        trackOver: false,
        stripeRows: false
    },
    
    columns: [
        {header: 'Name', dataIndex: 'name', menuDisabled: true, flex: 1}
    ],
    
    plugins: [{
        ptype: 'rowexpander',
        rowBodyTpl : new Ext.XTemplate(
            '<b>Name:</b> {name}<br/>',
            '<b>Description:</b> {description}</br>',
            '<b>Color:</b> <span style="font-size: 8px;border: 1px solid black; background-color: #{color}">&nbsp;&nbsp;&nbsp;&nbsp;</span>',
        {
            formatChange: function(v){
                return v;
            }
        })
    }],

    dockedItems: [{
        xtype: 'toolbar',
        dock: 'top',
        items: [{
            text: 'Add',
            action: 'addRegion'
        },{
            text: 'Edit',
            action: 'editRegion'
        },{
            text: 'Delete',
            action: 'deleteRegion'
        }]
    }]
});

Ext.create('Ext.Window', {
    title: 'New Region',
    name: 'newRegionWindow',

    height: 230,
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
        id: 'newRegionForm',
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
            xtype: 'textarea',
            fieldLabel: 'Description',
            name: 'description',
            allowBlank: false
        },{
            xtype: 'colorfield',
            name: 'color',
            fieldLabel: 'Color',
            text: 'Select', 
            value: 'FF0000'
        },{
            xtype: 'sliderfield',
            fieldLabel: 'Opacity',
            name: 'opacity',
            value: 65
        }],

        buttonAlign: 'center',
        buttons: [{
            text: 'Save',
            action: 'saveNewRegion'
        },{
            text: 'Cancel',
            action: 'cancelNewRegion'
        }]
    }]
    
});