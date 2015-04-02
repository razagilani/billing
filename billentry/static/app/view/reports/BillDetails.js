Ext.define('BillEntry.view.reports.BillDetails', {
    extend: 'BillEntry.view.utilitybills.UtilityBills',
    alias: 'widget.billDetails',
    store: 'UserUtilityBills',

    plugins: [],

    initComponent: function() {
        var prependColumns = [{
            header: 'Account ID',
            dataIndex: 'utility_account_id'
        }];

        // Omit columns by data_index
        var omitColumns = ['entered'];

        for(var i=0; i < this.columns.length; i++){
            if(omitColumns.indexOf(this.columns[i].dataIndex) === -1){
                prependColumns.push(this.columns[i])
            }
        }

        this.columns = prependColumns;
        this.callParent(arguments);
    },

    dockedItems: []

});