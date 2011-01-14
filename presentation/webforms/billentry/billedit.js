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

    var billPeriodsForm = new Ext.FormPanel(
    {
        labelWidth: 125,
        frame: true,
        title: 'test Begin Date',
        bodyStyle:'padding:5px 5px 0',
        width: 350,
        defaults: {width: 175},
        items: [
            new Ext.form.DateField({
                fieldLabel: 'test Service: Electric',
                name: 'Electric',
                value: '01/02/03'
            }),
        ]
    });

    // dynamically create the period forms when a bill is loaded
    function configureBeginPeriods(beginPeriods)
    {
        billPeriodsForm.removeAll();

        beginPeriods.forEach(
            function (value, index, array) {
                billPeriodsForm.add(
                    new Ext.form.DateField({
                        fieldLabel: value.service + ' Service',
                        name: value.service,
                        value: value.begindate,
                    })
                )
            }
        );

        billPeriodsForm.doLayout();
    }




    // initial data loaded into the grid before a bill is loaded
    // populate with data if initial pre-loaded data is desired
    var initialBillData = [
        //['Charge Group 1', 'Charge Description',100,'qty units', 10,'rate units',1000],
    ];

    var reader = new Ext.data.ArrayReader({}, [
       {name: 'chargegroup'},
       {name: 'description'},
       {name: 'quantity'},
       {name: 'quantityunits'},
       {name: 'rate'},
       {name: 'rateunits'},
       {name: 'total', type: 'float'},
       {name: 'processingnote'},
       {name: 'autototal', type: 'float'}
    ]);

    var store = new Ext.data.GroupingStore({
            reader: reader,
            data: initialBillData,
            sortInfo:{field: 'chargegroup', direction: 'ASC'},
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


    // create the Grid
    var grid = new Ext.grid.EditorGridPanel({
        tbar: [{
            // ref places a name for this component into the grid so it may be referenced as grid.insertBtn...
            ref: '../insertBtn',
            iconCls: 'icon-user-add',
            text: 'Insert',
            disabled: true,
            handler: function()
            {
                grid.stopEditing();

                // grab the current selection - only one row may be selected per singlselect configuration
                var selection = grid.getSelectionModel().getSelected();

                // make the new record
                var ChargeItemType = grid.getStore().recordType;
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
                var insertionPoint = store.indexOf(selection);
                store.insert(insertionPoint + 1, c);
                grid.getView().refresh();
                grid.getSelectionModel().selectRow(insertionPoint);
                grid.startEditing(insertionPoint +1,1);
                
                // An inserted record must be saved 
                grid.saveBtn.setDisabled(false);
            }
        },{
            // ref places a name for this component into the grid so it may be referenced as grid.removeBtn...
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
                grid.saveBtn.setDisabled(false);
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
                grid.saveBtn.setDisabled(true);

                // stop grid editing so that widgets like comboboxes in rows don't stay focused
                grid.stopEditing();

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
        height: 900,
        width: 1000,
        title: 'Actual Charges',
        clicksToEdit: 2
        // config options for stateful behavior
        //stateful: true,
        //stateId: 'grid' 
    });

    // selection callbacks
    grid.getSelectionModel().on('selectionchange', function(sm){
        // if a selection is made, allow it to be removed
        // if the selection was deselected to nothing, allow no 
        // records to be removed.
        grid.removeBtn.setDisabled(sm.getCount() < 1);

        // if there was a selection, allow an insertion
        grid.insertBtn.setDisabled(sm.getCount()<1);

    });
  
    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    store.on('update', function(){
        grid.saveBtn.setDisabled(false);
    });
    
    // configure bill period objects

    // get all utility service period starts and make widgets

    // 





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
        /*            new Ext.FormPanel({
                        labelWidth: 125,
                        frame: true,
                        title: 'test Begin Date',
                        bodyStyle:'padding:5px 5px 0',
                        width: 350,
                        defaults: {width: 175},
                        items: [{
                            fieldLabel: 'test Service: Electric',
                            xtype: 'datefield',
                            name: 'Electric',
                            value: '01/02/03'
                        }]
                    })
               */ billPeriodsForm ]
            },{
                title: 'Charge Items',
                xtype: 'panel',
                layout: 'fit',
                items: [
                  grid
                ]
              }
            ]
          }
        ]
      }
    )


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
        actualCharges = billXML2Array(data.responseXML);

        // get all of the utility bill periods for each service
        beginPeriods = utilbillPeriodBegins(data.responseXML);
        configureBeginPeriods(beginPeriods);

        // now that we have the data in locally manageable data structures
        // tell all of the backing ui widget data stores to load the data

        // load the data into the charges backing data store
        store.loadData(actualCharges);

    }

    function billLoadFailed(data) {
        // ToDo: take corrective action
        alert("Bill loading failed");
        alert(data);
    }

    // responsible for taking all of the data in the ui widget backing stores
    // and 'deserializing' them from locally manageable data types into XML
    // which is then submitted to the restful bill db
    function saveToXML(records)
    {

        // take the records that are maintained in the store
        // and update the bill document with them.
        bill = Array2BillXML(bill, records);

        // ToDo: credentials

        if (bill != null)
        {

            Ext.Ajax.request({
                url: 'http://'+location.host+'/exist/rest/db/skyline/bills/' + customerAccountCombo.getValue() 
                    + '/' + customerBillCombo.getValue(),
                method: 'PUT',
                xmlData: bill,
                success: billSaved,
                failure: billDidNotSave,
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
        store.commitChanges();

        // disable the save button until the next edit to the grid store
        grid.saveBtn.setDisabled(true);

    }

    function billDidNotSave(data)
    {
        alert('Bill Save Failed ' + data);

        // reenable the save button because of the failed save attempt
        grid.saveBtn.setDisabled(false);
    }


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


