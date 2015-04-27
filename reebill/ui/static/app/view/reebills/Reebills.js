Ext.define('ReeBill.view.reebills.Reebills', {
    extend: 'Ext.grid.Panel',
    requires: ['ReeBill.store.Reebills'],
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
                if (record.get('processed')){
                    return 'reebill-grid-unissued-processed';
                }
                return 'reebill-grid-unissued';
            } else {
                // unissued correction
                return 'reebill-grid-unissued-correction';
            }
        }
    },

    columns: [{
        header: 'Sequence',
        dataIndex: 'sequence',
        width: 90
    },{
        header: 'Corrections',
        dataIndex: 'corrections',
        width: 100
    },{
        header: 'Start Date',
        dataIndex: 'period_start',
        width: 120
    },{
        header: 'End Date',
        dataIndex: 'period_end',
        width: 120
    },{
        header: 'Issue Date',
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
        dataIndex: 'hypothetical_total',
        width: 120,
        align: 'right',
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Actual',
        dataIndex: 'actual_total',
        width: 120,
        align: 'right',
        renderer: Ext.util.Format.usMoney
    },{
        header: 'RE&E',
        dataIndex: 'ree_quantity',
        width: 120,
        align: 'right',
        renderer: function(value) {
            if (typeof(value) == 'number')
                return value.toFixed(5);

            return value;
        }
    },{
        header: 'RE&E Value',
        dataIndex: 'ree_value',
        width: 120,
        align: 'right',
        renderer: Ext.util.Format.usMoney
    },{
        header: 'RE&E Charges',
        dataIndex: 'ree_charge',
        align: 'right',
        width: 120,
        renderer: Ext.util.Format.usMoney
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{
            xtype: 'button',
            text: 'Create Next',
            action: 'createNext',
            iconCls: 'silk-add'
        },{
            xtype: 'button',
            text: 'Create Estimated',
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
            action: 'bindREOffset',
            disabled: true
        },{
            xtype: 'button',
            text: 'Compute',
            action: 'computeReebill',
            disabled: true
        },{
            xtype: 'button',
            text: 'Update Readings',
            action: 'updateReadings',
            disabled: true
        },{
            xtype: 'button',
            text: 'Toggle Processed',
            action: 'toggleReebillProcessed',
            disabled: true
        },'-',{
            xtype: 'button',
            text: 'Render PDF',
            action: 'renderPdf',
            disabled: true
        },'-',{
            xtype: 'button',
            text: 'Mail',
            iconCls: 'silk-email',
            action: 'email',
            disabled: true
        }]
    }]
});
