Ext.define('BillEntry.view.reports.UserStatistics', {
    extend: 'Ext.grid.Panel',
    alias: 'widget.userStatistic',
    title: 'User Statistics',
    store: 'Users',

    //plugins: [
    //    Ext.create('Ext.grid.plugin.CellEditing', {
    //        clicksToEdit: 2,
    //        listeners: {
    //            beforeedit: function (e, editor) {
    //                if (editor.record.get('processed'))
    //                    return false;
    //            }
    //        }
    //    })
    //],

    //viewConfig: {
    //    trackOver: false,
    //    stripeRows: true,
    //    getRowClass: function(record) {
    //        if (!record.get('processed'))
    //            return 'utilbill-grid-unprocessed';
    //    }
    //},

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
        items: utils.makeGridFilterTextField('count')
    }]

});