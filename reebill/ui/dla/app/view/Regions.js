Ext.define('DocumentTools.view.Regions', {
    extend: 'Ext.grid.Panel',

    title: 'Regions',
    alias: 'widget.regions',    
    store: 'Regions',
    
    viewConfig: {
        trackOver: false,
        stripeRows: false,
        getRowClass: function(rec) {
            if (rec.get('hidden'))
                return 'disabled-row';
        }
    },
    
    columns: [
        {header: 'Name', dataIndex: 'name', menuDisabled: true, flex: 1, renderer: function(val, md, rec) {
            if (rec.get('hidden'))
                return val + ' (hidden)';

            return val;
        }},
        {header: '', dataIndex: 'color', menuDisabled: true, width: 25, renderer: function(val, md, rec) {
            
            return '<span style="font-size: 8px;border: 1px solid black; background-color: #' + val + '">&nbsp;&nbsp;&nbsp;&nbsp;</span>';
        }}            
    ],
    
    plugins: [{
        ptype: 'rowexpander',
        rowBodyTpl : new Ext.XTemplate(
            '<b>Name:</b> {name}<br/>',
            '<b>Type:</b> {type}</br>',
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
            action: 'addRegion',
            iconCls: 'silk-shape-square-add'
        },{
            text: 'Edit',
            action: 'editRegion',
            iconCls: 'silk-shape-square-edit'
        },{
            text: 'Delete',
            action: 'deleteRegion',
            iconCls: 'silk-shape-square-delete'
        },{
            text: 'Toggle',
            action: 'toggleShow',
            iconCls: 'silk-eye'
        }]
    }]
});

Ext.create('Ext.Window', {
    title: 'Region',
    name: 'regionWindow',

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
        id: 'regionForm',
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
            xtype: 'combo',
            fieldLabel: 'Type',
            name: 'type',
            store: Ext.create('Ext.data.Store', {
                fields: ['label', 'value'],
                data : [
                    {'label':'Slice', 'value':'slice'},
                    {'label':'Mask', 'value':'mask'}
                ]
            }),
            queryMode: 'local',
            displayField: 'label',
            valueField: 'value',
            value: 'slice'
        },{
            xtype: 'textarea',
            fieldLabel: 'Description',
            name: 'description',
            allowBlank: true
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
        },{
            xtype: 'hiddenfield',
            name: 'id'
        }],

        buttonAlign: 'center',
        buttons: [{
            text: 'Save',
            action: 'saveRegion'
        },{
            text: 'Cancel',
            action: 'cancelRegion'
        }]
    }]
    
});