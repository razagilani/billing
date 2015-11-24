Ext.define('ReeBill.view.utilitybills.UploadUtilityBill', {
    extend: 'Ext.form.Panel',

    title: 'Upload Utility Bill',

    alias: 'widget.uploadUtilityBill',    

    requires: ['ReeBill.store.Services'],

    bodyPadding: 15,
    titleCollapse: true,
    floatable: false,
    collapsed: true,
    
    defaults: {
        anchor: '100%'
    },

    items: [{
        xtype: 'textfield',
        fieldLabel: 'Account',
        name: 'account',
        allowBlank: false
    },{
        xtype: 'combo',
        fieldLabel: 'Service',
        name: 'service',
        store: 'Services',
        triggerAction: 'all',
        valueField: 'value',
        displayField: 'name',
        value: 'Gas',
        queryMode: 'local',
        forceSelection: true,
        selectOnFocus: true
    },{
        xtype: 'datefield',
        fieldLabel: 'Begin Date',
        name: 'begin_date',
        allowBlank: false,
        format: 'Y-m-d'
    },{
        xtype: 'datefield',
        fieldLabel: 'End Date',
        name: 'end_date',
        allowBlank: false,
        format: 'Y-m-d'
    },{
        xtype: 'numberfield',
        fieldLabel: 'Total Charges',
        name: 'total_charges',
        value: 0,
        allowBlank: false
    },{
        xtype: 'fileuploadfield',
        fieldLabel: 'File',
        emptyText: 'Select a file to upload',
        name: 'file_to_upload',
        buttonText: 'Choose file...',
        allowBlank: true
    }],

    dockedItems: [{
        dock: 'bottom',
        xtype: 'toolbar',
        items: ['->',{
            xtype: 'button',
            action: 'resetUploadUtilityBillForm',
            text: 'Reset'
        },{
            xtype: 'button',
            action: 'submitUploadUtilityBillForm',
            text: 'Submit'
        }]
    }]

});
