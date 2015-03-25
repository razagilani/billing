Ext.define('BillEntry.view.reports.BillDetails', {
    extend: 'BillEntry.view.utilitybills.UtilityBills',
    alias: 'widget.billDetails',
    store: 'UserUtilityBills',

    plugins: [],

    initComponent: function() {
        var additionalColumns =[{
            header: 'Account ID',
            dataIndex: 'utility_account_id'
        }];

        console.log(this.columns);
        // Prepend the additional columns
        additionalColumns.push.apply(
            additionalColumns, this.columns
        );
        this.columns = additionalColumns;
        console.log(this.columns);
        this.callParent(arguments);
    },

    dockedItems: []

});