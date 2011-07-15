// Configure ext js widgets and events
function renderWidgets()
{
    // global to access xml bill for saving changes
    // The DOM containing an XML representation of a bill
    var bill = null;

    // global ajax timeout
    Ext.Ajax.timeout = 960000; //16 minutes

    // ToDo: state support for grid
    //Ext.state.Manager.setProvider(new Ext.state.CookieProvider());

    // set a variety of patterns for Date Pickers
    Date.patterns = {
        ISO8601Long:"Y-m-d H:i:s",
        ISO8601Short:"Y-m-d",
        ShortDate: "n/j/Y",
        LongDate: "l, F d, Y",
        FullDateTime: "l, F d, Y g:i:s A",
        MonthDay: "F d",
        ShortTime: "g:i A",
        LongTime: "g:i:s A",
        SortableDateTime: "Y-m-d\\TH:i:s",
        UniversalSortableDateTime: "Y-m-d H:i:sO",
        YearMonth: "F, Y"
    };

    ////////////////////////////////////////////////////////////////////////////
    // Upload tab
    //
    //
    
    // box to display bill images
    var NO_UTILBILL_SELECTED_MESSAGE = '<div style="position:absolute; top:30%;"><table style="width: 100%;"><tr><td style="text-align: center;"><img src="select_utilbill.png"/></td></tr></table></div>';
    var NO_REEBILL_SELECTED_MESSAGE = '<div style="position:absolute; top:30%;"><table style="width: 100%;"><tr><td style="text-align: center;"><img src="select_reebill.png"/></td></tr></table></div>';
    var utilBillImageBox = new Ext.Panel({
        collapsible: true,
        // content is initially just a message saying no image is selected
        // (will be replaced with an image when the user chooses a bill)
        html: {tag: 'div', id: 'utilbillimagebox', children: [{tag: 'div', html: NO_UTILBILL_SELECTED_MESSAGE,
            id: 'utilbillimage'}] },
        autoScroll: true,
        region: 'west',
        width: 600,
    });
    var reeBillImageBox = new Ext.Panel({
        collapsible: true,
        // content is initially just a message saying no image is selected
        // (will be replaced with an image when the user chooses a bill)
        html: {tag: 'div', id: 'reebillimagebox', children: [{tag: 'div', html: NO_REEBILL_SELECTED_MESSAGE,
            id: 'reebillimage'}] },
        autoScroll: true,
        region: 'east',
        width: 600,
    });

    // account field
    var upload_account = new Ext.form.TextField({
        fieldLabel: 'Account',
            name: 'account',
            width: 200,
            allowBlank: false,
    });
    // date fields
    var upload_begin_date = new Ext.form.DateField({
        fieldLabel: 'Begin Date',
            name: 'begin_date',
            width: 90,
            allowBlank: false,
            format: 'Y-m-d'
    });
    var upload_end_date = new Ext.form.DateField({
        fieldLabel: 'End Date',
            name: 'end_date',
            width: 90,
            allowBlank: false,
            format: 'Y-m-d'
    });

    // buttons
    var upload_reset_button = new Ext.Button({
        text: 'Reset',
        handler: function() {this.findParentByType(Ext.form.FormPanel).getForm().reset(); }
    });
    var upload_submit_button = new Ext.Button({
        text: 'Submit',
        handler: saveForm
    });

    var upload_form_panel = new Ext.form.FormPanel({
        fileUpload: true,
        title: 'Upload Bill',
        url: 'http://'+location.host+'/reebill/upload_utility_bill',
        frame:true,
        bodyStyle: 'padding: 10px 10px 0 10px;',
        defaults: {
            anchor: '95%',
            allowBlank: false,
            msgTarget: 'side'
        },

        items: [
            upload_account,
            upload_begin_date,
            upload_end_date,
            //file_chooser - defined in FileUploadField.js
            {
                xtype: 'fileuploadfield',
                id: 'form-file',
                emptyText: 'Select a file to upload',
                name: 'file_to_upload',
                buttonText: 'Choose file...',
                buttonCfg: { width:80 }
            },
        ],

        buttons: [upload_reset_button, upload_submit_button],
    });


    // data store for paging grid
    var paging_grid_store = new Ext.data.JsonStore({
        root: 'rows',
        totalProperty: 'results',
        pageSize: 25,
        paramNames: {start: 'start', limit: 'limit'},
        autoLoad: {params:{start: 0, limit: 25}},
        fields: [
            {name: 'account'},
            {name: 'period_start', type: 'date'},
            {name: 'period_end', type: 'date'},
        ],
        url: 'http://' + location.host + '/reebill/listUtilBills',
    });
    
    // TODO maybe find a better way of dealing with date formats than this
    var paging_grid_date_format = 'Y-m-d';

    // paging grid
    var paging_grid = new Ext.grid.GridPanel({
        title:'Utility Bills',
        store: paging_grid_store,
        trackMouseOver:false,
        flex:1,
        layout: 'fit',
        //autoExpandColumn: 'account',
        
        // grid columns
        columns:[{
                id: 'account',
                header: 'Account',
                dataIndex: 'account',
                width:80,
            },
            new Ext.grid.DateColumn({
                header: 'Start Date',
                dataIndex: 'period_start',
                dateFormat: paging_grid_date_format,
            }),
            new Ext.grid.DateColumn({
                header: 'End Date',
                dataIndex: 'period_end',
                dateFormat: paging_grid_date_format,
            })
        ],
        
        // paging bar on the bottom
        bbar: new Ext.PagingToolbar({
            pageSize: 25,
            store: paging_grid_store,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No utility bills to display",
        }),
    });

    // event handler for grid double-click: show image of utility bill
    // associated with the row
    paging_grid.on('cellclick', function(grid, rowIndex, columnIndex, e) {
        var record = grid.getStore().getAt(rowIndex);
        var fieldName = grid.getColumnModel().getDataIndex(columnIndex);
        var data = record.get(fieldName);
        account = record.get('account');
        begin_date_string = record.get('period_start');
        end_date_string = record.get('period_end');
        
        // parse date strings--the format is determined by the JSONDataStore's
        // JsonReader, but i can't figure out how to change that format, so
        // it's horrible: e.g. "Mon Dec 07 2009 00:00:00 GMT-0500 (EST)"
        // (built-in JS date constructor automatically detects the format)
        var parsed_begin_date = new Date(begin_date_string);
        var parsed_end_date = new Date(end_date_string);

        // convert the parsed date into a string in the format expected by the back end
        var formatted_begin_date_string = parsed_begin_date.format('Y-m-d');
        var formatted_end_date_string = parsed_end_date.format('Y-m-d');

        // url for getting bill images (calls bill_tool_bridge.getBillImage())
        theUrl = 'http://' + location.host + '/reebill/getUtilBillImage';
        
        // ajax call to generate image, get the name of it, and display it in a
        // new window
        Ext.Ajax.request({
            url: theUrl,
            params: {account: account, begin_date: formatted_begin_date_string,
                end_date: formatted_end_date_string},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false) {
                        Ext.MessageBox.alert('Server Error',
                            jsonData.errors.reason + " "
                            + jsonData.errors.details);
                        // replace bill image with a message instead
                        Ext.DomHelper.overwrite('utilbillimagebox', {tag: 'div',
                            html: NO_UTILBILL_SELECTED_MESSAGE, id: 'utilbillimage'}, true);
                    } else {
                        // show image in utilbillimageBox
                        Ext.DomHelper.overwrite('utilbillimagebox', {tag: 'img',
                            src: 'http://' + location.host + '/utilitybillimages/' 
                            + jsonData.imageName, width: '100%', id: 'utilbillimage'}, true);
                    } 
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', err);
                }
            },
            // this is called when the server returns 500 as well as when there's no response
            failure: function() { Ext.MessageBox.alert('Ajax failure', theUrl); },
            disableCaching: true,
        });

    });


          
    // is it better to get account and dates from the data store or the actual text
    // of the grid cells? i think the former.

    ////////////////////////////////////////////////////////////////////////////
    // Account and Bill selection tab
    //


    var accountsStore = new Ext.data.JsonStore({
        // store configs
        autoDestroy: true,
        autoLoad:false,
        url: 'http://'+location.host+'/reebill/listAccounts',
        storeId: 'accountsStore',
        root: 'rows',
        idProperty: 'account',
        fields: ['account', 'name'],
    });

    var accountCombo = new Ext.form.ComboBox({
        store: accountsStore,
        displayField:'name',
        valueField:'account',
        typeAhead: true,
        triggerAction: 'all',
        emptyText:'Select...',
        // TODO: seems to have no effect. investigate.
        //resizeable: true,
        width: 350,
        selectOnFocus:true,
    });

    var sequencesStore = new Ext.data.JsonStore({
        // store configs
        autoDestroy: true,
        autoLoad:false,
        url: 'http://'+location.host+'/reebill/listSequences',
        storeId: 'sequencesStore',
        root: 'rows',
        idProperty: 'sequence',
        fields: ['sequence'],
    });

    var sequenceCombo = new Ext.form.ComboBox({
        store: sequencesStore,
        displayField:'sequence',
        typeAhead: true,
        triggerAction: 'all',
        emptyText:'Select...',
        width: 350,
        selectOnFocus:true,
    });

    // event to link the account to the bill combo box
    accountCombo.on('select', function(combobox, record, index) {
        sequencesStore.setBaseParam('account', record.data.account);
        sequencesStore.load();
    });

    // fired when the customer bill combo box is selected
    // because a customer account and bill has been selected, load 
    // the bill document.  Follow configureWidgets() for additional details
    // ToDo: do not allow selection change if store is unsaved
    sequenceCombo.on('select', function(combobox, record, index) {
        configureWidgets();
    });

    // a hack so that a newly rolled bill may be accessed by directly entering its sequence
    // remove this when https://www.pivotaltracker.com/story/show/14564121 completes
    sequenceCombo.on('specialkey', function(field, e) {
        if (e.getKey() == e.ENTER) {
            configureWidgets();
        }
    });

    // forms for calling bill process operations

    var billOperationButton = new Ext.SplitButton({
        text: 'Process Bill',
        handler: allOperations, // handle a click on the button itself
        menu: new Ext.menu.Menu({
            items: [
                // these items will render as dropdown menu items when the arrow is clicked:
                {text: 'Roll Period', handler: rollOperation},
                {text: 'Bind RE&E Offset', handler: bindREEOperation},
                {text: 'Bind Rate Structure', handler: bindRSOperation},
                {text: 'Calculate REPeriod', handler: calcREPeriodOperation},
                {text: 'Pay', handler: payOperation},
                {text: 'Sum', handler: sumOperation},
                {text: 'CalcStats', handler: calcStatsOperation},
                {text: 'Issue', handler: issueOperation},
                {text: 'Render', handler: renderOperation},
                {text: 'Commit', handler: commitOperation},
                {text: 'Issue to Customer', handler: issueToCustomerOperation},
            ]
        })
    });


    function successResponse(response, options) 
    {
        var o = {};
        try {
            o = Ext.decode(response.responseText);}
        catch(e) {
            alert("Could not decode JSON data");
        }
        if(true !== o.success) {
            Ext.Msg.alert('Error', o.errors.reason + o.errors.details);
        } else {
            configureWidgets();
        }
    }

    function allOperations()
    {
    }

    // refactor request object
    /*MyAjaxRequest = Ext.extend ( Ext.Ajax.request, {
         url : 'ajax.php' ,
         params : { action : 'getDate' },
         method: 'GET',
         success: function ( result, request ) {
            Ext.MessageBox.alert ('Success', 'Data return from the server: '+    result.responseText);
         },
         failure: function ( result, request) {
            Ext.MessageBox.alert('Failed', result.responseText);
          }
    } ); */

    function issueToCustomerOperation()
    {
        registerAjaxEvents()
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/issueToCustomer',
            params: { 
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue()
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("Issue to customer response fail");
            }
        });
    }

    function calcStatsOperation()
    {
        registerAjaxEvents()
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/calcstats',
            params: { 
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue()
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("Calc response fail");
            }
        });
    }

    function sumOperation()
    {
        registerAjaxEvents()
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/sum',
            params: { 
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue()
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("Sum response fail");
            }
        });
    }

    function payOperation()
    {
        // modal to accept amount paid
        Ext.Msg.prompt('Amount Paid', 'Enter amount paid:', function(btn, text){
            if (btn == 'ok')
            {
                registerAjaxEvents()
                var amountPaid = parseFloat(text)

                account = accountCombo.getValue();
                sequence = sequenceCombo.getValue();

                Ext.Ajax.request({
                    url: 'http://'+location.host+'/reebill/pay',
                    params: { 
                        account: account,
                        sequence: sequence,
                        amount: amountPaid
                    },
                    disableCaching: true,
                    success: successResponse,
                });
            }
        });
    }

    function bindRSOperation()
    {
        registerAjaxEvents()
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/bindrs',
            params: { 
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue()
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("Bind RS response fail");
            }
        });
    }

    function calcREPeriodOperation()
    {
        registerAjaxEvents()
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/calc_reperiod',
            params: { 
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue()
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("Bind RS response fail");
            }
        });
    }

    function bindREEOperation()
    {

        registerAjaxEvents()
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/bindree',
            params: { 
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue()
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("Bind REE response fail");
            }
        });
    }

    function rollOperation()
    {
        registerAjaxEvents()
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/roll',
            params: { 
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue()
            },
            disableCaching: true,
            success: function (response) {
                var o = {};
                try {
                    o = Ext.decode(response.responseText);}
                catch(e) {
                    alert("Could not decode JSON data");
                }
                if(true !== o.success) {
                    Ext.Msg.alert('Error', o.errors.reason + o.errors.details);
                } else {
                    // TODO: pass these into successResponse somehow see 14945431
                    // a new sequence has been made
                    sequencesStore.load();
                    // select it
                    sequenceCombo.selectByValue((parseInt(sequence)+1), true);
                    // re configure displayed data
                    configureWidgets();
                }
            },
            failure: function () {
                alert("Roll response fail");
            }
        });
    }

    function issueOperation()
    {
        registerAjaxEvents()
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/issue',
            params: { 
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue()
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("Issue response fail");
            }
        });
    }

    function renderOperation()
    {
        registerAjaxEvents()
        Ext.Ajax.request({
            // TODO: pass in only account and sequence
            url: 'http://'+location.host+'/reebill/render',
            params: { 
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue()
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("Render response fail");
            }
        });
    }

    function commitOperation()
    {
        account = accountCombo.getValue();
        sequence = sequenceCombo.getValue();

        registerAjaxEvents();
        Ext.Ajax.request({
            // TODO: pass in only account and sequence
            url: 'http://'+location.host+'/reebill/commit',
            params: {
                account: accountCombo.getValue(),
                sequence: sequenceCombo.getValue(),
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("commit response fail");
            }
        });

    }

    ////////////////////////////////////////////////////////////////////////////
    //
    // Generic form save handler
    // 
    function saveForm() 
    {

        //http://www.sencha.com/forum/showthread.php?127087-Getting-the-right-scope-in-button-handler
        var formPanel = this.findParentByType(Ext.form.FormPanel);

        if (formPanel.getForm().isValid()) {

            formPanel.getForm().submit({
                params:{
                    // see baseParams
                }, 
                waitMsg:'Saving...',
                failure: function(form, action) {
                    switch (action.failureType) {
                        case Ext.form.Action.CLIENT_INVALID:
                            Ext.Msg.alert('Failure', 'Form fields may not be submitted with invalid values');
                            break;
                        case Ext.form.Action.CONNECT_FAILURE:
                            Ext.Msg.alert('Failure', 'Ajax communication failed');
                            break;
                        case Ext.form.Action.SERVER_INVALID:
                            Ext.Msg.alert('Failure', action.result.errors.reason + action.result.errors.details);
                        default:
                            Ext.Msg.alert('Failure', action.result.errors.reason + action.result.errors.details);
                    }
                },
                success: function(form, action) {
                    //alert(action.success);
                }
            })

        }else{
            Ext.MessageBox.alert('Errors', 'Please fix form errors noted.');
        }
    }

    //
    ////////////////////////////////////////////////////////////////////////////





    ////////////////////////////////////////////////////////////////////////////
    // Bill Period tab
    //
    // dynamically create the period forms when a bill is loaded
    //

    function configureUBPeriodsForms(account, sequence, periods)
    {
        var ubPeriodsTab = tabPanel.getItem('ubPeriodsTab');

        ubPeriodsTab.removeAll(true);

        var ubPeriodsFormPanels = [];
        
        for (var service in periods)
        {

            var ubPeriodsFormPanel = new Ext.FormPanel(
            {
                id: service + 'UBPeriodsFormPanel',
                header: false,
                url: 'http://'+location.host+'/reebill/setUBPeriod',
                border: false,
                labelWidth: 125,
                bodyStyle:'padding:10px 10px 0px 10px',
                items:[], // added by configureUBPeriodsForm()
                buttons: 
                [
                    // TODO: the save button is generic in function, refactor
                    {
                        text   : 'Save',
                        handler: saveForm
                    },{
                        text   : 'Reset',
                        handler: function() {
                            var formPanel = this.findParentByType(Ext.form.FormPanel);
                            formPanel.getForm().reset();
                        }
                    }
                ]
            });

            // add the period date pickers to the form
            ubPeriodsFormPanel.add(
                new Ext.form.DateField({
                    fieldLabel: service + ' Service Begin',
                    name: 'begin',
                    value: periods[service].begin,
                    format: 'Y-m-d'
                }),
                new Ext.form.DateField({
                    fieldLabel: service + ' Service End',
                    name: 'end',
                    value: periods[service].end,
                    format: 'Y-m-d'
                })
            );

            // add base parms for form post
            ubPeriodsFormPanel.getForm().baseParams = {account: account, sequence: sequence, service:service}

            ubPeriodsFormPanels.push(ubPeriodsFormPanel);

        }
        ubPeriodsTab.add(ubPeriodsFormPanels);
    }

    ////////////////////////////////////////////////////////////////////////////
    // Measured Usage tab
    //
    //
    // create a panel to which we can dynamically add/remove components
    // this panel is later added to the viewport so that it may be rendered


    function configureUBMeasuredUsagesForms(account, sequence, usages)
    {
        var ubMeasuredUsagesTab = tabPanel.getItem('ubMeasuredUsagesTab');

        ubMeasuredUsagesTab.removeAll(true);

        var ubMeasuredUsagesFormPanels = [];

        // for each service
        for (var service in usages)
        {
            // enumerate each meter
            usages[service].forEach(function(meter, index, array)
            {
                var meterFormPanel = new Ext.FormPanel(
                {
                    id: service +'-'+meter.identifier+'-meterReadDateFormPanel',
                    header: false,
                    url: 'http://'+location.host+'/reebill/setMeter',
                    border: false,
                    labelWidth: 125,
                    bodyStyle:'padding:10px 10px 0px 10px',
                    items:[], // added by configureUBMeasuredUsagesForm()
                    baseParams: null, // added by configureUBMeasuredUsagesForm()
                    autoDestroy: true,
                    layout: 'form',
                    buttons: 
                    [
                        // TODO: the save button is generic in function, refactor
                        {
                            text   : 'Save',
                            handler: saveForm
                        },{
                            text   : 'Reset',
                            handler: function() {
                                var formPanel = this.findParentByType(Ext.form.FormPanel);
                                formPanel.getForm().reset();
                            }
                        }
                    ]
                });

                // add the period date pickers to the form
                meterFormPanel.add(
                    new Ext.form.DateField({
                        fieldLabel: service + ' Prior Read',
                        name: 'priorreaddate',
                        value: meter.priorreaddate,
                        format: 'Y-m-d'
                    }),
                    new Ext.form.DateField({
                        fieldLabel: service + ' Present Read',
                        name: 'presentreaddate',
                        value: meter.presentreaddate,
                        format: 'Y-m-d'
                    })
                );

                // add base parms for form post
                meterFormPanel.getForm().baseParams = {account: account, sequence: sequence, service:service, meter_identifier:meter.identifier}

                ubMeasuredUsagesFormPanels.push(meterFormPanel);

                // and each register for that meter
                meter.registers.forEach(function(register, index, array) 
                {
                    if (register.shadow == false)
                    {

                        var registerFormPanel = new Ext.FormPanel(
                        {
                            id: service +'-'+meter.identifier+'-'+ register.identifier+'-meterReadDateFormPanel',
                            header: false,
                            url: 'http://'+location.host+'/reebill/setActualRegister',
                            border: false,
                            labelWidth: 125,
                            bodyStyle:'padding:10px 10px 0px 10px',
                            items:[], // added by configureUBMeasuredUsagesForm()
                            baseParams: null, // added by configureUBMeasuredUsagesForm()
                            autoDestroy: true,
                            layout: 'form',
                            buttons: 
                            [
                                // TODO: the save button is generic in function, refactor
                                {
                                    text   : 'Save',
                                    handler: saveForm
                                },{
                                    text   : 'Reset',
                                    handler: function() {
                                        var formPanel = this.findParentByType(Ext.form.FormPanel);
                                        formPanel.getForm().reset();
                                    }
                                }
                            ]
                        });

                        // add the period date pickers to the form
                        registerFormPanel.add(
                            new Ext.form.NumberField({
                                fieldLabel: register.identifier,
                                name: 'total',
                                value: register.total,
                            })
                        );

                        // add base parms for form post
                        registerFormPanel.getForm().baseParams = {account: account, sequence: sequence, service:service, meter_identifier: meter.identifier, register_identifier:register.identifier}

                        ubMeasuredUsagesFormPanels.push(registerFormPanel);
                    }

                })
            })
        }

        ubMeasuredUsagesTab.add(ubMeasuredUsagesFormPanels);
    }


    ////////////////////////////////////////////////////////////////////////////
    // Charges tab
    //


    /////////////////////////////////
    // support for the actual charges

    // initial data loaded into the grid before a bill is loaded
    // populate with data if initial pre-loaded data is desired
    var initialActualCharges = {
        rows: [
            //{chargegroup:'Distribution', rsbinding:'SOMETHING', description:'description', quantity:10, quantityunits:'kwh', rate:1, rateunits:'kwh', total:100, processingnote:'A Note'},
        ]
    };

    var aChargesReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'id',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'chargegroup', mapping: 'chargegroup'},
            {name: 'rsbinding', mapping: 'rsbinding'},
            {name: 'description', mapping: 'description'},
            {name: 'quantity', mapping: 'quantity'},
            {name: 'quantityunits', mapping: 'quantityunits'},
            {name: 'rate', mapping: 'rate'},
            {name: 'rateunits', mapping: 'rateunits'},
            {name: 'total', mapping: 'total', type: 'float'},
            {name: 'processingnote', mapping:'processingnote'},
            {name: 'autototal', mapping: 'autototal', type: 'float'}
        ]
    });
    var aChargesWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    // This proxy is only used for reading charge item records, not writing.
    // This is due to the necessity to batch upload all records. See Grid Editor save handler.
    // We leave the proxy here for loading data as well as if and when records have entity 
    // id's and row level CRUD can occur.
    var aChargesStoreProxy = new Ext.data.HttpProxy({
        method: 'GET',
        prettyUrls: false,
        // see options parameter for Ext.Ajax.request
        url: 'http://'+location.host+'/reebill/actualCharges',
        /*api: {
            // all actions except the following will use above url
            create  : '',
            update  : ''
        }*/
    });

    var aChargesStore = new Ext.data.GroupingStore({
        proxy: aChargesStoreProxy,
        autoSave: false,
        reader: aChargesReader,
        writer: aChargesWriter,
        data: initialActualCharges,
        sortInfo:{field: 'chargegroup', direction: 'ASC'},
        groupField:'chargegroup'
    });

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
    });
    var serviceComboFormPanel = new Ext.form.FormPanel({
        layout:'fit',
        width: 100,
        items: [
            new Ext.form.ComboBox({
                id: 'service_for_charges',
                triggerAction: 'all',
                store: ['Gas', 'Electric'],
                value: 'Gas',
            })
        ],
    });

    var aChargesToolbar = new Ext.Toolbar({
        items: [
            serviceComboFormPanel,
            {
                xtype: 'tbseparator'
            },{
                xtype: 'button',

                // ref places a name for this component into the grid so it may be referenced as aChargesGrid.insertBtn...
                id: 'aChargesInsertBtn',
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
                    aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(false);
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as aChargesGrid.removeBtn...
                id: 'aChargesRemoveBtn',
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
                    aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(false);
                }
            },{
                xtype:'tbseparator'
            },{
                xtype: 'button',
                // places reference to this button in grid.  
                id: 'aChargesSaveBtn',
                text: 'Save',
                disabled: true,
                handler: function()
                {
                    // disable the save button for the save attempt.
                    // is there a closer place for this to the actual button click due to the possibility of a double
                    // clicked button submitting two ajax requests?
                    aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(true);

                    // stop grid editing so that widgets like comboboxes in rows don't stay focused
                    aChargesGrid.stopEditing();

                    // OK, a little nastiness follows: We cannot rely on the underlying Store to
                    // send records back to the server because it does so intelligently: Only
                    // dirty records go back.  Unfortunately, since there is no entity id for
                    // a record (yet), all records must be returned so that ultimately an
                    // XML grove can be produced with proper document order.
                    //aChargesStore.save(); is what we want to do

                    var jsonData = Ext.encode(Ext.pluck(aChargesStore.data.items, 'data'));

                    // TODO: refactor out into globals
                    account = accountCombo.getValue();
                    sequence = sequenceCombo.getValue();

                    Ext.Ajax.request({
                        url: 'http://'+location.host+'/reebill/saveActualCharges',
                        params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence, rows: jsonData},
                        success: function() { 
                            // TODO: check success status in json package

                            // reload the store to clear dirty flags
                            aChargesStore.load({params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence}})
                        },
                        failure: function() { alert("ajax fail"); },
                    });
                }
            },{
                xtype:'tbseparator'
            },{
                xtype: 'button',
                text: 'Copy to Hypo',
                disabled: false,
                handler: function()
                {
                    // disable the save button for the save attempt.
                    // is there a closer place for this to the actual button click due to the possibility of a double
                    // clicked button submitting two ajax requests?
                    aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(true);

                    // stop grid editing so that widgets like comboboxes in rows don't stay focused
                    aChargesGrid.stopEditing();

                    // take the records that are maintained in the store
                    // and update the bill document with them.
                    //setActualCharges(bill, aChargesStore.getRange());

                    Ext.Ajax.request({
                        url: 'http://'+location.host+'/reebill/copyactual',
                        params: {account: account, sequence: sequence},
                        success: function() { 
                            // TODO: check success status in json package

                            // reload the store to clear dirty flags
                            aChargesStore.load({params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence}})
                            hChargesStore.load({params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence}})
                        },
                        failure: function() { alert("ajax fail"); },
                    });
                }
            }
        ]
    });


    var aChargesGrid = new Ext.grid.EditorGridPanel({
        tbar: aChargesToolbar,
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

    aChargesGrid.getSelectionModel().on('selectionchange', function(sm){
        // if a selection is made, allow it to be removed
        // if the selection was deselected to nothing, allow no 
        // records to be removed.

        aChargesGrid.getTopToolbar().findById('aChargesRemoveBtn').setDisabled(sm.getCount() <1);

        // if there was a selection, allow an insertion
        aChargesGrid.getTopToolbar().findById('aChargesInsertBtn').setDisabled(sm.getCount() <1);
    });
  
    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    aChargesStore.on('update', function(){
        aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(false);
    });
    


    ///////////////////////////////////////
    // support for the hypothetical charges

    // initial data loaded into the grid before a bill is loaded
    // populate with data if initial pre-loaded data is desired
    var initialHypotheticalCharges = {
        rows: [
            //{chargegroup:'Distribution', rsbinding:'SOMETHING', description:'description', quantity:10, quantityunits:'kwh', rate:1, rateunits:'kwh', total:100, processingnote:'A Note'},
        ]
    };

    var hChargesReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'id',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'chargegroup', mapping: 'chargegroup'},
            {name: 'rsbinding', mapping: 'rsbinding'},
            {name: 'description', mapping: 'description'},
            {name: 'quantity', mapping: 'quantity'},
            {name: 'quantityunits', mapping: 'quantityunits'},
            {name: 'rate', mapping: 'rate'},
            {name: 'rateunits', mapping: 'rateunits'},
            {name: 'total', mapping: 'total', type: 'float'},
            {name: 'processingnote', mapping:'processingnote'},
            {name: 'autototal', mapping: 'autototal', type: 'float'}
        ]
    });
    var hChargesWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    // This proxy is only used for reading charge item records, not writing.
    // This is due to the necessity to batch upload all records. See Grid Editor save handler.
    // We leave the proxy here for loading data as well as if and when records have entity 
    // id's and row level CRUD can occur.
    var hChargesStoreProxy = new Ext.data.HttpProxy({
        method: 'GET',
        prettyUrls: false,
        // see options parameter for Ext.Ajax.request
        url: 'http://'+location.host+'/reebill/hypotheticalCharges',
        /*api: {
            // all actions except the following will use above url
            create  : '',
            update  : ''
        }*/
    });

    var hChargesStore = new Ext.data.GroupingStore({
        proxy: hChargesStoreProxy,
        autoSave: false,
        reader: hChargesReader,
        writer: hChargesWriter,
        data: initialHypotheticalCharges,
        sortInfo:{field: 'chargegroup', direction: 'ASC'},
        groupField:'chargegroup'
    });

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
            },{
                header: 'RS Binding',
                width: 75,
                sortable: true,
                dataIndex: 'rsbinding',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Description',
                width: 75,
                sortable: true,
                dataIndex: 'description',
                editor: new Ext.form.TextField({allowBlank: false})
            },{
                header: 'Quantity',
                width: 75,
                sortable: true,
                dataIndex: 'quantity',
                editor: new Ext.form.NumberField({decimalPrecision: 5, allowBlank: true})
            },{
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
                
            },{
                header: 'Rate',
                width: 75,
                sortable: true,
                dataIndex: 'rate',
                editor: new Ext.form.NumberField({decimalPrecision: 10, allowBlank: true})
            },{
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
            },{
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
            },{
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
    });

    var hChargesToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as hChargesGrid.insertBtn...
                id: 'hChargesInsertBtn',
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
                    hChargesGrid.getTopToolbar().findById('hChargesSaveBtn').setDisabled(false);
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as hChargesGrid.removeBtn...
                id: 'hChargesRemoveBtn',
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
                    hChargesGrid.getTopToolbar().findById('hChargesSaveBtn').setDisabled(false);
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                // places reference to this button in grid.  
                id: 'hChargesSaveBtn',
                text: 'Save',
                disabled: true,
                handler: function()
                {
                    // disable the save button for the save attempt.
                    // is there a closer place for this to the actual button click due to the possibility of a double
                    // clicked button submitting two ajax requests?
                    hChargesGrid.getTopToolbar().findById('hChargesSaveBtn').setDisabled(true);

                    // stop grid editing so that widgets like comboboxes in rows don't stay focused
                    hChargesGrid.stopEditing();

                    // OK, a little nastiness follows: We cannot rely on the underlying Store to
                    // send records back to the server because it does so intelligently: Only
                    // dirty records go back.  Unfortunately, since there is no entity id for
                    // a record (yet), all records must be returned so that ultimately an
                    // XML grove can be produced with proper document order.
                    //hChargesStore.save(); is what we want to do

                    var jsonData = Ext.encode(Ext.pluck(hChargesStore.data.items, 'data'));

                    // TODO: refactor out into globals
                    account = accountCombo.getValue();
                    sequence = sequenceCombo.getValue();

                    Ext.Ajax.request({
                        url: 'http://'+location.host+'/reebill/saveHypotheticalCharges',
                        params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence, rows: jsonData},
                        success: function() { 
                            // TODO: check success status in json package

                            // reload the store to clear dirty flags
                            hChargesStore.load({params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence}})
                        },
                        failure: function() { alert("ajax fail"); },
                    });
                }
            }]
        });

    var hChargesGrid = new Ext.grid.EditorGridPanel({
        tbar: hChargesToolbar,
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

    hChargesGrid.getSelectionModel().on('selectionchange', function(sm){
        // if a selection is made, allow it to be removed
        // if the selection was deselected to nothing, allow no 
        // records to be removed.
        hChargesGrid.getTopToolbar().findById('hChargesRemoveBtn').setDisabled(sm.getCount() < 1);

        // if there was a selection, allow an insertion
        hChargesGrid.getTopToolbar().findById('hChargesInsertBtn').setDisabled(sm.getCount()<1);

    });
  
    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    hChargesStore.on('update', function(){
        hChargesGrid.getTopToolbar().findById('hChargesSaveBtn').setDisabled(false);
    });



    ///////////////////////////////////////
    // RSI Tab

    var initialRSI = {
        rows: [
            //{descriptor:'SOMETHING REALLY REALLY REALLY LONG', description:'description', quantity:'quantity', quantityunits:'quantityunits', rate:'rate', rateunits:'rateunits', roundrule:'roundrule', total:'total'},
        ]
    };

    var rsiReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'id',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'descriptor', mapping: 'descriptor'},
            {name: 'description', mapping: 'description'},
            {name: 'quantity', mapping: 'quantity'},
            {name: 'quantityunits', mapping: 'quantityunits'},
            {name: 'rate', mapping: 'rate'},
            {name: 'rateunits', mapping: 'rateunits'},
            {name: 'roundrule', mapping:'roundrule'},
            {name: 'total', mapping: 'total'},
        ]
    });
    var rsiWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    var rsiStoreProxy = new Ext.data.HttpProxy({
        method: 'GET',
        prettyUrls: false,
        // see options parameter for Ext.Ajax.request
        url: 'http://'+location.host+'/reebill/listRSIs',
        /*api: {
            // all actions except the following will use above url
            create  : '',
            update  : ''
        }*/
    });

    var rsiStore = new Ext.data.JsonStore({
        proxy: rsiStoreProxy,
        autoSave: false,
        reader: rsiReader,
        writer: rsiWriter,
        data: initialRSI,
        root: 'rows',
        fields: [
            {name: 'descriptor'},
            {name: 'description'},
            {name: 'quantity'},
            {name: 'quantityunits'},
            {name: 'rate'},
            {name: 'rateunits'},
            {name: 'roundrule'},
            {name: 'total'},
        ],
        //url: 'http://'+location.host+'/reebill/something',
    });

    var rsiColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
                header: 'RS Binding',
                sortable: true,
                dataIndex: 'descriptor',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Description',
                sortable: true,
                dataIndex: 'description',
                editor: new Ext.form.TextField({allowBlank: false})
            },{
                header: 'Quantity',
                sortable: true,
                dataIndex: 'quantity',
                editor: new Ext.form.TextField({allowBlank: false})
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'quantityunits',
                editor: new Ext.form.TextField({allowBlank: false})
            },{
                header: 'Rate',
                sortable: true,
                dataIndex: 'rate',
                editor: new Ext.form.TextField({allowBlank: false})
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'rateunits',
                editor: new Ext.form.TextField({allowBlank: false})
            },{
                header: 'Round Rule',
                sortable: true,
                dataIndex: 'roundrule',
                editor: new Ext.form.TextField({allowBlank: false})
            },{
                header: 'Total', 
                sortable: true, 
                dataIndex: 'total', 
                summaryType: 'sum',
                align: 'right',
                editor: new Ext.form.TextField({allowBlank: false})
            }
        ]
    });

    var rsiGrid = new Ext.grid.EditorGridPanel({
        colModel: rsiColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: rsiStore,
        enableColumnMove: false,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        title: 'Rate Structure',
        clicksToEdit: 2
    });

    // end of tab widgets
    ////////////////////////////////////////////////////////////////////////////

    ////////////////////////////////////////////////////////////////////////////
    // Status bar displayed at footer of every panel in the tabpanel

    var statusBar = new Ext.ux.StatusBar({
        defaultText: 'No RE Bill',
        id: 'statusbar',
        statusAlign: 'right', // the magic config
        //items: [{ text: 'A Button' }, '-', 'Plain Text', ' ', ' ']
    });

    ////////////////////////////////////////////////////////////////////////////
    // construct tabpanel for viewport

    var tabPanel = new Ext.TabPanel({
      region:'center',
      deferredRender:false,
      autoScroll: false, 
      //margins:'0 4 4 0',
      // necessary for child FormPanels to draw properly when dynamically changed
      layoutOnTabChange: true,
      activeTab: 0,
      bbar: statusBar,
      border:true,
      items:[
        {
          title: 'Upload UtilBill',
          xtype: 'panel',
          layout: 'vbox',
          layoutConfig : {
            //type : 'vbox',
            align : 'stretch',
            pack : 'start'
          },
          // utility bill image on one side, upload form & list of bills on the
          // other side (using 2 panels)
          items: [
            upload_form_panel,
            paging_grid,
          ],
        },{
          title: 'Select ReeBill',
          xtype: 'panel',
          bodyStyle:'padding:10px 10px 0px 10px',
          items: [
            accountCombo,
            sequenceCombo,
            billOperationButton
          ],
        },{
          id: 'ubPeriodsTab',
          title: 'Bill Periods',
          xtype: 'panel',
          items: null // configureUBPeriodForm set this
        },{
          id: 'ubMeasuredUsagesTab',
          title: 'Usage Periods',
          xtype: 'panel',
          items: null // configureUBMeasuredUsagesForm sets this
        },{
          title: 'Charge Items',
          xtype: 'panel',
          layout: 'accordion',
          items: [
            aChargesGrid,
            hChargesGrid,
          ]
        },{
          id: 'rsiTab',
          title: 'RSIs',
          xtype: 'panel',
          layout: 'accordion',
          items: [rsiGrid]
        }]
      });

    // end of tab widgets
    ////////////////////////////////////////////////////////////////////////////

    ////////////////////////////////////////////////////////////////////////////
    // assemble all of the widgets in a tabpanel with a header section
    var viewport = new Ext.Viewport
    (
      {
        layout: 'border',
        defaults: {
            collapsible: false,
            split: true,
            border: true,
        },
        items: [
          {
            region: 'north',
            xtype: 'panel',
            layout: 'fit',
            height: 80,
            // default overrides
            split: false,
            border: false,
            //autoLoad: {url:'green_stripe.jpg', scripts:true},
            contentEl: 'header',
          },
          utilBillImageBox,
          tabPanel,
          reeBillImageBox,
          {
            region: 'south',
            xtype: 'panel',
            layout: 'fit',
            height: 30,
            // default overrides
            split: false,
            border: false,
            //autoLoad: {url:'green_stripe.jpg', scripts:true},
            contentEl: 'footer',
          },
        ]
      }
    );

    // TODO: move these functions to a separate file for organization purposes
    // also consider what to do about the Ext.data.Stores and where they should
    // go since they hit the web for data.

    // Functions that handle the loading and saving of bill xml 
    // using the restful interface of eXist DB


    // responsible for initializing all ui widget backing stores
    // called due to sequenceCombo.on() select event (see above)
    function configureWidgets() {

        // TODO: which bill loaded? We need to look in the bill, or have the params
        // of the ajax call that loaded this bill.
        // by getting the current values out of the ui, a bug is created on the 
        // roll operation. 
        account = accountCombo.getValue();
        sequence = sequenceCombo.getValue();
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/ubPeriods',
            params: {account: account, sequence: sequence},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false)
                    {
                        Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                    } else {
                        //Ext.MessageBox.alert('Success', 'Decode of stringData OK<br />jsonData.data = ' + jsonData);
                    } 
                    configureUBPeriodsForms(account, sequence, jsonData);
                } catch (err) {
                    //Ext.MessageBox.alert('ERROR', 'Could not decode ' + jsonData);
                }
            },
            failure: function() {alert("ajax failure")},
            disableCaching: true,
        });

        // get the measured usage dates for each service
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/ubMeasuredUsages',
            params: {account: account, sequence: sequence},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false)
                    {
                        Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                    } else {
                        //Ext.MessageBox.alert('Success', 'Decode of stringData OK<br />jsonData.data = ' + jsonData);
                    } 
                    configureUBMeasuredUsagesForms(account, sequence, jsonData);
                } catch (err) {
                    //Ext.MessageBox.alert('ERROR', 'Could not decode ' + jsonData);
                }
            },
            failure: function() {alert("ajax failure")},
            disableCaching: true,
        });

        aChargesStore.load({params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence}});
        hChargesStore.load({params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence}});
        rsiStore.load({params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence}});

        var sb = Ext.getCmp('statusbar');
        sb.setStatus({
            text: account + "-" + sequence,
        });


        // url for getting bill images (calls bill_tool_bridge.getbillimage())
        reeBillImageURL = 'http://' + location.host + '/reebill/getReeBillImage';
        
        // ajax call to generate image, get the name of it, and display it in a
        // new window
        Ext.Ajax.request({
            url: reeBillImageURL,
            params: {account: account, sequence: sequence},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false) {
                        Ext.MessageBox.alert('server error',
                            jsonData.errors.reason + " "
                            + jsonData.errors.details);
                        // replace reebill image with a message instead
                        Ext.DomHelper.overwrite('reebillimagebox', {tag: 'div',
                            html: NO_REEBILL_SELECTED_MESSAGE, id: 'reebillimage'}, true);
                    } else {
                        // show image in utilbillimagebox
                        Ext.DomHelper.overwrite('reebillimagebox', {tag: 'img',
                            src: 'http://' + location.host + '/utilitybillimages/' 
                            + jsonData.imageName, width: '100%', id: 'reebillimage'}, true);
                    } 
                } catch (err) {
                    Ext.MessageBox.alert('error', err);
                }
            },
            // this is called when the server returns 500 as well as when there's no response
            failure: function() { Ext.MessageBox.alert('ajax failure', reeBillImageURL); },
            disablecaching: true,
        });
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

function showSpinner()
{
    Ext.Msg.show({title: "Please Wait...", closable: false})
}

function hideSpinner()
{
    Ext.Msg.hide()
    unregisterAjaxEvents()
}

function registerAjaxEvents()
{
    Ext.Ajax.addListener('beforerequest', this.showSpinner, this);
    Ext.Ajax.addListener('requestcomplete', this.hideSpinner, this);
    Ext.Ajax.addListener('requestexception', this.hideSpinner, this);
}
function unregisterAjaxEvents()
{
    Ext.Ajax.removeListener('beforerequest', this.showSpinner, this);
    Ext.Ajax.removeListener('requestcomplete', this.hideSpinner, this);
    Ext.Ajax.removeListener('requestexception', this.hideSpinner, this);
}
