Ext.define('ReeBill.view.Reebills', {
    extend: 'Ext.grid.Panel',

    title: 'Reebills',
    alias: 'widget.reebills',    
    store: 'Reebills',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {
            if (record.get('issued')) {
                // issued bill
            } else if (record.get('version') == 0) {
                // unissued version-0 bill
                return 'reebill-grid-unissued';
            } else {
                // unissued correction
                return 'reebill-grid-unissued-correction';
            }
        }
    },

    columns: [{
        header: 'Sequence',
        sortable: true,
        dataIndex: 'sequence',
        width: 90
    },{
        header: 'Corrections',
        sortable: false,
        dataIndex: 'corrections',
        width: 100
    },{
        header: 'Start Date',
        sortable: false,
        dataIndex: 'period_start',
        width: 120
    },{
        header: 'End Date',
        sortable: false,
        dataIndex: 'period_end',
        width: 120
    },{
        header: 'Issue Date',
        sortable: false,
        dataIndex: 'issue_date',
        width: 100,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        }
    },{
        header: 'Processed',
        dataIndex: 'processed',
        width: 100,
        renderer: function(value) {
            return value ? 'Yes' : 'No';
        }
    },{
        header: 'Hypo',
        sortable: false,
        dataIndex: 'hypothetical_total',
        width: 120,
        align: 'right',
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Actual',
        sortable: false,
        dataIndex: 'actual_total',
        width: 120,
        align: 'right',
        renderer: Ext.util.Format.usMoney
    },{
        header: 'RE&E',
        sortable: false,
        dataIndex: 'ree_quantity',
        width: 120,
        flex: 1,
        align: 'right',
        renderer: function(value) {
            if (typeof(value) == 'number')
                return value.toFixed(5);

            return value;
        }
    },{
        header: 'RE&E Value',
        sortable: false,
        dataIndex: 'ree_value',
        width: 120,
        align: 'right',
        renderer: Ext.util.Format.usMoney
    },{
        header: 'RE&E Charges',
        sortable: false,
        dataIndex: 'ree_charge',
        align: 'right',
        width: 120,
        renderer: Ext.util.Format.usMoney
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        items: [{
            xtype: 'button',
            text: 'Create Next',
            action: 'createNext',
            iconCls: 'silk-add'
        },{
            xtype: 'button',
            text: 'Delete',
            action: 'deleteReebill',
            iconCls: 'silk-delete',
            disabled: true
        },{        
            xtype: 'button',
            text: 'Create New Version',
            action: 'createNewVersion',
            iconCls: 'silk-add',
            disabled: true
        },'-',{
            xtype: 'button',
            text: 'Bind RE&E Offset',
            action: 'bindREOffset'
        },{
            xtype: 'button',
            text: 'Compute',
            action: 'computeReebill'
        },{
            xtype: 'button',
            text: 'Toggle Processed',
            action: 'toggleReebillProcessed'
        },'-',{
            xtype: 'button',
            text: 'Render PDF',
            action: 'renderPdf',
            disabled: true
        },'-',{
            xtype: 'button',
            text: 'Mail',
            iconCls: 'silk-email',
            action: 'email'
        }]
    }],

    bbar: {
        xtype: 'pagingtoolbar',
        pageSize: 25,
        store: 'Reebills',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}'
    }
});