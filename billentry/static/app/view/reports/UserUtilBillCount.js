Ext.define('BillEntry.view.reports.UserUtilBillCount', {
    extend: 'Ext.grid.Panel',
    alias: 'widget.userUtilBillCount',
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
        header: '# of Gas Bills Entered',
        dataIndex: 'gas_count',
        width: 120,
        items: [
            utils.makeNumericGridFilterTextField('gas_count', '>'),
            utils.makeNumericGridFilterTextField('gas_count', '<')
        ],
        summaryType: 'sum'
    }, {
        header: '# of Electric Bills Entered',
        dataIndex: 'electric_count',
        width: 160,
        items: [
            utils.makeNumericGridFilterTextField('electric_count', '>'),
            utils.makeNumericGridFilterTextField('electric_count', '<')
        ],
        summaryType: 'sum'
    }, {
        header: 'Total # of Bills Entered',
        dataIndex: 'total_count',
        width: 150,
        items: [
            utils.makeNumericGridFilterTextField('total_count', '>'),
            utils.makeNumericGridFilterTextField('total_count', '<')
        ],
        summaryType: 'sum'
    },]

});