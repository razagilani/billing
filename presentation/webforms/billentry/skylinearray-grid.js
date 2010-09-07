/*!
 * Ext JS Library 3.2.1
 * Copyright(c) 2006-2010 Ext JS, Inc.
 * licensing@extjs.com
 * http://www.extjs.com/license
 */
var myData = "";

//stopped here - figure out how to save store
var store;
Ext.onReady(function(){

    // NOTE: This is an example showing simple state management. During development,
    // it is generally best to disable state management as dynamically-generated ids
    // can change across page loads, leading to unpredictable results.  The developer
    // should ensure that stable state ids are set for stateful components in real apps.    
    //Ext.state.Manager.setProvider(new Ext.state.CookieProvider());


    // flatten xml representation to an array
    myData = [
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

    store = new Ext.data.GroupingStore({
            reader: reader,
            data: myData,
            sortInfo:{field: 'chargegroup', direction: "ASC"},
            groupField:'chargegroup'
        });

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
                header: 'Quantity Units',
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
                header: 'Rate Units',
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
        colModel: colModel,
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
        clicksToEdit: 1
        // config options for stateful behavior
        //stateful: true,
        //stateId: 'grid' 
    });
    
    // render the grid to the specified div in the page
    grid.render('grid-example');

});
