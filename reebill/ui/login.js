Ext.onReady(function() {
    var loginFormPanel = new Ext.form.FormPanel({
        standardSubmit: true,
        frame: true,
        title: 'Log in',
        width: 350,
        defaults: {width: 230},
        defaultType: 'textfield', // if this is wrong, including anything in 'items results in 'undefined is not a function'
        items: [
            {
                fieldLabel: 'Username',
                name: 'username',
                allowBlank: false
            },
            {
                fieldLabel: 'Password',
                name: 'password',
                allowBlank: false,
                inputType: 'password'
            },
            {
                inputType: 'hidden',
                id: 'submitbutton',
                name: 'myhiddenbutton',
                value: 'hiddenvalue'
            }
        ],
        buttons: [{
            text: 'Submit',
            handler: function() {
                loginFormPanel.getForm().getEl().dom.action = 'login';
                loginFormPanel.getForm().getEl().dom.method = 'POST';
                loginFormPanel.getForm().submit();
            }
        }]
    });
    loginFormPanel.render('loginform');
});
