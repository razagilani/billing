//FIELD_INITIAL_STYLE = 'color:#bbdd99; font-size:medium';
//FIELD_NORMAL_STYLE = 'color:#66aa44; font-size:medium';
FIELD_NORMAL_STYLE = 'font-size:medium';

//var nameBlank = true;
//var passwordBlank = true;

var prettyField = function(name, label, inputType) {
    return new Ext.form.TextField({
        name: name,
        fieldLabel: label,
        labelStyle: 'font-size:medium',
        style: FIELD_NORMAL_STYLE,
        allowBlank: false,
        inputType: inputType,
    });
};

// TODO change "Username" label to "identifier"
var nameField = new prettyField('username', 'Username');
var passwordField = new prettyField('password', 'Password', 'password');

var openIdIdentifierField = new prettyField('identifier', 'Identifier');

var rememberMeCheckbox = new Ext.form.Checkbox({
    name: 'rememberme',
    boxLabel: 'Remember Me'
});

function submitHandler() {
    loginFormPanel.getForm().getEl().dom.action = 'http://' + location.host + '/reebill/login'
    loginFormPanel.getForm().getEl().dom.method = 'POST';
    loginFormPanel.getForm().submit();
}

var loginFormPanel = new Ext.form.FormPanel({
    standardSubmit: true,
    //frame: true,
    //title: 'Log in',
    border: false,
    width: 300,
    //defaults: {width: 350},
    defaultType: 'textfield', // if this is wrong, including anything in 'items results in 'undefined is not a function'
    items: [nameField, passwordField, rememberMeCheckbox],
    buttons: [{
        /* button style requires "cls:'buttonstyle'" attribute in button,
         * separate css file with ".buttonstyle {...}" */
        text: 'Log In',
        handler: submitHandler
    }],
    keys: [{
        key: [Ext.EventObject.ENTER],
        handler: submitHandler
    }]
});

var openIDButton = new Ext.Button({
    text: 'Log in With Your Google Account',
    //cls:'x-btn-text-icon',
    disabled: true,
});

var outerPanel = new Ext.Panel({
    items: [loginFormPanel, openIDButton],
    layout: new Ext.layout.VBoxLayout({
        align: 'center',
        padding: 0,
        defaultMargins: {top: 10, left: 10, right: 10, bottom: 10},
    }),
    border: false,
    height: 200, // TODO these should be set by the size of the contents instead of hard-coded
    width: 350,
})


function submitHandler() {
    loginFormPanel.getForm().getEl().dom.action = 'http://' + location.host + '/reebill/login'
    loginFormPanel.getForm().getEl().dom.method = 'POST';
    loginFormPanel.getForm().submit();
}

Ext.onReady(function() {

    outerPanel.render('loginform');

    //nameField.setValue("Username");
    //passwordField.setValue("Password");

    //nameField.on('keydown', function() {
        //nameBlank = (nameField.getValue() == '');
        //console.log('nameField value: "' + nameField.getValue() + '"');
    //});
    //passwordField.on('keydown', function() {
        //passwordBlank = (passwordField.getValue() == '');
        //console.log('passwordField value: "' + passwordField.getValue() + '"');
    //});

    //nameField.on('focus', function() {
        //console.log('username focus');
        //if (nameBlank) {
            //nameField.setValue('');
            //clickedUsername = false;
        //} else {
        //}
    //});
    //passwordField.on('focus', function() {
        //console.log('password focus');
        //if (passwordBlank) {
            //passwordField.setValue('');
            //passwordField.setInputType('password');
            //clickedPassword = false;
        //} else {

        //}
    //});
});

