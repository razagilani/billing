Ext.define('ReeBill.view.UtilityBills', {
    extend: 'Ext.grid.Panel',

    title: 'Utility Bills',
    alias: 'widget.utilityBills',    
    store: 'UtilityBillsMemory',
    
    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2,
            listeners: {
                beforeedit: function (e, editor) {
                    if (editor.record.get('processed'))
                        return false;
                }
            }
        })
    ],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {
            if (!record.get('processed'))
                return 'utilbill-grid-unprocessed';
        }
    },
    
    columns: [{
        header: 'Name',
        dataIndex: 'name',
        hidden: true
    },{
        header: 'Service',
        dataIndex: 'service',
        editor: {
            xtype: 'combo',
            name: 'service',
            store: 'Services',
            triggerAction: 'all',
            valueField: 'name',
            displayField: 'value',
            queryMode: 'local',
            forceSelection: true,
            selectOnFocus: true
        }  
    },{
        header: 'Start Date',
        dataIndex: 'period_start',
        editor: {
            xtype: 'datefield',
            allowBlank: false, 
            format: 'Y-m-d'
        },
        width: 100,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        }
    },{
        header: 'End Date',
        dataIndex: 'period_end',
        editor: {
            xtype: 'datefield',
            allowBlank: false, 
            format: 'Y-m-d'
        },
        width: 100,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        }
    },{
        header: 'Total',
        dataIndex: 'target_total',
        editor: {
            xtype: 'numberfield',
            allowBlank: false
        },
        width: 100,
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Calculated',
        dataIndex: 'computed_total',
        width: 100,
        renderer: Ext.util.Format.usMoney
    },{
        header: 'RB Seq./Vers.',
        tooltip: 'Reebill Sequence/Version',
        dataIndex: 'reebills',
        width: 120,
        renderer: function(value, metaData, record) {
            var result = '';
            var reebills = record.get('reebills');

            for (var i = 0; i < reebills.length; i++) {
                var sequence = reebills[i].sequence;
                result += sequence.toString() + "-";
                while (i < reebills.length && reebills[i].sequence ==
                        sequence) {
                    result += reebills[i].version + ",";
                    i++;
                } 
                result = result.substr(0,result.length-1);
                result += ' ';
            }

            return result;
        }
    },{
        header: 'Processed',
        dataIndex: 'processed',
        width: 100,
        tooltip: "<b>Processed:</b> This bill's rate structure and charges are correct and will be used to predict the rate structures of other bills.<br /><b>Unprocessed:</b> This bill will be ingnored when predicting the rate structures of other bills.<br />",
        renderer: function(value) {
            return value ? 'Yes' : 'No';                    
        }
    },{
        header: 'State',
        dataIndex: 'state',
        width: 100
    },{
        header: 'Utility',
        dataIndex: 'utility',
        editor: {
            xtype: 'combo',
            id: 'utility_combo',
            store: 'Utilities',
            displayField: 'name',
            valueField: 'name',
            triggerAction: 'all',
            forceSelection: false,
            typeAhead: true,
            typeAheadDelay : 1,
            autoSelect: false,
            minChars: 1,
            listeners: {
                blur: {
                    fn: function (combo) {
                        utility_grid = combo.findParentByType('grid');
                        selected = utility_grid.getSelectionModel().getSelection()[0];
                        selected.set('action', 'utility');
                    }
                },
                focus: function(combo) {
                    utility_grid = combo.findParentByType('grid');
                    selected = utility_grid.getSelectionModel().getSelection()[0];
                    combo.setValue(selected.get('utility').name);
                }
            }
        },
        width: 100,
        renderer: function(value, metaData, record) {
            return record.get('utility').name;
        }
    },{
        header: 'Supplier',
        dataIndex: 'supplier',
        editor: {
            xtype: 'combo',
            store: 'Suppliers',
            displayField: 'name',
            valueField: 'name',
            triggerAction: 'all',
            forceSelection: false,
            typeAhead: true,
            typeAheadDelay : 1,
            autoSelect: false,
            minChars: 1,
            listeners: {
                blur: {
                    fn: function (combo) {
                        utility_grid = combo.findParentByType('grid');
                        selected = utility_grid.getSelectionModel().getSelection()[0];
                        selected.set('action', 'supplier');
                    }
                },
                focus: function(combo) {
                    utility_grid = combo.findParentByType('grid');
                    selected = utility_grid.getSelectionModel().getSelection()[0];
                    combo.setValue(selected.get('supplier').name);
                }
            }
        },
        width: 100,
        renderer: function(value, metaData, record) {
            return record.get('supplier').name;
        }
    },{
        header: 'Rate Class',
        dataIndex: 'rate_class',
        editor: {
            xtype: 'combo',
            store: 'RateClasses',
            displayField: 'name',
            valueField: 'name',
            triggerAction: 'all',
            forceSelection: false,
            typeAhead: true,
            typeAheadDelay: 1,
            autoSelect: false,
            minChars: 1,
            listeners: {
                blur: {
                    fn: function (combo) {
                        utility_grid = combo.findParentByType('grid');
                        selected = utility_grid.getSelectionModel().getSelection()[0];
                        selected.set('action', 'rate_class');
                    }
                },
                beforeselect: {
                    fn: function(combo, record, index){
                        utility_grid = combo.findParentByType('grid');
                        selected = utility_grid.getSelectionModel().getSelection()[0];
                        this.store.clearFilter(true);
                        this.store.filter('utility_id', selected.id);
                    }
                },
                focus: function(combo) {
                    utility_grid = combo.findParentByType('grid');
                    selected = utility_grid.getSelectionModel().getSelection()[0];
                    combo.setValue(selected.get('rate_class').name);
                }
            }
        },
        width: 125,
        flex: 1,
        renderer: function(value, metaData, record) {
            return record.get('rate_class').name;
        }
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{
            xtype: 'button',
            action: 'utilbillCompute',
            text: 'Compute',
            disabled: true
        },{
            xtype: 'button',
            action: 'utilbillRemove',
            iconCls: 'silk-delete',
            text: 'Delete',
            disabled: true
        },{
            xtype: 'button',
            action: 'utilbillToggleProcessed',
            text: 'Toggle Processed',
            disabled: true
//        },'-',{
//            xtype: 'button',
//            action: 'utilbillDla',
//            text: 'Layout',
//            disabled: true
//        },{
//            xtype: 'button',
//            action: 'utilbillSlice',
//            text: 'Identify',
//            disabled: true
//        },{
//            xtype: 'button',
//            action: 'utilbillResults',
//            text: 'Review',
//            disabled: true
        }]
    }],

    bbar: {
        xtype: 'pagingmemorytoolbar',
        pageSize: 25,
        store: 'UtilityBillsMemory',
        refreshStore: 'UtilityBills',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}'
    }
});
