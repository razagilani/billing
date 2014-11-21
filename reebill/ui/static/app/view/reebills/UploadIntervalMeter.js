Ext.define('ReeBill.view.reebills.UploadIntervalMeter', {
    extend: 'Ext.form.Panel',

    title: 'Upload Interval Meter CSV',

    alias: 'widget.uploadIntervalMeter',    

    bodyPadding: 15,
    collapsible:true,
    collapsed:true,
    floatable: false,
    titleCollapse: true,
    
    defaults: {
        anchor: '100%'
    },

    items: [{
        xtype: 'fileuploadfield',
        fieldLabel: 'CSV File',
        emptyText: 'Select a file to upload',
        name: 'file_to_upload',
        buttonText: 'Choose file...',
        allowBlank: false,
    },{
        xtype: 'fieldset',
        title: 'Mapping',
        defaults: {
            anchor: '100%',
            labelWidth: 200
        },
        collapsible: false,
        items: [{
            xtype: 'textfield',
            fieldLabel: 'Register Binding',
            name: 'register_binding',
            value: '',
            allowBlank: false
        },{
            xtype: 'textfield',
            fieldLabel: 'Timestamp Column',
            name: 'timestamp_column',
            value: 'A',
            allowBlank: false
        },{
            xtype: 'combo',
            value: '%Y-%m-%d %H:%M:%S',
            fieldLabel: 'Timestamp Format',
            name: 'timestamp_format',
            store: 'Timestamps',
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'name',
            editable: false,
            queryMode: 'local',
            forceSelection: true
        },{
            xtype: 'textfield',
            name: 'energy_column',
            fieldLabel: 'Metered Energy Column',
            value: 'B'
        },{
            xtype: 'combo',
            value: 'kwh',
            fieldLabel: 'Metered Energy Units',
            name: 'energy_unit',
            store: 'Units',
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'name',
            editable: false,
            queryMode: 'local',
            forceSelection: true
        }]
    }],

    dockedItems: [{
        dock: 'bottom',
        xtype: 'toolbar',
        items: ['->',{        
            xtype: 'button',
            text: 'Reset',
            action: 'resetUploadIntervalMeter'
        },{        
            xtype: 'button',
            text: 'Submit',
            action: 'submitUploadIntervalMeter'
        }]
    }]
});
