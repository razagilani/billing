Ext.define('BillEntry.view.reports.UserStatistics', {
    extend: 'Ext.grid.Panel',
    alias: 'widget.userStatistics',
    store: 'UserUtilBillCounts',

    features: [{
        ftype: 'summary'
    }],


    columns: [{
        header: 'User',
        dataIndex: 'email',
        minWidth: 150,
        flex: 1,
        items: utils.makeGridFilterTextField('email')
    }, {
        header: '# of Bills Entered',
        dataIndex: 'count',
        width: 120,
        items: utils.makeGridFilterTextField('count'),
        summaryType: 'sum'
    }]

});