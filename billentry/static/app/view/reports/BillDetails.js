Ext.define('BillEntry.view.reports.BillDetails', {
    extend: 'BillEntry.view.utilitybills.UtilityBills',
    alias: 'widget.billDetails',

    plugins: [],

    // Omit columns by data_index
    omitColumns: [],
    disableColumns: true,

    initComponent: function() {
        var prependColumns = [{
            header: 'Acc ID',
            dataIndex: 'utility_account_id',
            width: 50
        },{
            header: 'Flagged By',
            dataIndex: 'flagged_by',
            width: 100
        }];

        // Ommiting columns in this.omitColumns
        for(var i=0; i < this.columns.length; i++){
            if(this.omitColumns.indexOf(this.columns[i].dataIndex) === -1){
                prependColumns.push(this.columns[i])
            }
        }

        // disabling columns if this.disableColumns
        if(this.disableColumns) {
            for (var i = 0; i < prependColumns.length; i++) {
                prependColumns[i].disabled = true;
            }
        }

        this.columns = prependColumns;
        this.callParent(arguments);
    },

    dockedItems: []

});