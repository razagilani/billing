Ext.define('BillEntry.controller.UploadBills', {
    extend: 'Ext.app.Controller',

    stores: [
        'AltitudeAccounts'
    ],

    views: [
        'uploadbills.UploadBillsForm'],

    refs: [{
        ref: 'uploadBillsForm',
        selector: 'uploadBillsForm'
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
     * Initialize the upload form.
     */
    initalizeUploadForm: function() {
         var form = this.getUploadBillsForm();
         form.getForm().reset();
         var dropzone = document.getElementById('dropzoneIFrame').contentDocument.getElementById('upload-files').dropzone;
         var url = 'http://'+window.location.host+'/utilitybills/uploadbill';
         Ext.Ajax.request({
                              url: url,
                              params: {},
                              method: 'DELETE',
                              failure: function (response) {
                              },
                              success: function (response) {
                              }
                          });
         dropzone.removeAllFiles();
     },

    /**
    * Handle the submit button being clicked.
    */
    handleSubmit: function() {
        var scope = this;
        var store = this.getAltitudeAccountsStore();

        this.getUploadBillsForm().getForm().submit({
             url: 'http://' + window.location.host + '/utilitybills/uploadbill',
             success: function () {
                 scope.initalizeUploadForm();
                 store.reload();
             },
             failure: function (form, action) {
                 utils.makeServerExceptionWindow(
                     'Unknown', 'Error', action.response.responseText);
             }
         });
    },

    /**
     * Handle the reset button being clicked.
     */
    handleReset: function() {
        this.initalizeUploadForm();
    }
})
