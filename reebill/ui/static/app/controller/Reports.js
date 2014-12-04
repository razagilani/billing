Ext.define('ReeBill.controller.Reports', {
    extend: 'Ext.app.Controller',

    stores: [
        'Accounts'
    ],

    views: [
        'reports.AccountDatePicker', 'reports.EstimatedRevenue',
        'reports.Exports', 'reports.Reconciliations'
    ],
    
    refs: [{
        ref: 'reconciliationsGrid',
        selector: 'grid[id=reconciliationsGrid]'
    },{
        ref: 'exportRebill',
        selector: 'button[action=serviceForCharges]'
    },{
        ref: 'exportUtilityBills',
        selector: 'button[action=exportRebill]'
    },{
        ref: 'accountDatePicker',
        selector: 'window[id=accountDatePicker]'
    },{
        ref: 'submitAccountDatePicker',
        selector: 'button[action=submitAccountDatePicker]'
    },{
        ref: 'resetAccountDatePicker',
        selector: 'button[action=resetAccountDatePicker]'
    },{
        ref: 'export12MonthRevenue',
        selector: 'button[action=export12MonthRevenue]'
    }],
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'panel[name=reportsTab]': {
                activate: this.handleActivate
            },
            'grid[id=reconciliationsGrid]': {
                selectionchange: this.handleRowSelect
            },
            'button[action=exportRebill]': {
                click: this.handleExportRebill
            },
            'button[action=exportUtilityBills]': {
                click: this.handleExportUtilityBills
            },
            'button[action=submitAccountDatePicker]': {
                click: this.handleSubmitAccountDatePicker
            },
            'button[action=resetAccountDatePicker]': {
                click: this.handleResetAccountDatePicker
            },
            'button[action=export12MonthRevenue]': {
                click: this.handleExport12MonthRevenue
            }
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
    },

    /**
    * Handle the ExportRebill button.
    */
    handleExportRebill: function() {
        var dialog = this.getAccountDatePicker();
        var form = dialog.down('form').getForm();
        form.baseParams = {type: 'reebill_details'};
        dialog.show();
    },

    /**
     * Handle the ExportUtilityBills button.
     */
    handleExportUtilityBills: function() {
        var dialog = this.getAccountDatePicker();
        var form = dialog.down('form').getForm();
        form.baseParams = {type: 'utilbills'};
        dialog.show();
    },

    /**
     * Handle the Export12MonthRevenue button.
     */
    handleExport12MonthRevenue: function() {
        var dialog = this.getAccountDatePicker();
        var form = dialog.down('form').getForm();
        form.baseParams = {type: '12MonthRevenue'};
        this.handleSubmitAccountDatePicker();
    },

    handleSubmitAccountDatePicker: function() {
        var dialog = this.getAccountDatePicker();
        var formPanel = dialog.down('form');
        var form = formPanel.getForm();
        var saveButton = this.getSubmitAccountDatePicker();
        form.submit({
            url: 'http://' + window.location.host + '/reebill/reports',
            submitEmptyText: false
        });
    },

    handleResetAccountDatePicker: function() {
        var dialog = this.getAccountDatePicker();
        dialog.down('form').getForm().reset();
    }

});
