/* Global variables for login */
Ext.namespace("ReeBill.LoginWindow");

ReeBill.LoginFormFields = [
{
    // TODO change "Username" label to "identifier".  Why? -RA
    name:'username',
    fieldLabel:'User Name',
    msgTarget:'side',
},{
    name:'password',
    fieldLabel:'Password',
    inputType:'password',
    msgTarget:'side',
},{
    name: 'rememberme',
    xtype: 'checkbox',
    fieldLabel: 'Remember Me'
}];

// used by external pages such as login.html
ReeBill.WelcomeLoginFormPanel = new Ext.form.FormPanel({
    id: "WelcomeLoginFormPanel",
    url: 'http://' + location.host + '/reebill/login',
    border: false,
    padding: 1, // chrome truncates top border of username text field
    defaultType: 'textfield', // if this is wrong, including anything in 'items results in 'undefined is not a function'
    items: ReeBill.LoginFormFields,
    buttons: [{
        text: 'Log In',
        type: 'submit',
        formBind: true,
        handler: function () {
            console.log(this);
            Ext.getCmp('WelcomeLoginFormPanel').form.submit({
                waitMsg:'Authenticating',
                success: function() {
                    window.location = 'http://' + location.host + '/billentry.html';
                }
            });
        },
    }],
    /*keys: [{
        key: [Ext.EventObject.ENTER],
        handler: submitHandler
    }]*/
})


// used in app for re-authenticating
ReeBill.LoginWindow = new Ext.Window({
    id: 'LoginWindow',
    title: "Log In",
    layout:'fit',
    width:300,
    height:160,
    closeAction:'hide',
    resizable: false,
    closable: false,
    items: new Ext.form.FormPanel({
        id: "LoginFormPanel",
        //standardSubmit: true,
        url: 'http://' + location.host + '/reebill/login',
        border: false,
        padding: '10px 0px 0px 10px',
        defaultType: 'textfield', // if this is wrong, including anything in 'items results in 'undefined is not a function'
        items: ReeBill.LoginFormFields,
        buttons: [{
            text: 'Log In',
            type: 'submit',
            formBind: true,
            handler: function () {
                console.log(this);
                Ext.getCmp('LoginFormPanel').form.submit({
                    waitMsg:'Authenticating',
                    success: function() {
                        Ext.getCmp('LoginWindow').hide();
                    }
                });
            },
        }],
        /*keys: [{
            key: [Ext.EventObject.ENTER],
            handler: submitHandler
        }]*/
    }),
});

/*var openIDButton = new Ext.Button({
    text: 'Log in With Your Google Account',
    //cls:'x-btn-text-icon',
    disabled: true,
});*/

