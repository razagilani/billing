Ext.define('ReeBill.view.Accounts', {
    extend: 'Ext.grid.Panel',

    title: 'Accounts Processing Status',
    alias: 'widget.accounts',   
    store: 'Accounts',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {
            if (record.get('provisionable'))
                return 'account-grid-gray';
        }
    },
    
    columns: [
        {header: 'Account', dataIndex: 'account'},
        {header: 'Codename', dataIndex: 'codename'},        
        {header: 'Casual Name', dataIndex: 'casualname'},        
        {header: 'Primus Name', dataIndex: 'primusname'},        
        {header: 'Utility Service Address', dataIndex: 'utilityserviceaddress'},        
        {header: 'Last Issued', dataIndex: 'lastissuedate'},        
        {header: 'Days Since Utility Bill', dataIndex: 'dayssince'},        
        {header: 'Last Event', dataIndex: 'lastevent', width: 350}
    ],

    bbar: {
        xtype: 'pagingtoolbar',
        pageSize: 25,
        store: 'Accounts',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}',
        items: ['->',{
            xtype: 'combo',
            name: 'accountsFilter',
            fieldLabel: 'Filter',
            labelWidth: 50,
            width: 400,
            value: '',
            editable: false,
            store: new Ext.data.Store({
                fields: ['label', 'value'],
                data: [
                    {label: 'No filter', value: ''},
                    {label: 'All ReeBill Customers', value: 'reebillcustomers'},
                    {label: 'All XBill Customers', value: 'xbillcustomers'}
                ]
            }),
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'label',
            forceSelection: true,
            selectOnFocus: true
        }]
    }
});