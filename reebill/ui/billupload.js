Ext.onReady(function() {
    // account field
    var account = new Ext.form.TextField({
        fieldLabel: 'Account',
            name: 'account',
            width: 200,
            allowBlank: false,
    });

    // date fields
    var begin_date = new Ext.form.DateField({
        fieldLabel: 'Begin Date',
            name: 'begin_date',
            width: 90,
            allowBlank: false,
            format: 'Y-m-d'
    });
    var end_date = new Ext.form.DateField({
        fieldLabel: 'End Date',
            name: 'end_date',
            width: 90,
            allowBlank: false,
            format: 'Y-m-d'
    });

    // buttons
    var reset_button = new Ext.Button({
        text: 'Reset',
        handler: function() {this.findParentByType(Ext.form.FormPanel).getForm().reset(); }
    });
    var submit_button = new Ext.Button({
        text: 'Submit',
        handler: saveForm
    });

    var form_panel = new Ext.form.FormPanel({
        fileUpload: true,
        renderTo: 'myform',
        title: 'Upload Bill',
        width: 400,
        url: 'http://localhost:8086/upload',
        frame:true,

        autoHeight: true,
        bodyStyle: 'padding: 10px 10px 0 10px;',
        labelWidth: 50,
        defaults: {
            anchor: '95%',
            allowBlank: false,
            msgTarget: 'side'
        },

        items: [
            account,
            begin_date,
            end_date,

            //file_chooser
            {
                xtype: 'fileuploadfield',
                id: 'form-file',
                emptyText: 'Select a file to upload',
                name: 'file_to_upload',
                buttonText: 'Choose file...',
                buttonCfg: { width:80 }
            },
        ],

        buttons: [reset_button, submit_button],
    });

});


function saveForm() {
    //http://www.sencha.com/forum/showthread.php?127087-Getting-the-right-scope-in-button-handler
    var formPanel = this.findParentByType(Ext.form.FormPanel);
    if (formPanel.getForm().isValid()) {
        formPanel.getForm().submit({
            params:{
                       // see baseParams
                   },
            waitMsg:'Saving...',
            failure: function(form, action) {
                // TODO: better error messages here
                switch (action.failureType) {
                    case Ext.form.Action.CLIENT_INVALID:
                        Ext.Msg.alert('Failure',
                            'Form fields may not be submitted with invalid values');
                        break;
                    case Ext.form.Action.CONNECT_FAILURE:
                        Ext.Msg.alert('Failure', 'Ajax communication failed');
                        break;
                    case Ext.form.Action.SERVER_INVALID:
                        Ext.Msg.alert('Failure');
                        break;
                    default:
                        Ext.Msg.alert('Failure');
                }
            },
            success: function(form, action) {
                         //alert(action.success);
            }
        });
    }else{
        Ext.MessageBox.alert('Errors', 'Please fix form errors noted.');
    }
}

