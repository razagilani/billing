var EstimatedRevenueRenderer = function(value){
    if(!isNaN(parseFloat(value))){
        return Ext.util.Format.usMoney(parseFloat(value));
    }
    return value;
}


Ext.define('ReeBill.view.reports.EstimatedRevenue', {
    extend: 'Ext.grid.Panel',

    title:'12 Month Estimated Revenue',
    alias: 'widget.estimatedRevenue',
    store: 'EstimatedRevenue',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },
    
    columns: [{
        header: 'Account',
        dataIndex: 'account',
        width: 90,
        flex: 1
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -11), 'M Y'),
        dataIndex: 'revenue_11_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -10), 'M Y'),
        dataIndex: 'revenue_10_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -9), 'M Y'),
        dataIndex: 'revenue_9_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -8), 'M Y'),
        dataIndex: 'revenue_8_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -7), 'M Y'),
        dataIndex: 'revenue_7_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -6), 'M Y'),
        dataIndex: 'revenue_6_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, 5), 'M Y'),
        dataIndex: 'revenue_5_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -4), 'M Y'),
        dataIndex: 'revenue_4_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -3), 'M Y'),
        dataIndex: 'revenue_3_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -2), 'M Y'),
        dataIndex: 'revenue_2_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(Ext.Date.add(new Date(), Ext.Date.MONTH, -1), 'M Y'),
        dataIndex: 'revenue_1_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    },{
        header: Ext.Date.format(new Date(), 'M Y'),
        dataIndex: 'revenue_0_months_ago',
        width: 90,
        renderer: EstimatedRevenueRenderer
    }],

    bbar: {
        xtype: 'pagingtoolbar',
        pageSize: 25,
        store: 'EstimatedRevenue',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}'
    }

});
