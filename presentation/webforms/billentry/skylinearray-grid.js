function renderWidgets()
{

    //Ext.state.Manager.setProvider(new Ext.state.CookieProvider());

    // set up combo boxes

    var customerAccountRecordType = Ext.data.Record.create([
        {name: 'account', mapping: ""}
    ]);

    var customerAccountXMLReader = new Ext.data.XmlReader({
        record: 'account',
    }, customerAccountRecordType);

    var customerAccountStore = new Ext.data.Store({
        //url: 'http://skyline/exist/rest/db/skyline/bills',
        url: 'http://skyline/exist/rest/db/skyline/ListAccounts.xql',
        reader: customerAccountXMLReader
    });

    var customerAccountCombo = new Ext.form.ComboBox({
        store: customerAccountStore,
        displayField:'account',
        typeAhead: true,
        triggerAction: 'all',
        emptyText:'Select...',
        selectOnFocus:true,
        applyTo: 'customer-accounts',
    });

    customerAccountCombo.on('select', function(combobox, record, index) {
        alert(record.data.account);
    });




    // flatten xml representation to an array
    var myData = [
        ['Charge Group 1', '1 Charge Description',500,'ccf', 10,'dollars',1000],
        ['Charge Group 3', '3 Charge Description',100,'kWh', 10,'percent',1000],
        ['Charge Group 1', '1 Charge Description',100,'kWh', 10,'dollars',1000],
        ['Charge Group 1', '1 Charge Description',100,'kWh', 10,'cents',1000],
        ['Charge Group 1', '1 Charge Description',100,'ccf', 10,'percent',1000],
        ['Charge Group 2', '2 Charge Description',100,'KWD', 10,'cents',1000],
        ['Charge Group 2', '2 Charge Description',100,'qty units', 10,'rate units',1000],
        ['Charge Group 2', '2 Charge Description',100,'qty units', 10,'rate units',1000],
        ['Charge Group 2', '2 Charge Description',100,'qty units', 10,'rate units',1000],
        ['Charge Group 3', '3 Charge Description',100,'qty units', 10,'rate units',1000],
        ['Charge Group 3', '3 Charge Description',100,'qty units', 10,'rate units',1000],
        ['Charge Group 3', '3 Charge Description',100,'qty units', 10,'rate units',1000],
    ];

    var reader = new Ext.data.ArrayReader({}, [
       {name: 'chargegroup'},
       {name: 'description'},
       {name: 'quantity', type: 'float'},
       {name: 'quantityunits'},
       {name: 'rate', type: 'float'},
       {name: 'rateunits'},
       {name: 'total', type: 'float'},
       {name: 'autototal', type: 'float'}
    ]);

    var store = new Ext.data.GroupingStore({
            reader: reader,
            data: myData,
            sortInfo:{field: 'chargegroup', direction: "ASC"},
            groupField:'chargegroup'
        });


	// utilize custom extension for Group Summary
    var summary = new Ext.ux.grid.GroupSummary();

    var colModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
                id:'chargegroup',
                header: 'Charge Group',
                width: 160,
                sortable: true,
                dataIndex: 'chargegroup',
                hidden: true 
            }, 
            {
                header: 'Description',
                width: 75,
                sortable: true,
                dataIndex: 'description',
                editor: new Ext.form.TextField({allowBlank: false})
            },
            {
                header: 'Quantity',
                width: 75,
                sortable: true,
                dataIndex: 'quantity',
                editor: new Ext.form.NumberField({allowBlank: false})
            },
            {
                header: 'Units',
                width: 75,
                sortable: true,
                dataIndex: 'quantityunits',
                editor: new Ext.form.ComboBox({
                    typeAhead: true,
                    triggerAction: 'all',
                    // transform the data already specified in html
                    //transform: 'light',
                    lazyRender: true,
                    listClass: 'x-combo-list-small',
                    mode: 'local',
                    store: new Ext.data.ArrayStore({
                        fields: [
                            'displayText'
                        ],
                        // TODO: externalize these units
                        data: [['kWh'], ['ccf']]
                    }),
                    valueField: 'displayText',
                    displayField: 'displayText'
                })
                
            },
            {
                header: 'Rate',
                width: 75,
                sortable: true,
                dataIndex: 'rate',
                editor: new Ext.form.NumberField({allowBlank: false})
            },
            {
                header: 'Units',
                width: 75,
                sortable: true,
                dataIndex: 'rateunits',
                editor: new Ext.form.ComboBox({
                    typeAhead: true,
                    triggerAction: 'all',
                    // transform the data already specified in html
                    //transform: 'light',
                    lazyRender: true,
                    listClass: 'x-combo-list-small',
                    mode: 'local',
                    store: new Ext.data.ArrayStore({
                        fields: [
                            'displayText'
                        ],
                        // TODO: externalize these units
                        data: [['dollars'], ['cents']]
                    }),
                    valueField: 'displayText',
                    displayField: 'displayText'
                })
            },
            {
                header: 'Total', 
                width: 75, 
                sortable: true, 
                dataIndex: 'total', 
                summaryType: 'sum',
                align: 'right',
                editor: new Ext.form.NumberField({allowBlank: false}),
                renderer: function(v, params, record)
                {
                    return Ext.util.Format.usMoney(record.data.total);
                }
            },
            {
                header: 'Auto Total', 
                width: 75, 
                sortable: true, 
                dataIndex: 'autototal', 
                summaryType: 'sum',
                renderer: function(v, params, record)
                {
                    record.data.autototal = record.data.quantity * record.data.rate;
                    //return Ext.util.Format.usMoney(record.data.quantity * record.data.rate);
                    return Ext.util.Format.usMoney(record.data.autototal);
                },
                // figure out how to sum column based on a renderer
                summaryRenderer: function(v, params, record)
                {
                    return Ext.util.Format.usMoney(record.data.autototal);
                }
            }
        ]
    }
    )


    // create the Grid
    var grid = new Ext.grid.EditorGridPanel({
        tbar: [{
            iconCls: 'icon-user-add',
            text: 'Insert',
            handler: function()
            {
                var defaultData = 
                {
                    chargegroup: 'Charge Group 1',
                    description: 'description',
                    quantity: 15.5,
                    quantityunits: 'kWh',
                    rate: 15.5,
                    rateunits: 'dollars',
                    total: 1500.1,
                    //autototal: 0
                };
                var ChargeItemType = grid.getStore().recordType;
                var c = new ChargeItemType(defaultData);

                grid.stopEditing();
                // grab the current selection - only one row may be selected per singlselect configuration
                var selection = grid.getSelectionModel().getSelected();
                var insertionPoint = store.indexOf(selection);
                store.insert(insertionPoint + 1, c);
                grid.getView().refresh();
                grid.getSelectionModel().selectRow(insertionPoint);
                grid.startEditing(0);
            }
        },{
            ref: '../removeBtn',
            iconCls: 'icon-user-delete',
            text: 'Remove',
            disabled: true,
            handler: function()
            {
                grid.stopEditing();
                var s = grid.getSelectionModel().getSelections();
                for(var i = 0, r; r = s[i]; i++)
                {
                    store.remove(r);
                }
            }
        },{
            text: 'Save',
            handler: function()
            {
                store.commitChanges();
                saveToXML(store.getRange());
            }
        }],
        colModel: colModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: store,
        enableColumnMove: false,
        view: new Ext.grid.GroupingView({
            forceFit:true,
            groupTextTpl: '{text} ({[values.rs.length]} {[values.rs.length > 1 ? "Items" : "Item"]})'
        }),
        plugins: summary,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        autoExpandColumn: 'chargegroup',
        height: 350,
        width: 600,
        title: 'Actual Charges',
        clicksToEdit: 2
        // config options for stateful behavior
        //stateful: true,
        //stateId: 'grid' 
    });

    // selection callbacks
    grid.getSelectionModel().on('selectionchange', function(sm){
        sm.getCount();
        grid.removeBtn.setDisabled(sm.getCount() < 1);
    });
    
    
    // render the grid to the specified div in the page
    grid.render('grid-example');


}

    function saveToXML(records)
    {
       alert(records[0].data.description);
    }




/**
 * Custom function used for column renderer
 * @param {Object} val
 */
function change(val){
    if(val > 0){
        return '<span style="color:green;">' + val + '</span>';
    }else if(val < 0){
        return '<span style="color:red;">' + val + '</span>';
    }
    return val;
}

/**
 * Custom function used for column renderer
 * @param {Object} val
 */
function pctChange(val){
    if(val > 0){
        return '<span style="color:green;">' + val + '%</span>';
    }else if(val < 0){
        return '<span style="color:red;">' + val + '%</span>';
    }
    return val;
}


