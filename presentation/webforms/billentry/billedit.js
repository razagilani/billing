// Configure ext js widgets and events
function renderWidgets()
{
    // global to access xml bill for saving changes
    // The DOM containing an XML representation of a bill
    var bill = null;


    // ToDo: state support for grid
    //Ext.state.Manager.setProvider(new Ext.state.CookieProvider());


    ////////////////////////////////////////////////////////////////////////////
    // Account and Bill selection tab
    //

    // set up combo box for listing the accounts
    var customerAccountRecordType = Ext.data.Record.create([
        {name: 'account', mapping: ''}
    ]);

    // Trick: the repeating record is <account> and it is directly a child of <accounts> 
    var customerAccountXMLReader = new Ext.data.XmlReader({
        record: 'account',
    }, customerAccountRecordType);

    // access the list of accounts so that a customer may be selected and their
    // bills listed
    var customerAccountStore = new Ext.data.Store({
        url: 'http://'+location.host+'/exist/rest/db/skyline/ListAccounts.xql',
        reader: customerAccountXMLReader
    });

    var customerAccountCombo = new Ext.form.ComboBox({
        store: customerAccountStore,
        displayField:'account',
        typeAhead: true,
        triggerAction: 'all',
        emptyText:'Select...',
        selectOnFocus:true,
    });

    // set up combo box for listing the bills
    var customerBillRecordType = Ext.data.Record.create([
        {name: 'bill', mapping: ''}
    ]);

    var customerBillXMLReader = new Ext.data.XmlReader({
        record: 'bill',
    }, customerBillRecordType);


    // access the list of bills for a customer that has been previously selected.
    var customerBillStore = new Ext.data.Store({
        url: 'http://'+location.host+'/exist/rest/db/skyline/ListBills.xql',
        reader: customerBillXMLReader
    });

    var customerBillCombo = new Ext.form.ComboBox({
        store: customerBillStore,
        displayField:'bill',
        typeAhead: true,
        triggerAction: 'all',
        emptyText:'Select...',
        selectOnFocus:true,
    });

    // event to link the account to the bill combo box
    customerAccountCombo.on('select', function(combobox, record, index) {
        customerBillStore.setBaseParam('id', record.data.account);
        customerBillStore.load();
    });

    // fired when the customer bill combo box is selected
    // because a customer account and bill has been selected, load 
    // the bill document.  Follow billLoaded() for additional details
    // ToDo: do not allow selection change if store is unsaved
    customerBillCombo.on('select', function(combobox, record, index) {

        // loads a bill from eXistDB
        Ext.Ajax.request({
            url: 'http://'+location.host+'/exist/rest/db/skyline/bills/' + customerAccountCombo.getValue() 
                + '/' + record.data.bill,
           success: billLoaded,
           failure: billLoadFailed,
           disableCaching: true,
        });
    });

    ////////////////////////////////////////////////////////////////////////////
    // Bill Period tab
    //

    // create a panel to which we can dynamically add/remove components
    // this panel is later added to the viewport so that it may be rendered

    var ubPeriodsFormPanel = new Ext.FormPanel(
    {
        header: false,
        //labelWidth: 125,
        //frame: true,
        //title: 'test Begin Date',
        //bodyStyle:'padding:5px 5px 0',
        //width: 350,
        //defaults: {width: 175},
        items:[], // added by configureUBPeriodsForm()
        //autoDestroy: true,
        //footer: true,
        layout: 'form',
        buttons: 
        [
            {
                text   : 'Save',
                handler: function() {
                    if (ubPeriodsFormPanel.getForm().isValid()) {

                        // extract values from form, and reconstruct
                        // array to go back into xml-bind.js

                        // save values to bill document
                        setUBPeriods(bill, ubPeriodsFormPanel.getForm().getFieldValues());

                        // send bill document to server
                        saveToXML(billSaved, billDidNotSave);
                    }
                }
            },{
                text   : 'Reset',
                handler: function() {
                    ubPeriodsFormPanel.getForm().reset();
                }
            }
        ]
    });

    // dynamically create the period form fields when a bill is loaded
    function configureUBPeriodsForm(beginPeriods)
    {
        ubPeriodsFormPanel.removeAll();

        // add the period date pickers to the form
        beginPeriods.forEach(
            function (value, index, array) {
                ubPeriodsFormPanel.add(
                    new Ext.form.DateField({
                        fieldLabel: value.service + ' Service Begin',
                        name: 'billperiodbegin-'+value.service,
                        value: value.begindate,
                        disabled: true,
                    }),
                    new Ext.form.DateField({
                        fieldLabel: value.service + ' Service End',
                        name: 'billperiodend-'+value.service,
                        value: value.enddate,
                    })
                )
            }
        );

        // the tabpanel that contains ubPeriodsFormPanel performs layoutOnTabChange:
        // so the dynamically added forms draw properly

    }

    ////////////////////////////////////////////////////////////////////////////
    // Measured Usage tab
    //

    // create a panel to which we can dynamically add/remove components
    // this panel is later added to the viewport so that it may be rendered

    var ubMeasuredUsageFormPanel = new Ext.FormPanel(
    {
        header: false,
        //labelWidth: 125,
        //frame: true,
        //title: 'test Begin Date',
        //bodyStyle:'padding:5px 5px 0',
        //width: 350,
        //defaults: {width: 175},
        items:[], // added by configureUBMeasuredUsageForm()
        //autoDestroy: true,
        //footer: true,
        layout: 'form',
        buttons: 
        [
            {
                text   : 'Save',
                handler: function() {
                    if (ubMeasuredUsageFormPanel.getForm().isValid()) {

                        // extract values from form, and reconstruct
                        // array to go back into xml-bind.js

                        // save values to bill document
                        setUBMeasuredUsage(bill, ubMeasuredUsageFormPanel.getForm().getFieldValues());

                        // send bill document to server
                        saveToXML(billSaved, billDidNotSave);
                    }
                }
            },{
                text   : 'Reset',
                handler: function() {
                    ubMeasuredUsageFormPanel.getForm().reset();
                }
            }
        ]
    });

    // dynamically create the measured usage form fields when a bill is loaded
    function configureUBMeasuredUsagePeriodsForm(measuredUsagePeriods)
    {
        ubMeasuredUsageFormPanel.removeAll();

        // add the period date pickers to the form
        measuredUsagePeriods.forEach(
            function (value, index, array) {
                ubMeasuredUsageFormPanel.add(
                    new Ext.form.DateField({
                        fieldLabel: value.service + ' Prior Read Date',
                        name: 'priorreaddate-'+value.service,
                        value: value.priorreaddate,
                        disabled: true,
                    }),
                    new Ext.form.DateField({
                        fieldLabel: value.service + ' Present Read Date',
                        name: 'presentreaddate-'+value.service,
                        value: value.presentreaddate,
                    })
                )
            }
        );

        // the tabpanel that contains this form panel performs layoutOnTabChange:
        // so the dynamically added form fields draw properly

    }


    ////////////////////////////////////////////////////////////////////////////
    // Charges tab
    //

    /////////////////////////////////
    // support for the actual charges

    // initial data loaded into the grid before a bill is loaded
    // populate with data if initial pre-loaded data is desired
    var initialActualCharges = [
        //['Charge Group 1', 'Charge Description',100,'qty units', 10,'rate units',1000],
    ];

    var aChargesReader = new Ext.data.ArrayReader({}, [
       {name: 'chargegroup'},
       {name: 'rsbinding'},
       {name: 'description'},
       {name: 'quantity'},
       {name: 'quantityunits'},
       {name: 'rate'},
       {name: 'rateunits'},
       {name: 'total', type: 'float'},
       {name: 'processingnote'},
       {name: 'autototal', type: 'float'}
    ]);

    var aChargesStore = new Ext.data.GroupingStore({
            reader: aChargesReader,
            data: initialActualCharges,
            sortInfo:{field: 'chargegroup', direction: 'ASC'},
            groupField:'chargegroup'
    });


	// utilize custom extension for Group Summary
    var aChargesSummary = new Ext.ux.grid.GroupSummary();

    var aChargesColModel = new Ext.grid.ColumnModel(
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
                header: 'RS Binding',
                width: 75,
                sortable: true,
                dataIndex: 'rsbinding',
                editor: new Ext.form.TextField({allowBlank: true})
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
                editor: new Ext.form.NumberField({decimalPrecision: 5, allowBlank: true})
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
                        data: [['dollars'], ['kWh'], ['ccf'], ['Therms'], ['kWD'], ['KQH'], ['rkVA']]
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
                editor: new Ext.form.NumberField({decimalPrecision: 10, allowBlank: true})
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
                align: 'right',
                renderer: function(v, params, record)
                {
                    // terrible hack allowing percentages to display as x%
                    // yet participate as a value between 0 and 1 for
                    // showing that charge items compute
                    var q = record.data.quantity;
                    var r = record.data.rate;

                    if (r && record.data.quantityunits && record.data.rateunits == 'percent')
                        r /= 100;

                    if (q && r)
                        record.data.autototal = q * r;
                    else if (q && !r)
                        record.data.autototal = record.data.total;
                    else if (!q && r)
                        record.data.autototal = record.data.total;
                    else
                        record.data.autototal = record.data.total;

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


    // create actual charges Grid
    var aChargesGrid = new Ext.grid.EditorGridPanel({
        tbar: [{
            // ref places a name for this component into the grid so it may be referenced as aChargesGrid.insertBtn...
            ref: '../insertBtn',
            iconCls: 'icon-user-add',
            text: 'Insert',
            disabled: true,
            handler: function()
            {
                aChargesGrid.stopEditing();

                // grab the current selection - only one row may be selected per singlselect configuration
                var selection = aChargesGrid.getSelectionModel().getSelected();

                // make the new record
                var ChargeItemType = aChargesGrid.getStore().recordType;
                var defaultData = 
                {
                    // ok, this is tricky:  the newly created record is assigned the chargegroup
                    // of the selection during the insert.  This way, the new record is added
                    // to the proper group.  Otherwise, if the record does not have the same
                    // chargegroup name of the adjacent record, a new group is shown in the grid
                    // and the UI goes out of sync.  Try this by change the chargegroup below
                    // to some other string.
                    chargegroup: selection.data.chargegroup,
                    description: 'enter description',
                    quantity: 0,
                    quantityunits: 'kWh',
                    rate: 0,
                    rateunits: 'dollars',
                    total: 0,
                    //autototal: 0
                };
                var c = new ChargeItemType(defaultData);
    
                // select newly inserted record
                var insertionPoint = aChargesStore.indexOf(selection);
                aChargesStore.insert(insertionPoint + 1, c);
                aChargesGrid.getView().refresh();
                aChargesGrid.getSelectionModel().selectRow(insertionPoint);
                aChargesGrid.startEditing(insertionPoint +1,1);
                
                // An inserted record must be saved 
                aChargesGrid.saveBtn.setDisabled(false);
            }
        },{
            // ref places a name for this component into the grid so it may be referenced as aChargesGrid.removeBtn...
            ref: '../removeBtn',
            iconCls: 'icon-user-delete',
            text: 'Remove',
            disabled: true,
            handler: function()
            {
                aChargesGrid.stopEditing();
                var s = aChargesGrid.getSelectionModel().getSelections();
                for(var i = 0, r; r = s[i]; i++)
                {
                    aChargesStore.remove(r);
                }
                aChargesGrid.saveBtn.setDisabled(false);
            }
        },{
            // places reference to this button in grid.  
            ref: '../saveBtn',
            text: 'Save',
            disabled: true,
            handler: function()
            {
                // disable the save button for the save attempt.
                // is there a closer place for this to the actual button click due to the possibility of a double
                // clicked button submitting two ajax requests?
                aChargesGrid.saveBtn.setDisabled(true);

                // stop grid editing so that widgets like comboboxes in rows don't stay focused
                aChargesGrid.stopEditing();

                // TODO: move this to the UI widget responsible for editing this content.
                // take the records that are maintained in the store
                // and update the bill document with them.
                setActualCharges(bill, aChargesStore.getRange());
                
                saveToXML(billSaved, billDidNotSave);
            }
        },{
            // places reference to this button in grid.  
            ref: '../copyActual',
            text: 'Copy to Hypo',
            disabled: false,
            handler: function()
            {
                // disable the save button for the save attempt.
                // is there a closer place for this to the actual button click due to the possibility of a double
                // clicked button submitting two ajax requests?
                aChargesGrid.saveBtn.setDisabled(true);

                // stop grid editing so that widgets like comboboxes in rows don't stay focused
                aChargesGrid.stopEditing();

                // take the records that are maintained in the store
                // and update the bill document with them.
                setActualCharges(bill, aChargesStore.getRange());

                saveToXML(function() {

                    // now that the bill is saved, create the hypothetical charges
                    // on the server

                    Ext.Ajax.request({
                        url: 'http://'+location.host+'/billtool/copyactual?'
                            + 'src=' + customerAccountCombo.getValue() + '/' + customerBillCombo.getValue() 
                            + '&dest=' + customerAccountCombo.getValue() + '/' + customerBillCombo.getValue(),
                        disableCaching: true,
                        success: function () {
                            // loads a bill from eXistDB
                            Ext.Ajax.request({
                                url: 'http://'+location.host+'/exist/rest/db/skyline/bills/' + customerAccountCombo.getValue() 
                                    + '/' + customerBillCombo.getValue(),
                               success: billLoaded,
                               failure: billLoadFailed,
                               disableCaching: true,
                            });
                        },
                        failure: function () {
                            alert("copy actual response fail");
                        }
                    });
                }, billDidNotSave);

            }
        }],
        colModel: aChargesColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: aChargesStore,
        enableColumnMove: false,
        view: new Ext.grid.GroupingView({
            forceFit:true,
            groupTextTpl: '{text} ({[values.rs.length]} {[values.rs.length > 1 ? "Items" : "Item"]})'
        }),
        plugins: aChargesSummary,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        autoExpandColumn: 'chargegroup',
        height: 900,
        width: 1000,
        title: 'Actual Charges',
        clicksToEdit: 2
        // config options for stateful behavior
        //stateful: true,
        //stateId: 'grid' 
    });

    // selection callbacks
    aChargesGrid.getSelectionModel().on('selectionchange', function(sm){
        // if a selection is made, allow it to be removed
        // if the selection was deselected to nothing, allow no 
        // records to be removed.
        aChargesGrid.removeBtn.setDisabled(sm.getCount() < 1);

        // if there was a selection, allow an insertion
        aChargesGrid.insertBtn.setDisabled(sm.getCount()<1);

    });
  
    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    aChargesStore.on('update', function(){
        aChargesGrid.saveBtn.setDisabled(false);
    });
    


    ///////////////////////////////////////
    // support for the hypothetical charges

    // initial data loaded into the grid before a bill is loaded
    // populate with data if initial pre-loaded data is desired
    var initialHCharges = [
        //['Charge Group 1', 'Charge Description',100,'qty units', 10,'rate units',1000],
    ];

    var hChargesReader = new Ext.data.ArrayReader({}, [
       {name: 'chargegroup'},
       {name: 'rsbinding'},
       {name: 'description'},
       {name: 'quantity'},
       {name: 'quantityunits'},
       {name: 'rate'},
       {name: 'rateunits'},
       {name: 'total', type: 'float'},
       {name: 'processingnote'},
       {name: 'autototal', type: 'float'}
    ]);

    var hChargesStore = new Ext.data.GroupingStore({
            reader: hChargesReader,
            data: initialHCharges,
            sortInfo:{field: 'chargegroup', direction: 'ASC'},
            groupField:'chargegroup'
    });


	// utilize custom extension for Group Summary
    var hChargesSummary = new Ext.ux.grid.GroupSummary();

    var hChargesColModel = new Ext.grid.ColumnModel(
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
                header: 'RS Binding',
                width: 75,
                sortable: true,
                dataIndex: 'rsbinding',
                editor: new Ext.form.TextField({allowBlank: true})
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
                editor: new Ext.form.NumberField({decimalPrecision: 5, allowBlank: true})
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
                        data: [['dollars'], ['kWh'], ['ccf'], ['Therms'], ['kWD'], ['KQH'], ['rkVA']]
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
                editor: new Ext.form.NumberField({decimalPrecision: 10, allowBlank: true})
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
                align: 'right',
                renderer: function(v, params, record)
                {
                    // terrible hack allowing percentages to display as x%
                    // yet participate as a value between 0 and 1 for
                    // showing that charge items compute
                    var q = record.data.quantity;
                    var r = record.data.rate;

                    if (r && record.data.quantityunits && record.data.rateunits == 'percent')
                        r /= 100;

                    if (q && r)
                        record.data.autototal = q * r;
                    else if (q && !r)
                        record.data.autototal = record.data.total;
                    else if (!q && r)
                        record.data.autototal = record.data.total;
                    else
                        record.data.autototal = record.data.total;

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
    );


    // create actual charges Grid
    var hChargesGrid = new Ext.grid.EditorGridPanel({
        tbar: [{
            // ref places a name for this component into the grid so it may be referenced as hChargesGrid.insertBtn...
            ref: '../insertBtn',
            iconCls: 'icon-user-add',
            text: 'Insert',
            disabled: true,
            handler: function()
            {
                hChargesGrid.stopEditing();

                // grab the current selection - only one row may be selected per singlselect configuration
                var selection = hChargesGrid.getSelectionModel().getSelected();

                // make the new record
                var ChargeItemType = hChargesGrid.getStore().recordType;
                var defaultData = 
                {
                    // ok, this is tricky:  the newly created record is assigned the chargegroup
                    // of the selection during the insert.  This way, the new record is added
                    // to the proper group.  Otherwise, if the record does not have the same
                    // chargegroup name of the adjacent record, a new group is shown in the grid
                    // and the UI goes out of sync.  Try this by change the chargegroup below
                    // to some other string.
                    chargegroup: selection.data.chargegroup,
                    description: 'enter description',
                    quantity: 0,
                    quantityunits: 'kWh',
                    rate: 0,
                    rateunits: 'dollars',
                    total: 0,
                    //autototal: 0
                };
                var c = new ChargeItemType(defaultData);
    
                // select newly inserted record
                var insertionPoint = hChargesStore.indexOf(selection);
                hChargesStore.insert(insertionPoint + 1, c);
                hChargesGrid.getView().refresh();
                hChargesGrid.getSelectionModel().selectRow(insertionPoint);
                hChargesGrid.startEditing(insertionPoint +1,1);
                
                // An inserted record must be saved 
                hChargesGrid.saveBtn.setDisabled(false);
            }
        },{
            // ref places a name for this component into the grid so it may be referenced as hChargesGrid.removeBtn...
            ref: '../removeBtn',
            iconCls: 'icon-user-delete',
            text: 'Remove',
            disabled: true,
            handler: function()
            {
                hChargesGrid.stopEditing();
                var s = hChargesGrid.getSelectionModel().getSelections();
                for(var i = 0, r; r = s[i]; i++)
                {
                    hChargesStore.remove(r);
                }
                hChargesGrid.saveBtn.setDisabled(false);
            }
        },{
            // places reference to this button in grid.  
            ref: '../saveBtn',
            text: 'Save',
            disabled: true,
            handler: function()
            {
                // disable the save button for the save attempt.
                // is there a closer place for this to the actual button click due to the possibility of a double
                // clicked button submitting two ajax requests?
                hChargesGrid.saveBtn.setDisabled(true);

                // stop grid editing so that widgets like comboboxes in rows don't stay focused
                hChargesGrid.stopEditing();

                // TODO: move this to the UI widget responsible for editing this content.
                // take the records that are maintained in the store
                // and update the bill document with them.
                setHypotheticalCharges(bill, hChargesStore.getRange());
                
                saveToXML(billSaved, billDidNotSave);
            }
        }],
        colModel: hChargesColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: hChargesStore,
        enableColumnMove: false,
        view: new Ext.grid.GroupingView({
            forceFit:true,
            groupTextTpl: '{text} ({[values.rs.length]} {[values.rs.length > 1 ? "Items" : "Item"]})'
        }),
        plugins: hChargesSummary,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        autoExpandColumn: 'chargegroup',
        height: 900,
        width: 1000,
        title: 'Hypothetical Charges',
        clicksToEdit: 2
        // config options for stateful behavior
        //stateful: true,
        //stateId: 'grid' 
    });

    // selection callbacks
    hChargesGrid.getSelectionModel().on('selectionchange', function(sm){
        // if a selection is made, allow it to be removed
        // if the selection was deselected to nothing, allow no 
        // records to be removed.
        hChargesGrid.removeBtn.setDisabled(sm.getCount() < 1);

        // if there was a selection, allow an insertion
        hChargesGrid.insertBtn.setDisabled(sm.getCount()<1);

    });
  
    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    hChargesStore.on('update', function(){
        hChargesGrid.saveBtn.setDisabled(false);
    });



    // end of tab widgets
    ////////////////////////////////////////////////////////////////////////////
    ////////////////////////////////////////////////////////////////////////////


    // assemble all of the widgets in a tabpanel with a header section
    var viewport = new Ext.Viewport
    (
      {
        layout: 'border',
        items: [
          {
            region: 'north',
            border: false,
            xtype: 'panel',
            layout: 'fit',
            height: 60,
            layoutConfig:
            {
              border: false,
            },
            autoLoad: {url:'header', scripts:true},
          },{
            region: 'center',
            xtype: 'tabpanel',
            activeTab: 0,
            // necessary for child FormPanels to draw properly when dynamically changed
            layoutOnTabChange: true,
            items:[
              {
                title: 'Select Bill',
                xtype: 'panel',
                //layout: 'fit',
                items: [
                  customerAccountCombo,
                  customerBillCombo
                ],
              },{
                title: 'Bill Periods',
                xtype: 'panel',
                layout: 'fit',
                items: [
                    ubPeriodsFormPanel
                ]
            },{
                title: 'Usage Periods',
                xtype: 'panel',
                layout: 'fit',
                items: [
                    ubMeasuredUsageFormPanel
                ]
            },{
                title: 'Charge Items',
                xtype: 'panel',
                layout: 'accordion',
                items: [
                  aChargesGrid,
                  hChargesGrid
                ]
              }
            ]
          }
        ]
      }
    );

    // TODO: move these functions to a separate file for organization purposes
    // also consider what to do about the Ext.data.Stores and where they should
    // go since they hit the web for data.

    // Functions that handle the loading and saving of bill xml 
    // using the restful interface of eXist DB


    // responsible for initializing all ui widget backing stores
    // called due to customerBillCombo.on() select event (see above)
    function billLoaded(data) {

        // set the bill document to a global so that it may always be referenced
        bill = data.responseXML;

        // 'deserialize' the bill data from XML into locally manageable data structures
        
        // flatten the actual charges found in the bill
        // ToDo: do this on a per service basis
        actualCharges = getActualCharges(bill);
        hypotheticalCharges = getHypotheticalCharges(bill);

        // get all of the utility bill periods for each service
        ubPeriods = getUBPeriods(bill);
        configureUBPeriodsForm(ubPeriods);

        // get the measured usage dates for each service
        ubMeasuredUsagePeriods = getUBMeasuredUsagePeriods(bill);
        configureUBMeasuredUsagePeriodsForm(ubMeasuredUsagePeriods);

        // now that we have the data in locally manageable data structures
        // tell all of the backing ui widget data stores to load the data

        // load the data into the charges backing data store
        aChargesStore.loadData(actualCharges);
        hChargesStore.loadData(hypotheticalCharges);

    }

    function billLoadFailed(data) {
        // ToDo: take corrective action
        alert("Bill loading failed");
        alert(data);
    }

    // the UI widgets are responsible for getting/setting data from the bill document.
    // This methods is reponsible for the restful communication of the bill doc
    // back to the server.
    function saveToXML(successCallback, failCallback)
    {
        // ToDo: credentials

        if (bill != null)
        {

            Ext.Ajax.request({
                url: 'http://'+location.host+'/exist/rest/db/skyline/bills/' + customerAccountCombo.getValue() 
                    + '/' + customerBillCombo.getValue(),
                method: 'PUT',
                xmlData: bill,
                success: successCallback,
                failure: failCallback,
            });
            /* Seeing this bug in your FF console?
             *   Error: no element found
             *   Source File: http://tyrell/exist/rest/db/skyline/bills/00000/3.xml
             *   Line: 1
             * eXistDB returns no entity in the response body for PUTs
             * Per http://www.w3.org/TR/XMLHttpRequest, the browser should handle this.
             * FF does not.  
             * http://www.sencha.com/forum/showthread.php?78777-CLOSED-3.0.1-Ext.Ajax.request-causes-firefox-error-when-no-entity-returned
             * https://bugzilla.mozilla.org/show_bug.cgi?id=521301
             */
        } else alert('No bill to save');
    }

    function billSaved(data)
    {
        // successful PUT of bill to eXistDB.  Deflag the red dirty markers on grid
        aChargesStore.commitChanges();
        hChargesStore.commitChanges();

        // disable the save button until the next edit to the grid store
        aChargesGrid.saveBtn.setDisabled(true);
        hChargesGrid.saveBtn.setDisabled(true);

    }

    function billDidNotSave(data)
    {
        alert('Bill Save Failed ' + data);

        // reenable the save button because of the failed save attempt
        aChargesGrid.saveBtn.setDisabled(false);
        hChargesGrid.saveBtn.setDisabled(false);
    }


}



// TODO: move this code to an area adjacent to the grid
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
