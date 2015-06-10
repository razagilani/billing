Ext.define('BillEntry.controller.UploadBills', {
    extend: 'Ext.app.Controller',

    stores: [
        'AltitudeAccounts'
    ],

    views: [
        'uploadbills.UploadBillsForm'],

    refs: [{
        ref: 'uploadBillsForm',
        selector: 'uploadBills'
    }],

    init: function() {
        this.application.on({
            scope: this
        });

        this.control({
             '[action=resetUploadBillsForm]': {
                 click: this.handleReset
             },
             '[action=submitUploadBillsForm]': {
                 click: this.handleSubmit
             }
         });
    },

    /**
    * Handle the submit button being clicked.
    */
    handleSubmit: function() {
        var scope = this;
        var store = this.getAltitudeAccountsStore();
        var dropzoneform = Ext.ComponentQuery.query('uploadFiles');
        dropzoneform.processQueue();
        this.getUploadBillsForm().getForm().submit({
             url: 'http://' + window.location.host + '/utilitybills/utilitybills',
             success: function () {
                 scope.initalizeUploadForm();
                 store.reload();
             },
             failure: function (form, action) {
                 utils.makeServerExceptionWindow(
                     'Unknown', 'Error', action.response.responseXML.body.innerHTML);
             }
         });
    },

    /**
     * Handle the compute button being clicked.
     */
    handleReset: function() {
        var form = this.getUploadBillsForm();
        form.getForm().reset();
    }
})
