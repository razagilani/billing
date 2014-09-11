Ext.define('ReeBill.view.Accounts', {
    extend: 'Ext.grid.Panel',

    title: 'Accounts Processing Status',
    alias: 'widget.accounts',   
    store: 'AccountsMemory',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {
            if (record.get('provisionable'))
                return 'account-grid-gray';
        }
    },
    
    columns: [{
        header: 'Account',
        dataIndex: 'account',
        width: 100
    },{
        header: 'Codename',
        dataIndex: 'codename',
        width: 120
    },{
        header: 'Casual Name',
        dataIndex: 'casualname',
        width: 200
    },{
        header: 'Primus Name',
        dataIndex: 'primusname',
        width: 120
    },{
        header: 'Utility Service Address',
        dataIndex: 'utilityserviceaddress',
        width: 200
    },{
        header: 'Last Issued',
        dataIndex: 'lastissuedate',
        width: 120,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        },
    },{
        header: 'Days Since',
        tooltip: 'Days Since Last Issued Utility Bill',
        dataIndex: 'lastperiodend',
        renderer: function(value){
            if(value === Infinity){
                return ''
            }
            return value
        },
        align: 'right',
        width: 100
    },{
        header: 'Last Event',
        dataIndex: 'lastevent',
        width: 350,
        flex:1
    }],

    bbar: {
        xtype: 'pagingmemorytoolbar',
        pageSize: 25,
        store: 'AccountsMemory',
        refreshStore: 'Accounts',
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
            store: 'AccountsFilter',
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'label',
            forceSelection: true,
            selectOnFocus: true
        }]
    }
});