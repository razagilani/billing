Ext.define('ReeBill.view.accounts.MergeDialog', {
    extend: 'Ext.window.Window',
    requires: [],
    xtype: 'mergedialog',
    modal: true,
    autoScroll: true,
    width: 550,
    maxHeight: 650,
    title: 'Merge Records',
    requires: ['ReeBill.model.MergeModel'],

    // The records to merge
    records: {},
    // The grid that defines the columns that should be merged
    basedOn: null,
    // The store associated with the records
    store: null,
    // The dataIndeces of columns that should be excluded
    exclude: [],

    initComponent: function(){
        // Build a Dictionary of options for each field
        var me = this;
        var options = {};
        Ext.each(this.records, function(rec){
            for(var key in rec.data){
                if (options[key] === undefined){
                    options[key] = []
                }
                options[key].push(rec.data[key])
            }
        });

        // Create a store for each field, filled with the unique options
        for(var key in options){
            options[key] = Ext.Array.unique(options[key]);
            var store_data = []
            Ext.each(options[key], function(unique_val){
                var disp = Ext.isEmpty(unique_val) ? '&lt;Empty Field&gt;' : unique_val;
                store_data.push({'val': unique_val, 'display': disp})
            });
            options[key] = Ext.create('Ext.data.Store', {
                model: 'ReeBill.model.MergeModel',
                proxy: 'memory',
                data : store_data
            });
        }

        // Create a grid in memory in order to copy data labels
        var grid = Ext.create(this.basedOn);
        var fields = [];
        Ext.each(grid.columns, function(col){
            // Exclude all columns that are not defined in the Record Model
            // or columns which are specifically excluded
            if(options[col.dataIndex] === undefined ||
                Ext.Array.contains(me.exclude, col.dataIndex)){
                return
            }

            if(options[col.dataIndex].count() > 1) {
                fields.push({
                    xtype: 'combo',
                    fieldLabel: col.text,
                    store: options[col.dataIndex],
                    queryMode: 'local',
                    forceSelection: true,
                    displayField: 'display',
                    valueField: 'val',
                    triggerAction: 'all',
                    margin: 10,
                    name: col.dataIndex,
                    value: options[col.dataIndex].getAt(0).get('val')
                });
            }else{
                fields.push({
                    xtype: 'displayfield',
                    margin: 10,
                    fieldLabel: col.text,
                    value: options[col.dataIndex].getAt(0).get('display')
                });
                fields.push({
                    xtype: 'hidden',
                    name: col.dataIndex,
                    value: options[col.dataIndex].getAt(0).get('val')
                });
            }
        });

        this.items= [
            Ext.create('Ext.form.Panel',{
                bodyStyle:'padding:5px 5px 0',
                fieldDefaults: {
                    msgTarget: 'side',
                    labelWidth: 150
                },
                defaults: {
                    anchor: '100%'
                },
                items: fields,
                buttons: [{
                    text: 'Merge',
                    handler: function(){
                        // Update the first record to match the merge
                        me.records[0].set(this.up('form').getValues());
                        var account_ids = []
                        for(var i=1; i < me.records.length; i++) {
                            account_ids.push(me.records[i].data['utility_account_id']);
                        }
                        me.records[0].set({'accounts_deleted': account_ids})

                        // Delete all others
                        for(var i=1; i < me.records.length; i++){
                            me.store.remove(me.records[i]);
                        }

                        // Cleanup
                        me.hide();
                        Ext.defer(function(){
                            this.close()
                        }, 10000, me);
                    }
                },{
                    text: 'Cancel',
                    handler:function(){
                        me.close();
                    }
                }]
            })
        ];

        this.callParent();
    }
});
