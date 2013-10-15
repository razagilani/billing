// necessary for form validation messages to appear when a field's msgTarget qtip config is used
//Ext.QuickTips.init();

var DEFAULT_RESOLUTION = 100;
var DEFAULT_DIFFERENCE_THRESHOLD = 10;

/*
* Test Code.  TODO 25495769: externalize it into a separate file which can be selectively included to troubleshoot.
*/
// Ext 4 fires events when ajax is aborted
// so this is an Ext 3 workaround
/*
Ext.Ajax.addEvents({requestaborted:true});
Ext.override(Ext.data.Connection, {
    abort : function(transId){
        if(transId || this.isLoading()){
            Ext.lib.Ajax.abort(transId || this.transId);
            this.fireEvent('requestaborted', this, this.transId);
        }
    }
});
Ext.Ajax.addListener('beforerequest', function (conn, request) {
        console.log("beforerequest");
        console.log(conn);
        console.log(request);
    }, this);
Ext.Ajax.addListener('requestcomplete', function (conn, request) {
        console.log("requestcomplete");
        console.log(conn);
        console.log(request);
    }, this);
Ext.Ajax.addListener('requestexception', function (conn, request) {
        console.log("requestexception");
        console.log(conn);
        console.log(request);
    }, this);
Ext.Ajax.addListener('requestaborted', function (conn, request) {
        console.log("requestaborted");
        console.log(conn);
        console.log(request);
    }, this);
*/

/* Constructor for menus that show versions of utility bills in
 * utility-bill-editing tabs */

function reeBillReady() {
    // global declaration of account and sequence variable
    // these variables are updated by various UI's and represent
    // the current Reebill Account-Sequence being acted on
    // TODO:  Put these in ReeBill namespace?
    var selected_account = null;
    var selected_sequence = null;

    // this is a Record object in 'utilbillGridStore'
    var selected_utilbill = null;

    // handle global success:false responses
    // monitor session status and display login panel if they are not logged in.
    Ext.util.Observable.observeClass(Ext.data.Connection); 
    Ext.data.Connection.on('requestcomplete', function(dataconn, response) { 
        try {
            var jsonData = Ext.util.JSON.decode(response.responseText);
            if (typeof(jsonData.success) === "undefined") {
                console.log("Server returned malformed json reponse:  Success field missing.");
                console.log(jsonData);
            } else {
                if (jsonData.success == false) {
                    if (typeof(jsonData.code) === "undefined") {
                        console.log("Server returned malformed json reponse:  Code field missing.");
                        console.log(jsonData);
                    } else {
                        if (jsonData.code == 1) {
                            // if the loginWindow is not showing, show it. Otherwise ignore all other calls to login
                            // of which there may be many.
                            window.location.href = 'http://'+location.host+'/reebill/logout'
                        } else {
                            //console.log(jsonData);
                        }
                    }
                } else {
                    //console.log(jsonData);
                }
            }
        } catch (e) {
            console.log("Unexpected exception observing Ext.data.Connection requestcomplete:");
            console.log(e);
            Ext.MessageBox.alert("Unexpected exception observing Ext.data.Connection requestcomplete: " + e);
        }
    });

    // ToDo: 5204832 state support for grid
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
    // Utility Bill Tab
    //
    //
    
    // box to display bill images
    var utilBillImageBox = new Ext.Panel({
        collapsible: true,
        // content is initially just a message saying no image is selected
        // (will be replaced with an image when the user chooses a bill)
        html: {tag: 'div', id: 'utilbillimagebox', children: [{tag: 'div', html: NO_UTILBILL_SELECTED_MESSAGE,
            id: 'utilbillimage'}] },
        autoScroll: true,
        region: 'west',
        width: 300,
    });
    var reeBillImageBox = new Ext.Panel({
        collapsible: true,
        collapsed: true,
        // content is initially just a message saying no image is selected
        // (will be replaced with an image when the user chooses a bill)
        html: {tag: 'div', id: 'reebillimagebox', children: [{tag: 'div', html: NO_REEBILL_SELECTED_MESSAGE,
            id: 'reebillimage'}] },
        autoScroll: true,
        region: 'east',
        width: 300,
    });

    // account field
    var upload_account = new Ext.form.TextField({
        fieldLabel: 'Account',
            name: 'account',
            width: 200,
            allowBlank: false,
            readOnly: true
    });
    // service field
    var upload_service = new Ext.form.ComboBox({
        fieldLabel: 'Service',
        name: 'service',
        allowBlank: false,
        store: ['Gas', 'Electric'],
        value: 'Gas',
        width: 50,
    })
    // date fields
    var uploadStartDateField = new Ext.form.DateField({
        fieldLabel: 'Begin Date',
            name: 'begin_date',
            width: 90,
            allowBlank: false,
            format: 'Y-m-d'
    });
    var uploadEndDateField = new Ext.form.DateField({
        fieldLabel: 'End Date',
            name: 'end_date',
            width: 90,
            allowBlank: false,
            format: 'Y-m-d'
    });
    var uploadTotalChargesField = new Ext.form.NumberField({
        fieldLabel: 'Total Charges',
            name: 'total_charges',
            width: 90,
            value: 0,
    });

    // buttons
    var upload_reset_button = new Ext.Button({
        text: 'Reset',
        handler: function() {this.findParentByType(Ext.form.FormPanel).getForm().reset(); }
    });
    var upload_submit_button = new Ext.Button({
        text: 'Submit',
        handler: function(b, e) {
            //You cannot simply call saveForm, because it needs to be able to find its parent.
            //Using 'this' as the scope tells it that it is not just in an anonymus function.
            saveForm(b, e, function(b,e) {
                utilbillGrid.getBottomToolbar().doRefresh();
                uploadStartDateField.setValue(uploadEndDateField.getValue());
                uploadEndDateField.setValue("");
                uploadTotalChargesField.setValue(0);
            })
        },
    });

    var upload_form_panel = new Ext.form.FormPanel({
        fileUpload: true,
        title: 'Upload Utility Bill',
        url: 'http://'+location.host+'/reebill/upload_utility_bill',
        frame:true,
        bodyStyle: 'padding: 10px 10px 0 10px;',
        defaults: {
            anchor: '95%',
            //allowBlank: false,
            msgTarget: 'side'
        },

        items: [
            upload_account,
            upload_service,
            uploadStartDateField,
            uploadEndDateField,
            uploadTotalChargesField,
            {
                xtype: 'fileuploadfield',
                id: 'form-file',
                emptyText: 'Select a file to upload',
                name: 'file_to_upload',
                buttonText: 'Choose file...',
                buttonCfg: { width:80 },
                allowBlank: true
                //disabled: true
            },
        ],

        buttons: [upload_reset_button, upload_submit_button],
    });



    var initialutilbill =  {
        rows: [
        ]
    };

    var utilbillWriter = new Ext.data.JsonWriter({
        encode: true,
        writeAllFields: false,
    });

    var utilbillStoreDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/utilbill_grid',
    });
    utilbillStoreDataConn.autoAbort = true;
    utilbillStoreDataConn.disableCaching = true;

    var utilbillStoreProxy = new Ext.data.HttpProxy(utilbillStoreDataConn);

    var utilbillGridStore = new Ext.data.JsonStore({
        proxy: utilbillStoreProxy,
        autoSave: true,
        writer: utilbillWriter,
        baseParams: { start:0, limit: 120},
        data: initialutilbill,
        root: 'rows',
        totalProperty: 'results',
        // defaults to id? probably should explicity state it until we are ext experts
        //idProperty: 'sequence',
        fields: [
        {name: 'id'},
        {name: 'name'},
        {name: 'account'},
        {name: 'rate_structure'},
        {name: 'utility'},
        {
            name: 'period_start', 
            type: 'date',
            dateFormat: 'Y-m-d'
        },
        {   
            name: 'period_end',
            type: 'date',
            dateFormat: 'Y-m-d'
        },
        {
            name: 'total_charges',
            type: 'float'
        },
        {name: 'reebills'},
        {name: 'state'},
        {name: 'service'},
        {name: 'editable'},
        ],
    });

    utilbillGridStore.on('load', function (store, records, options) {
        // the grid is disabled before loading, reenable it when complete
        utilbillGrid.setDisabled(false);
    });

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    utilbillGridStore.on('update', function(){
        //utilbillGrid.getTopToolbar().findById('utilbillSaveBtn').setDisabled(false);
    });
    
    utilbillGridStore.on('beforesave', function() {
        // TODO: 26013493 not sure this needs to be set here - should save to last set params
        //utilbillGridStore.setBaseParam("account", selected_account);
    });
    
    // event for when the store loads, for when it is paged
    utilbillGridStore.on('beforeload', function(store, options) {

        // disable the grid before it loads
        utilbillGrid.setDisabled(true);

        // The Ext API is not clear on the relationship between options and baseParams
        // options appears to override baseParams.  Furthermore, start and limit appear
        // to be treated differently.  Need to scour the Ext source to figure this out.

        // account changed, reset the paging 
        if (store.baseParams.account && store.baseParams.account != selected_account) {
            // TODO: 26143175 start new account selection on the last page
            // reset pagination since it is a new account being loaded.
            options.params.start = 0;
        }
        options.params.account = selected_account;

        // set the current selection into the store's baseParams
        store.baseParams.account = selected_account;

    });

    utilbillGridStore.on('exception', function(dataProxy, type, action,
                options, response, arg) {
        // 54000111, removed the issue specific error logging
        //if (type == 'remote' && action == 'destroy' && response.success !=
        //        true) {
        Ext.Msg.alert('Error', response.raw.errors.reason + " " + response.raw.errors.details);
        //} else {
            // catch-all for other errors
        //    Ext.Msg.alert('Error', "utilbillGridStore error: type "+type
        //        +", action "+action+", response "+response);
        //}
    });

    var utilbillColModel = new Ext.grid.ColumnModel({
        columns:[
            {
                id: 'name',
                header: 'Name',
                dataIndex: 'name',
                hidden: true,
            },
            {
                id: 'service',
                header: 'Service',
                dataIndex: 'service',
                editable: true,
                editor: new Ext.form.TextField({}),
                width: 70,
            },
            new Ext.grid.DateColumn({
                header: 'Start Date',
                dataIndex: 'period_start',
                dateFormat: 'Y-m-d',
                editable: true,
                editor: new Ext.form.DateField({allowBlank: false, format: 'Y-m-d'}),
                width: 70
            }),
            new Ext.grid.DateColumn({
                header: 'End Date',
                dataIndex: 'period_end',
                dateFormat: 'Y-m-d',
                editable: true,
                editor: new Ext.form.DateField({allowBlank: false, format: 'Y-m-d'}),
                width: 70
            }),
            {
                id: 'total_charges',
                header: 'Total Charges',
                dataIndex: 'total_charges',
                editable: true,
                editor: new Ext.form.NumberField({allowBlank: false}),
                width: 90,
            },{
                id: 'sequence',
                header: 'Reebill Sequence/Version',
                dataIndex: 'reebills',
                width: 150,
                renderer: function(value, metaData, record, rowIndex, colIndex, store) {
                    /* assume the server returns the sequence/version
                    pairs in sorted order. Render the list of JSON objects in
                    'record.data.reebills' as sequences followed by "-" and a
                    comma-separated list of versions of that sequence, e.g.
                    "1-0,1,2 2-0". */
                    var result = '';
                    var reebills = record.data.reebills;
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
            },
            {
                id: 'state',
                header: 'State',
                dataIndex: 'state',
                width: 150,
            },
            {
                id: 'utility',
                header: 'Utility',
                dataIndex: 'utility',
                editable: true,
                editor: new Ext.form.TextField({}),
                width: 150,
            },
            {
                id: 'rate_structure',
                header: 'Rate Structure',
                dataIndex: 'rate_structure',
                editable: true,
                editor: new Ext.form.TextField({}),
            },
        ],
    });


    // put this by the other dataconnection instantiations
    var utilbillImageDataConn = new Ext.data.Connection({
        url: 'http://' + location.host + '/reebill/getUtilBillImage',
        timeout: 60000, // 1 minute
    });
    utilbillImageDataConn.autoAbort = true;
    utilbillImageDataConn.disableCaching = true;

    // in the mail tab
    var utilbillGrid = new Ext.grid.EditorGridPanel({
        flex: 1,
        tbar: new Ext.Toolbar({
            items: [{
                xtype: 'button',
                id: 'utilbillRemoveButton',
                iconCls: 'icon-delete',
                text: 'Delete',
                disabled: false,
                handler: function() {
                    //utilbillGrid.stopEditing();
                    var selections = utilbillGrid.getSelectionModel().getSelections();
                    for (var i = 0; i < selections.length; i++) {
                        utilbillGridStore.remove(selections[i]);
                    }
                  //  utilbillGridStore.reload({callback: function(records, options, success){
                  //      utilbillGrid.refresh();
                  //  }});
                }
            },
        ]
        }),
        bbar: new Ext.PagingToolbar({
            // TODO: constant
            pageSize: 25,
            store: utilbillGridStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No Utility Bills to display",
        }),
        colModel: utilbillColModel,
        //selModel: new Ext.grid.RowSelectionModel({singleSelect: false}),
        store: utilbillGridStore,
        enableColumnMove: false,
        autoExpandColumn: 'rate_structure',
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        title: 'Utility Bills',
        clicksToEdit: 2,
        selModel: new Ext.grid.RowSelectionModel({
            singleSelect: true,
            moveEditorOnEnter: false,
            listeners: {
                rowdeselect: function (selModel, index, record) {
                    selected_utilbill = null;
                    ubMeasuredUsagesPanel.setDisabled(true);
                    ubRegisterGrid.setEditable(false);
                    rateStructurePanel.setDisabled(true);
                    chargeItemsPanel.setDisabled(true);
                },
                
                rowselect: function (selModel, index, record) {
                    selected_utilbill = record.data;
                    ubMeasuredUsagesPanel.setDisabled(false);
                    ubRegisterGrid.setEditable(true);
                    rateStructurePanel.setDisabled(false);
                    chargeItemsPanel.setDisabled(false);

                    // replace the records in 'ubVersionStore' with new ones,
                    // so the contents of the 3 utility bill version menus
                    // match the selected utility bill. there's always one row
                    // for the current version of the utility bill, and one row
                    // for each issued reebill version attached to it (if any)
                    records = [[null, null, null]];
                    for (var i = 0; i < selected_utilbill.reebills.length; i++) {
                        //Check that reebill associated with this version is issued
                        // otherwise there is no associated frozen utilbill
                        if (selected_utilbill.reebills[i].issue_date != null) {
                            records.push([
                                selected_utilbill.reebills[i].sequence,
                                selected_utilbill.reebills[i].version,
                                selected_utilbill.reebills[i].issue_date,
                            ]);
                        }
                    }
                    records.sort(function (a, b) {
                        if (a[2] == null) {
                            return -1;
                        }
                        if (b[2] == null) {
                            return 1;
                        }
                        if (b[2] > a[2]) {
                            return 1;
                        }
                        if (b[2] == a[2]) {
                            return 0;
                        }
                        return -1;
                    });
                    //Go through the menus and load the data
                    menus = UBVersionMenu.prototype.ubVersionMenus
                    for (var i = 0;i < menus.length;i++) {
                        menus[i].store.loadData(records);
                    }
                    //Select the 'Current Version'.  Only has to be selected once since they are all connected
                    if (menus.length > 0) {
                        //Fires the event 'select', which takes a combobox, record, and index as arguments
                        //Gets the correct record type from the combobox's store
                        menus[0].fireEvent('select', menus[0], new (menus[0].store.recordType)({
                            sequence: null,
                            version: null,
                            issue_date: null,
                        }), 0);
                    }

                    // a row was selected in the UI, update subordinate ReeBill Data
                    //if (record.data.sequence != null) {
                    //    loadReeBillUIForSequence(record.data.account, record.data.sequence);
                    //}
                    // convert the parsed date into a string in the format expected by the back end
                    var formatted_begin_date_string = record.data.period_start.format('Y-m-d');
                    var formatted_end_date_string = record.data.period_end.format('Y-m-d');


                    // image rendering resolution
                    // TODO Ext.getCmp vs doc.getElement
                    var menu = document.getElementById('billresolutionmenu');
                    if (menu) {
                        resolution = menu.value;
                    } else {
                        resolution = DEFAULT_RESOLUTION;
                    }

                    // ajax call to generate image, get the name of it, and display it in a
                    // new window
                    if (record.data.state == 'Final' || record.data.state == 'Utility Estimated') {

                        utilbillImageDataConn.request({
                            params: {account: record.data.account, begin_date: formatted_begin_date_string,
                                end_date: formatted_end_date_string, resolution: resolution},
                            success: function(result, request) {
                                var jsonData = null;
                                try {
                                    jsonData = Ext.util.JSON.decode(result.responseText);
                                    var imageUrl = '';
                                    if (jsonData.success == true) {
                                        imageUrl = 'http://' + location.host + '/utilitybillimages/' + jsonData.imageName;
                                    }
                                    // TODO handle failure if needed
                                    Ext.DomHelper.overwrite('utilbillimagebox',
                                        getImageBoxHTML(imageUrl, 'Utility bill',
                                        'utilbill', NO_UTILBILL_SELECTED_MESSAGE),
                                        true);
                                } catch (err) {
                                    Ext.MessageBox.alert('getutilbillimage ERROR', err);
                                }
                            },
                            // this is called when the server returns 500 as well as when there's no response
                            failure: function () {
                                Ext.MessageBox.alert('Ajax failure');
                            },
                        });

                        // while waiting for the ajax request to finish, show a
                        // loading message in the utilbill image box
                        Ext.DomHelper.overwrite('utilbillimagebox', {tag: 'div',
                                html: LOADING_MESSAGE, id: 'utilbillimage'}, true);
                    }
                    else {
                        Ext.DomHelper.overwrite('utilbillimagebox', getImageBoxHTML(null, 'Utility bill', 'utilbill', NO_UTILBILL_SELECTED_MESSAGE), true);
                    }
                }
            }
        }),
    });

    utilbillGrid.getSelectionModel().on('selectionchange', function(sm){
        //utilbillGrid.getTopToolbar().findById('utilbillInsertBtn').setDisabled(sm.getCount() <1);
        var enable = sm.getSelections().every(function(r) {return r.data.editable});
        utilbillGrid.getTopToolbar().findById('utilbillRemoveButton').setDisabled(!enable);
    });
  

    // disallow rowediting of utility bills that are associated to reebills
    utilbillGrid.on('beforeedit', function(e) {
        if (!e.record.data.editable) {
            Ext.Msg.alert("Utility bill data cannot be edited once associated to an issued ReeBill.");
            return false;
        }

    });

    utilbillGrid.on('validateedit', function(e) {
        // Resolve that 'service' values can only be Gas or Electric
        // (or whatever is specified as acceptable values)
        // TODO: Make this depend on a data source of good values rather than hard-coded values
        if(e.field == 'service' && e.value != "Gas" && e.value != "Electric")
        {
            Ext.Msg.alert("Service type must be one of: \'Gas\' \'Electric\'");
            return false;
        }
    });

    //
    // Instantiate the Utility Bill panel
    //
    var utilityBillPanel = new Ext.Panel({
        id: 'utilityBillTab',
        title: 'Utility Bills',
        disabled: utilityBillPanelDisabled,
        layout: 'vbox',
        layoutConfig : {
            align : 'stretch',
            pack : 'start'
        },
        // utility bill image on one side, upload form & list of bills on the
        // other side (using 2 panels)
        items: [
            upload_form_panel,
            utilbillGrid,
        ],
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    utilityBillPanel.on('activate', function (panel) {

        // demand that the store configure and load itself
        utilbillGridStore.reload();

    });

          
    ////////////////////////////////////////////////////////////////////////////
    // ReeBill Tab
    //

    // Select ReeBill

    // forms for calling bill process operations
    var billOperationButton = new Ext.SplitButton({
        text: 'Process Bill',
        handler: allOperations, // handle a click on the button itself
        menu: new Ext.menu.Menu({
            items: [
                // these items will render as dropdown menu items when the arrow is clicked:
                {text: 'Roll Period', handler: function(){
                    //Ext.Msg.show({title: "Please wait while new ReeBill is created", closable: false});
                    rollOperation();
                    }
                },
                {text: 'Bind RE&E Offset', handler: bindREEOperation},
                {text: 'Compute Bill', handler: computeBillOperation},
                //{text: 'Attach Utility Bills to Reebill', handler: attachOperation},
                {text: 'Render', handler: renderOperation},
            ]
        })
    });

    function deleteReebills(sequences) {
        /* instead of using reebillStore.remove(), which (temporarily) deletes
         * the row from the grid whether or not the record was really supposed
         * to go away, just tell the server to do the right thing, then reload
         * the store to get the latest data from the server. */
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/delete_reebill',
            params: { account: selected_account, sequences: sequences },
            success: function(result, request) {
                var jsonData = Ext.util.JSON.decode(result.responseText);
                Ext.Msg.hide();
                if (jsonData.success == true) {
                    reeBillStore.reload();
                } else {
                    Ext.MessageBox.alert("Error", jsonData.errors.reason +
                        "\n" + jsonData.errors.details);
                }
            },
            failure: function() {
                Ext.MessageBox.alert('Ajax failure', 'delete_reebill request failed');
            },
        });
    }

    var deleteButton = new Ext.Button({
        text: 'Delete selected reebill',
        iconCls: 'icon-delete',
        disabled: true,
        handler: function() {
            var selectedRecords = reeBillGrid.getSelectionModel().getSelections();
            var sequences = selectedRecords.map(function(rec) {
                return rec.data.sequence;
            });

            Ext.Msg.confirm('Confirm deletion',
                'Are you sure you want to delete the latest version of reebill '
                + selected_account + '-' + sequences + '?', function(answer) {
                    if (answer == 'yes') {
                        reeBillGrid.getSelectionModel().clearSelections();
                        deleteReebills(sequences);
                    }
            });

            reeBillStore.reload();
        }
    })

    var newVersionConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/new_reebill_version',
        disableCaching: true,
        timeout: 960000,
    });
    var versionButton = new Ext.Button({
        text: 'Create new version',
        iconCls: 'icon-add',
        disabled: true,
        handler: function() {
            var waitMask = new Ext.LoadMask(Ext.getBody(), { msg:"Creating new versions; please wait" });
            waitMask.show();
            newVersionConn.request({
                url: 'http://'+location.host+'/reebill/new_reebill_version',

                params: { account: selected_account, sequence: selected_sequence },
                success: function(result, request) {
                    var jsonData = Ext.util.JSON.decode(result.responseText);
                    waitMask.hide();
                    if (jsonData.success == true) {
                        reeBillStore.reload();
                        Ext.MessageBox.alert("New version created", jsonData.new_version);
                    } else {
                        Ext.MessageBox.alert("Error", jsonData.errors.reason +
                            "\n" + jsonData.errors.details);
                    }
                },
                failure: function() {
                    waitMask.hide();
                    Ext.MessageBox.alert('Ajax failure', 'new_reebill_version request failed');
                },
            });
        }
    });

    var initialReebill =  {
        rows: [
        ]
    };

    var reeBillReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // find out why these properties have to be configured in the store
        //idProperty: 'id',
        //root: 'rows',
        //totalProperty: 'results',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'sequence', mapping: 'sequence'},
        ]
    });

    var reeBillWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    var reeBillStoreDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/reebill',
    });
    reeBillStoreDataConn.autoAbort = true;
    reeBillStoreDataConn.disableCaching = true;
    reeBillStoreDataConn.on('beforerequest', function(conn, options) {
    });

    var reeBillStoreProxy = new Ext.data.HttpProxy(reeBillStoreDataConn);

    var reeBillStore = new Ext.data.JsonStore({
        proxy: reeBillStoreProxy,
        autoSave: false,
        batch: false,
        reader: reeBillReader,
        writer: reeBillWriter,
        baseParams: { start:0, limit: 25},
        //data: initialReebill,
        root: 'rows',
        totalProperty: 'results',
        idProperty: 'id',
        fields: [
            {name: 'sequence'},
            {name: 'period_start'},
            {name: 'period_end'},
            {name: 'corrections'}, // human-readable (could replace with a nice renderer function for max_version)
            {name: 'issue_date'},
            {name: 'max_version'}, // machine-readable
            {name: 'hypothetical_total'},
            {name: 'actual_total'},
            {name: 'ree_quantity'},
            {name: 'ree_value'},
            {name: 'prior_balance'},
            {name: 'payment_received'},
            {name: 'total_adjustment'},
            {name: 'balance_forward'},
            {name: 'balance_forward'},
            {name: 'ree_charges'},
            {name: 'balance_due'},
            {name: 'total_error'},
            {name: 'issued'},
            {name: 'services'},
        ],
        remoteSort: true,
        sortInfo: { //Sort in descending order by sequence number
            field: 'sequence',
            direction: 'DESC'
        },
    });

    reeBillStore.on('beforesave', function(store, data) {
        reeBillGrid.setDisabled(true);
    });

    reeBillStore.on('beforewrite', function(store, action, record, options, arg) {
        if (action == 'destroy') {
            // TODO say what the actual version is (and don't mention version if it's 0)
            var result = Ext.Msg.confirm('Confirm deletion',
                'Are you sure you want to delete the latest version of reebill '
                + selected_account + '-' + selected_sequence + '?', function(answer) {
            });
            if (result == true) {
                return false;
            }
        }
        return true;
    });
    reeBillStore.on('update', function(){
    });

    reeBillStore.on('save', function () {
        reeBillGrid.setDisabled(false);
    });

    reeBillStore.on('beforeload', function (store, options) {

        // disable the grid before it loads
        reeBillGrid.setDisabled(true);

        // The Ext API is not clear on the relationship between options and baseParams
        // options appears to override baseParams.  Furthermore, start and limit appear
        // to be treated differently.  Need to scour the Ext source to figure this out.

        // account changed, reset the paging 
        if (store.baseParams.account && store.baseParams.account != selected_account) {
            // TODO: 26143175 start new account selection on the last page
            // reset pagination since it is a new account being loaded.
            options.params.start = 0;
        }

        options.params.account = selected_account;
        options.params.service = Ext.getCmp('service_for_charges').getValue();

        // set the current selection into the store's baseParams
        // so that the store can decide to load itself if it wants
        store.baseParams.account = selected_account;

    });
    
    // fired when the datastore has completed loading
    reeBillStore.on('load', function (store, records, options) {
        // was disabled prior to loading, and must be enabled when loading is complete
        reeBillGrid.setDisabled(false);
    });
    
    // handles all server errors for reeBillStore. see DataProxy.exception
    // event for argument meanings
    reeBillStore.on('exception', function(dataProxy, type, action, options, response,
                arg) {
        if (type == 'remote' && action == 'destroy') {
            if (response.success !== true) {
                Ext.Msg.alert('Error', response.raw.errors.reason + " " +
                        response.raw.errors.details);
            } else {
                loadReeBillUIForSequence(selected_account, selected_sequence);
            }
        } else {
            // catch-all for other errors
            Ext.Msg.alert('Error', "reebillstore error: type "+type+", action "+action+", response "+response);
        }
    });

    function reeBillGridRenderer(value, metaData, record, rowIndex, colIndex,
            store) {
        if (record.data.issued) {
            // issued bill
            metaData.css = 'reebill-grid-issued';
        } else if (record.data.max_version == 0) {
            // unissued version-0 bill
            metaData.css = 'reebill-grid-unissued';
        } else {
            // unissued correction
            metaData.css = 'reebill-grid-unissued-correction';
        }
        return value;
    }

    var reeBillColModel = new Ext.grid.ColumnModel(
    {
        columns: [
        /* NOTE: "width" is absolute column width in pixels, and one column
         * must not be given a width (i.e. must expand to take up all available
         * space) or else column width will not work properly (maybe Ext tries
         * to distribute the space proportionally). */
            {
                header: 'Sequence',
                sortable: true,
                dataIndex: 'sequence',
                //editor: new Ext.form.TextField({allowBlank: true})
                width: 70,
                renderer: reeBillGridRenderer,
            },{
                header: 'Corrections',
                sortable: false,
                dataIndex: 'corrections',
                width: 90,
                renderer: reeBillGridRenderer,
            //},{
                //header: 'Total Error',
                //sortable: false,
                //dataIndex: 'total_error',
                //width: 45,
                //renderer: reeBillGridRenderer,
            },{
                header: 'Start Date',
                sortable: false,
                dataIndex: 'period_start',
                width: 70,
                renderer: reeBillGridRenderer,
            },{
                header: 'End Date',
                sortable: false,
                dataIndex: 'period_end',
                width: 70,
                renderer: reeBillGridRenderer,
            },{
                header: 'Issue Date',
                sortable: false,
                dataIndex: 'issue_date',
                width: 70,
                renderer: reeBillGridRenderer,
            },{
                header: 'Hypo',
                sortable: false,
                dataIndex: 'hypothetical_total',
                width: 65,
                align: 'right',
                renderer: reeBillGridRenderer,
            },{
                header: 'Actual',
                sortable: false,
                dataIndex: 'actual_total',
                width: 65,
                align: 'right',
                renderer: reeBillGridRenderer,
            },{
                header: 'RE&E',
                sortable: false,
                dataIndex: 'ree_quantity',
                width: 70,
                align: 'right',
                renderer: reeBillGridRenderer,
            },{
                header: 'RE&E Value',
                sortable: false,
                dataIndex: 'ree_value',
                width: 90,
                align: 'right',
                renderer: reeBillGridRenderer,
            //},{
                //header: 'Prior Balance',
                //sortable: false,
                //dataIndex: 'prior_balance',
                //width: 65,
                //align: 'right',
                //renderer: reeBillGridRenderer,
            //},{
                //header: 'Payment',
                //sortable: false,
                //dataIndex: 'payment_received',
                //width: 65,
                //align: 'right',
                //renderer: reeBillGridRenderer,
            //},{
                //header: 'Adjustment',
                //sortable: false,
                //dataIndex: 'total_adjustment',
                //width: 65,
                //align: 'right',
                //renderer: reeBillGridRenderer,
            //},{
                //header: 'Balance Fwd',
                //sortable: false,
                //dataIndex: 'balance_forward',
                //width: 65,
                //align: 'right',
                //renderer: reeBillGridRenderer,
            },{
                header: 'RE&E Charges',
                sortable: false,
                dataIndex: 'ree_charges',
                //width: 65,
                align: 'right',
                renderer: reeBillGridRenderer,
            //},{
                //header: 'Balance Due',
                //sortable: false,
                //dataIndex: 'balance_due',
                //width: 65,
                //align: 'right',
                //renderer: reeBillGridRenderer,
            },
        ]
    });

    // TODO 25418527: Figure why the fuck each item in the toolbar has to be wrapped by a panel
    // so as to not overlap.
    var reeBillToolbar = new Ext.Toolbar(
    {
        items: [
            {
                xtype: 'panel',
                width: 200,
                items: [
                    // TODO:21046353
                    new Ext.form.ComboBox({
                        id: 'service_for_charges',
                        fieldLabel: 'Service',
                        triggerAction: 'all',
                        mode: 'local',
                        store: new Ext.data.ArrayStore({
                            id: 0,
                            fields: ['service'],
                        }),
                        valueField: 'service',
                        displayField: 'service',
                        width: 200,
                    }),
                ],
            },
            { xtype: 'tbseparator' },
            {
                xtype: 'panel',
                items: [
                    billOperationButton,
                ],
            },

            deleteButton,
            versionButton
        ]
    });

    var reeBillGrid = new Ext.grid.GridPanel({
        flex: 1,
        tbar: reeBillToolbar,
        bbar: new Ext.PagingToolbar({
            // TODO: constant
            pageSize: 25,
            store: reeBillStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No ReeBills to display",
        }),
        colModel: reeBillColModel,
        selModel: new Ext.grid.RowSelectionModel({
            singleSelect: true,
            listeners: {
                /* rowdeselect is always called before rowselect when the selection changes. */
                rowdeselect: function(selModel, index, record) {
                     loadReeBillUIForSequence(selected_account, null);
                },
                rowselect: function (selModel, index, record) {
                    // TODO: have other widgets pull when this selection is made
                    loadReeBillUIForSequence(selected_account, record.data.sequence);
                    ubRegisterGrid.getSelectionModel().clearSelections();
                },
            },
        }),
        store: reeBillStore,
        enableColumnMove: false,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        title: 'ReeBills',
    });

    reeBillGrid.getSelectionModel().on('selectionchange', function(sm){
    });


    var accountInfoDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/account_info',
    });
    accountInfoDataConn.autoAbort = true;
    accountInfoDataConn.disableCaching = true;

    var accountInfoFormItems = [
        {
            xtype: 'fieldset',
            title: 'Rates',
            collapsible: false,
            defaults: {
                anchor: '0',
            },
            items: [
                {
                    xtype: 'textfield',
                    id: 'discount_rate',
                    fieldLabel: 'Discount Rate',
                    name: 'discount_rate',
                },{
                    xtype: 'textfield',
                    id: 'late_charge_rate',
                    fieldLabel: 'Late Charge Rate',
                    name: 'late_charge_rate',
                    msgTarget: 'under',
                },
            ],
        },
        {
            xtype: 'fieldset',
            title: 'Skyline Billing Address',
            collapsible: false,
            defaults: {
                anchor: '0',
            },
            items: [
                {
                    xtype: 'textfield',
                    id: 'ba_addressee',
                    fieldLabel: 'Addressee',
                    name: 'ba_addressee',
                    //value: addresses['billing_address']['addressee'],
                },{
                    xtype: 'textfield',
                    id: 'ba_street',
                    fieldLabel: 'Street',
                    name: 'ba_street',
                    //value: addresses['billing_address']['street'],
                },{
                    xtype: 'textfield',
                    id: 'ba_city',
                    fieldLabel: 'City',
                    name: 'ba_city',
                    //value: addresses['billing_address']['city'],
                },{
                    xtype: 'textfield',
                    id: 'ba_state',
                    fieldLabel: 'State',
                    name: 'ba_state',
                    //value: addresses['billing_address']['state'],
                },{
                    xtype: 'textfield',
                    id: 'ba_postal_code',
                    fieldLabel: 'Postal Code',
                    name: 'ba_postal_code',
                    //value: addresses['billing_address']['postal_code'],
                },
            ]
        },{
            xtype: 'fieldset',
            title: 'Skyline Service Address',
            collapsible: false,
            defaults: {
                anchor: '0',
            },
            items: [
                {
                    xtype: 'textfield',
                    id: 'sa_addressee',
                    fieldLabel: 'Addressee',
                    name: 'sa_addressee',
                    //value: addresses['service_address']['addressee'],
                },{
                    xtype: 'textfield',
                    id: 'sa_street',
                    fieldLabel: 'Street',
                    name: 'sa_street',
                    //value: addresses['service_address']['street'],
                },{
                    xtype: 'textfield',
                    id: 'sa_city',
                    fieldLabel: 'City',
                    name: 'sa_city',
                    //value: addresses['service_address']['city'],
                },{
                    xtype: 'textfield',
                    id: 'sa_state',
                    fieldLabel: 'State',
                    name: 'sa_state',
                    //value: addresses['service_address']['state'],
                },{
                    xtype: 'textfield',
                    id: 'sa_postal_code',
                    fieldLabel: 'Postal Code',
                    name: 'sa_postal_code',
                    //value: addresses['service_address']['postal_code'],
                },
            ]
        },
    ]

    var accountInfoFormPanel = new Ext.FormPanel(
    {
        id: 'accountInfoFormPanel',
        title: 'Sequential Account Information',
        header: true,
        url: 'http://'+location.host+'/reebill/set_account_info',
        border: false,
        frame: true,
        flex: 1,
        bodyStyle:'padding:10px 10px 0px 10px',
        defaults: {
            anchor: '-20',
            allowBlank: false,
        },
        items:[accountInfoFormItems], 
        buttons: 
        [
            // TODO: the save button is generic in function, refactor
            {
                text   : 'Save',
                handler: saveForm,
            },{
                text   : 'Reset',
                handler: function() {
                    var formPanel = this.findParentByType(Ext.form.FormPanel);
                    formPanel.getForm().reset();
                }
            }
        ]
    })

    // since this panel depends on data from the reeBillGrid, hook into
    // its activate so that the user has the chance to pick a selected_sequence
    accountInfoFormPanel.on('activate', function (panel) {
        // because this tab is being displayed, demand the form that it contain 
        // be populated
        // disable it during load, the datastore re-enables when loaded.
        accountInfoFormPanel.setDisabled(true);

        //var accountInfoFormPanel = Ext.getCmp('accountInfoFormPanel');
        // add base parms for form post
        // we should set these on the form when the form activates?
        accountInfoFormPanel.getForm().baseParams = {account: selected_account, sequence: selected_sequence}

        // get the address information for this reebill 
        // fire this request when the widget is displayed
        accountInfoDataConn.request({
            params: {account: selected_account, sequence: selected_sequence},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false) {
                        Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                    } else {
                        Ext.getCmp('discount_rate').setValue(jsonData['discount_rate']);
                        Ext.getCmp('late_charge_rate').setValue(jsonData['late_charge_rate']);

                        Ext.getCmp('ba_addressee').setValue(jsonData['billing_address']['addressee']);
                        Ext.getCmp('ba_street').setValue(jsonData['billing_address']['street']);
                        Ext.getCmp('ba_city').setValue(jsonData['billing_address']['city']);
                        Ext.getCmp('ba_state').setValue(jsonData['billing_address']['state']);
                        Ext.getCmp('ba_postal_code').setValue(jsonData['billing_address']['postal_code']);

                        Ext.getCmp('sa_addressee').setValue(jsonData['service_address']['addressee']);
                        Ext.getCmp('sa_street').setValue(jsonData['service_address']['street']);
                        Ext.getCmp('sa_city').setValue(jsonData['service_address']['city']);
                        Ext.getCmp('sa_state').setValue(jsonData['service_address']['state']);
                        Ext.getCmp('sa_postal_code').setValue(jsonData['service_address']['postal_code']);

                        accountInfoFormPanel.doLayout();
                    } 
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    accountInfoFormPanel.setDisabled(false);
                }
            },
            failure: function(result, request) {
                try {
                    Ext.MessageBox.alert('Server Error', result.responseText);
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    accountInfoFormPanel.setDisabled(false);
                }
            },
        });
    });


    // finally, set up the tabe that will contain the above widgets
    var reeBillPanel = new Ext.Panel({
        id: 'reeBillTab',
        title: 'ReeBills',
        disabled: reeBillPanelDisabled,
        layout: 'accordion',
        items: [reeBillGrid, accountInfoFormPanel ],
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    reeBillPanel.on('activate', function (panel) {
        reeBillStore.reload();
    });

    function allOperations() {
        Ext.Msg.alert('Notice', "One of the operations on this menu must be selected");
    }

    var computeBillOperationConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/compute_bill',
        disableCaching: true,
    });
    computeBillOperationConn.autoAbort = true;
    function computeBillOperation() {
        tabPanel.setDisabled(true);

        computeBillOperationConn.request({
            params: {account: selected_account, sequence: selected_sequence},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false) {
                        Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                    }
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    //Ext.Msg.hide();
                    tabPanel.setDisabled(false);
                    reeBillStore.reload()
                }
            },
            failure: function(result, request) {
                try {
                    Ext.MessageBox.alert('Server Error', result.responseText);
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    //Ext.Msg.hide();
                    tabPanel.setDisabled(false);
                }
            },
        });
    }

    var bindREEOperationConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/bindree',
        disableCaching: true,
        timeout: 960000,
    });
    bindREEOperationConn.autoAbort = true;
    function bindREEOperation() {
        var waitMask = new Ext.LoadMask(Ext.getBody(), { msg:"Gathering data; please wait" });
        waitMask.show();

        bindREEOperationConn.request({
            params: {account: selected_account, sequence: selected_sequence},
            success: function(result, request) {
                var jsonData = null;
                waitMask.hide();
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false) {
                        Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                    }
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                }
            },
            failure: function(result, request) {
                waitMask.hide();
                try {
                    Ext.MessageBox.alert('Server Error', result.responseText);
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                }
            },
        });
    }

    var rollOperationConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/roll',
        disableCaching: true,
        timeout: 120000, // 2 minutes
    });
    rollOperationConn.autoAbort = true;
    function rollOperation()
    {
        tabPanel.setDisabled(true);
        var waitMask = new Ext.LoadMask(Ext.getBody(), { msg:"Creating new reebill; please wait" });
        waitMask.show();
        if(reeBillStore.getTotalCount() == 0) {
            waitMask.hide();
            Ext.Msg.prompt('Service Start Date', 'Enter the date (YYYY-MM-DD) on which your utility service(s) started', function (btn, service_start_date) {
                if(btn == 'ok') {
                    waitMask.show();
                    rollOperationConn.request({
                    params: {account: selected_account, start_date: service_start_date},
                    success: function(result, request) {
                        var jsonData = null;
                        try {
                            jsonData = Ext.util.JSON.decode(result.responseText);
                            if (jsonData.success == false) {
                                waitMask.hide();
                                Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                            } else {
                                reeBillGrid.getSelectionModel().clearSelections();
                                reeBillStore.setDefaultSort('sequence', 'DESC');
                                pageSize = reeBillGrid.getBottomToolbar().pageSize;
                                reeBillStore.load({params: {start: 0, limit: pageSize}, callback: function () {
                                    reeBillGrid.getSelectionModel().selectFirstRow();
                                }});
                            }
                        } catch (err) {
                            waitMask.hide();
                            Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                        } finally {
                            tabPanel.setDisabled(false);
                            waitMask.hide();
                        }

                    },
                    failure: function(result, request) {
                        waitMask.hide();
                        try {
                            Ext.MessageBox.alert('Server Error', result.responseText);
                        } catch (err) {
                            Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                        } finally {
                            tabPanel.setDisabled(false);
                        }
                    },
                    });
                } else {
                    tabPanel.setDisabled(false);
                    waitMask.hide();
                };
            });
        }
        else
        {
            rollOperationConn.request({
                params: {account: selected_account},
                success: function(result, request) {
                    var jsonData = null;
                    try {
                        jsonData = Ext.util.JSON.decode(result.responseText);
                        if (jsonData.success == false) {
                            waitMask.hide();
                            Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                        } else {
                            reeBillGrid.getSelectionModel().clearSelections();
                            reeBillStore.setDefaultSort('sequence', 'DESC');
                            pageSize = reeBillGrid.getBottomToolbar().pageSize;
                            reeBillStore.load({params: {start: 0, limit: pageSize}, callback: function () {
                                reeBillGrid.getSelectionModel().selectFirstRow();
                            }});
                        }
                    } catch (err) {
                        waitMask.hide();
                        Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                    } finally {
                        tabPanel.setDisabled(false);
                        waitMask.hide();
                    }
                },
                failure: function(result, request) {
                    waitMask.hide();
                    try {
                        Ext.MessageBox.alert('Server Error', result.responseText);
                    } catch (err) {
                        Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                    } finally {
                        tabPanel.setDisabled(false);
                    }
                },
            });
        }
    }

    var renderDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/render',
    });
    renderDataConn.autoAbort = true;
    renderDataConn.disableCaching = true;
    function renderOperation()
    {
        // while waiting for the next ajax request to finish, show a loading message
        // in the utilbill image box
        Ext.DomHelper.overwrite('reebillimagebox', {tag: 'div', html:LOADING_MESSAGE, id: 'reebillimage'}, true);
        renderDataConn.request({
            params: { 
                account: selected_account,
                sequence: selected_sequence
            },
            success: function(response, options) {
                var response_obj = {};
                try {
                    response_obj = Ext.decode(response.responseText);
                } catch (e) {
                    Ext.Msg.alert("Fatal: Could not decode JSON data");
                }
                if (response_obj.success !== true) {
                    Ext.Msg.alert('Error', response_obj.errors.reason + " " +
                            response_obj.errors.details);
                    // handle failure if needed
                    Ext.DomHelper.overwrite('reebillimagebox', getImageBoxHTML('', 'Reebill', 'reebill', NO_REEBILL_SELECTED_MESSAGE), true);
                } else {
                    loadReeBillUIForSequence(selected_account, selected_sequence);
                }
            },
            failure: function () {
                Ext.MessageBox.alert('Error', "Render response fail");
                // handle failure if needed
                Ext.DomHelper.overwrite('reebillimagebox', getImageBoxHTML('', 'Reebill', 'reebill', NO_REEBILL_SELECTED_MESSAGE), true);
            }
        });
    }

    /*var attachDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/attach_utilbills',
    });
    attachDataConn.autoAbort = true;
    attachDataConn.disableCaching = true;
    function attachOperation() {
        /* Finalize association of utilbills with reebill.
        attachDataConn.request({
            params: {
                account: selected_account,
                sequence: selected_sequence,
            },
            success: function(response, options) {
                var response_obj = {};
                try {
                    response_obj = Ext.decode(response.responseText);
                } catch (e) {
                    Ext.Msg.alert("Fatal: Could not decode JSON data");
                }
                if (response_obj.success !== true) {
                    Ext.Msg.alert('Error', response_obj.errors.reason + " " +
                            response_obj.errors.details);
                } else {
                    loadReeBillUIForSequence(selected_account, selected_sequence);
                }
            },
            failure: function() {
                Ext.MessageBox.alert('Error', "Attach Utility Bills failed");
            }
        });
    }*/


    ////////////////////////////////////////////////////////////////////////////
    //
    // Generic form save handler
    // 
    // TODO: 20496293 accept functions to callback on form post success
    function saveForm(b, e, callback) {
        //http://www.sencha.com/forum/showthread.php?127087-Getting-the-right-scope-in-button-handler
        var formPanel = b.findParentByType(Ext.form.FormPanel);
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
                            Ext.Msg.alert('Failure', action.result.errors.reason + ' ' + action.result.errors.details);
                            break;
                        default:
                            Ext.Msg.alert('Failure1', action.result.errors.reason + ' ' + action.result.errors.details);
                    }
                },
                success: function(form, action) {
                    // If an argument is not passed into a function, it has type 'undefined'
                    if (typeof callback !== 'undefined') {
                        callback(b, e)
                    }
                }
            })
        }else{
            Ext.MessageBox.alert('Errors', 'Please fix form errors noted.');
        }
    }

    //
    ////////////////////////////////////////////////////////////////////////////

    ////////////////////////////////////////////////////////////////////////////
    // Meters and Registers Tab
    //
    //
    // create a panel to which we can dynamically add/remove components
    // this panel is later added to the viewport so that it may be rendered


    var ubRegisterToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                id: 'ubNewRegisterBtn',
                iconCls: 'icon-add',
                text: 'New',
                disabled: false,
                handler: function() {
                    ubRegisterGrid.stopEditing();

                    var ubRegisterType = ubRegisterGrid.getStore().recordType;
                    var defaultData = 
                        {
                        };
                    var r = new ubRegisterType(defaultData);
                    
                    ubRegisterStore.add([r]);
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                id: 'ubRemoveRegisterBtn',
                iconCls: 'icon-delete',
                text: 'Remove',
                disabled: true,
                handler: function()
                {
                    ubRegisterGrid.stopEditing();
                    var s = ubRegisterGrid.getSelectionModel().getSelected();
                    ubRegisterStore.remove(s);
                }
            }
        ]
    });
    
    var initialUBRegister = {
        rows: [],
        total: 0
    };
    
    var ubRegisterReader = new Ext.data.JsonReader({
        root: 'rows',
        totalProperty: 'total',
        fields: [
            {name: 'id', mapping: 'id'},
            {name: 'service', mapping: 'service'},
            {name: 'meter_id', mapping: 'meter_id'},
            {name: 'register_id', mapping: 'register_id'},
            {name: 'type', mapping: 'type'},
            {name: 'binding', mapping: 'binding'},
            {name: 'description', mapping: 'description'},
            {name: 'quantity', mapping: 'quantity'},
            {name: 'quantity_units', mapping: 'quantity_units'},
        ],
    });

    var ubRegisterWriter = new Ext.data.JsonWriter({
        encode: true,
        writeAllFields: false,
        listful: true,
    });

    var ubRegisterStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/utilbill_registers'
    });
    ubRegisterStoreProxyConn.autoAbort = true;
    ubRegisterStoreProxyConn.disableCaching = true;

    var ubRegisterStoreProxy = new Ext.data.HttpProxy(ubRegisterStoreProxyConn);

    var ubRegisterStore = new Ext.data.Store({
        proxy: ubRegisterStoreProxy,
        reader: ubRegisterReader,
        writer: ubRegisterWriter,
        autoSave: true,
        remoteSort: true,
        data: initialUBRegister,
    });
    
    ubRegisterStore.on('beforeload', function(store, options) {
        if (ubRegisterGrid.getSelectionModel().hasSelection()) {
            options.params.current_selected_id = ubRegisterGrid.getSelectionModel().getSelected().id;
        }
        ubRegisterGrid.getSelectionModel().clearSelections();
        options.params.account = selected_account;
        options.params.utilbill_id = selected_utilbill.id;
        
        //Include the reebill's associated sequence and version if the utilbill is associated with one
        record = measuredUsageUBVersionMenu.selected_record
        //If there is no sequence or version, don't include those parameters
        if (record.data.sequence == null) {
            if (options.params.reebill_sequence != undefined) {
                delete options.params.reebill_sequence
            }
            if (options.params.reebill_version != undefined) {
                delete options.params.reebill_version
            }
        }
        //Otherwise, get the correct sequence and version
        else {
            options.params.reebill_sequence = record.data.sequence
            options.params.reebill_version = record.data.version
        }

        ubRegisterGrid.setDisabled(true);
        ubRegisterToolbar.find('id','ubRemoveRegisterBtn')[0].setDisabled(true);
    });

    ubRegisterStore.on('load', function(store, record, options) {
        ubRegisterGrid.setDisabled(false);
        o = ubRegisterReader.jsonData
        if (o.current_selected_id !== undefined) {
            ubRegisterGrid.getSelectionModel().selectRow(ubRegisterStore.indexOfId(o.current_selected_id))
        }
    });

    ubRegisterStore.on('beforewrite', function(store, action, rs, options, arg) {
        options.params.account = selected_account;
        options.params.utilbill_id = selected_utilbill.id;
        
        //Include the reebill's associated sequence and version if the utilbill is associated with one
        record = measuredUsageUBVersionMenu.selected_record
        //If there is no sequence or version, don't include those parameters
        if (record.data.sequence == null) {
            if (options.params.reebill_sequence != undefined) {
                delete options.params.reebill_sequence
            }
            if (options.params.reebill_version != undefined) {
                delete options.params.reebill_version
            }
        }
        //Otherwise, get the correct sequence and version
        else {
            options.params.reebill_sequence = record.data.sequence
            options.params.reebill_version = record.data.version
        }

        if (ubRegisterGrid.getSelectionModel().hasSelection()) {
            options.params.current_selected_id = ubRegisterGrid.getSelectionModel().getSelected().id;
        }
    });

    ubRegisterStore.on('write', function(store, action, result, res, rs) {
        ubRegisterGrid.getSelectionModel().clearSelections();
        ubRegisterStore.loadData(res.raw, false);
        if (res.raw.current_selected_id !== undefined) {
            ubRegisterGrid.getSelectionModel().selectRow(ubRegisterStore.indexOfId(res.raw.current_selected_id))
        }
    });

    ubRegisterStore.on('remove', function(store, record, index) {
        ubRegisterToolbar.find('id','ubRemoveRegisterBtn')[0].setDisabled(true);
        intervalMeterFormPanel.setDisabled(true);
    });
    
    ubRegisterColModel = new Ext.grid.ColumnModel({
        columns:[
            {
                id: 'service',
                header: 'Service',
                dataIndex: 'service',
                editable: true,
                sortable: false,
                editor: new Ext.form.TextField({allowBlank: false}),
                width: 70,
            },
            {
                id: 'meter_id',
                header: 'Meter ID',
                dataIndex: 'meter_id',
                editable: true,
                sortable: false,
                editor: new Ext.form.TextField({allowBlank: false}),
                width: 100,
            },
            {
                id: 'register_id',
                header: 'Register ID',
                dataIndex: 'register_id',
                editable: true,
                sortable: false,
                editor: new Ext.form.TextField({allowBlank: false}),
                width: 100,
            },
            {
                id: 'type',
                header: 'Type',
                dataIndex: 'type',
                editable: true,
                sortable: false,
                editor: new Ext.form.TextField({allowBlank: false}),
                width: 70,
            },
            {
                id: 'binding',
                header: 'RSI Binding',
                dataIndex: 'binding',
                editable: true,
                sortable: false,
                editor: new Ext.form.TextField({allowBlank: false}),
                width: 100,
            },
            {
                id: 'quantity',
                header: 'Quantity',
                dataIndex: 'quantity',
                editable: true,
                sortable: false,
                editor: new Ext.form.NumberField({allowBlank: false}),
                width: 70,
            },
            {
                id: 'quantity_units',
                header: 'Units',
                dataIndex: 'quantity_units',
                width: 70,
                sortable: true,
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
                id: 'description',
                header: 'Description',
                dataIndex: 'description',
                editable: true,
                sortable: false,
                editor: new Ext.form.TextField({allowBlank: false}),
            },
        ],
    });

    var ubRegisterGrid = new Ext.grid.EditorGridPanel({
        colModel: ubRegisterColModel,
        selModel: new Ext.grid.RowSelectionModel({
            singleSelect: true,
            moveEditorOnEnter: false,
            listeners: {
                rowdeselect: function(selModel, index, record) {
                    ubRegisterToolbar.find('id','ubRemoveRegisterBtn')[0].setDisabled(true);
                    intervalMeterFormPanel.setDisabled(true);
                },
                rowselect: function(selModel, index, record) {
                    ubRegisterToolbar.find('id','ubRemoveRegisterBtn')[0].setDisabled(ubRegisterGrid.disableEditing);
                    intervalMeterFormPanel.setDisabled(ubRegisterGrid.disableEditing);
                },
            },
        }),
        tbar: ubRegisterToolbar,
        store: ubRegisterStore,
        enableColumnMove: false,
        frame: true,
        animCollapse: false,
        stripeRows: true,
        autoExpandColumn: 'description',
        title: 'Utility Bill Registers',
        clicksToEdit: 2,
        flex: 1,
        disableEditing: true,
        setEditable: function(editable) {
            this.disableEditing = !editable
            ubRegisterToolbar.find('id','ubNewRegisterBtn')[0].setDisabled(!editable);
            ubRegisterToolbar.find('id','ubRemoveRegisterBtn')[0].setDisabled(!editable);
            intervalMeterFormPanel.setDisabled(!editable);
        },
    });

    ubRegisterGrid.on('beforeedit', function(e) {
        if (e.grid.disableEditing) {
            return false
        }
        return true
    });

    var intervalMeterFormPanel = new Ext.form.FormPanel({
        id: 'interval-meter-csv-field',
        title: 'Upload Interval Meter CSV',
        fileUpload: true,
        url: 'http://'+location.host+'/reebill/upload_interval_meter_csv',
        frame:true,
        //bodyStyle: 'padding: 10px 10px 0 10px;',
        labelWidth: 175,
        flex: 0,
        disabled: true,
        defaults: {
            anchor: '95%',
            //allowBlank: false,
            msgTarget: 'side'
        },
        items: [
            //file_chooser - defined in FileUploadField.js
            {
                xtype: 'fileuploadfield',
                emptyText: 'Select a file to upload',
                name: 'csv_file',
                fieldLabel: 'CSV File',
                buttonText: 'Choose file...',
                buttonCfg: { width:80 },
                allowBlank: true
            },{
                xtype: 'fieldset',
                title: 'Mapping',
                collapsible: false,
                defaults: {
                    anchor: '0',
                },
                items: [
                    {
                        xtype: 'textfield',
                        name: 'timestamp_column',
                        fieldLabel: "Timestamp Column",
                        value: "A",
                    },{
                        xtype: 'combo',
                        mode: 'local',
                        value: "%Y-%m-%d %H:%M:%S",
                        //forceSelection: true,
                        editable: true,
                        triggerAction: 'all',
                        fieldLabel: "Timestamp Format",
                        name: 'timestamp_format',
                        hiddenName: 'timestamp_format',
                        displayField: 'name',
                        valueField: 'value',
                        store: new Ext.data.JsonStore({
                            fields: ['name', 'value'],
                            data: [
                                {name: '%Y-%m-%d %H:%M:%S',value: '%Y-%m-%d %H:%M:%S'},
                                {name: '%Y/%m/%d %H:%M:%S',value: '%Y/%m/%d %H:%M:%S'},
                                {name: '%m/%d/%Y %H:%M:%S',value: '%m/%d/%Y %H:%M:%S'},
                                {name: '%Y-%m-%dT%H:%M:%SZ',value: '%Y-%m-%dT%H:%M:%SZ'}
                            ]
                        })
                    },{
                        xtype: 'textfield',
                        name: 'energy_column',
                        fieldLabel: "Metered Energy Column",
                        value: "B",
                    },{
                        xtype: 'combo',
                        mode: 'local',
                        value: 'kwh',
                        triggerAction: 'all',
                        forceSelection: true,
                        editable: false,
                        fieldLabel: 'Metered Energy Units',
                        name: 'energy_unit',
                        hiddenName: 'energy_unit',
                        displayField: 'name',
                        valueField: 'value',
                        store: new Ext.data.JsonStore({
                            fields : ['name', 'value'],
                            data : [
                                {name : 'kWh', value: 'kwh'},
                                {name : 'BTU', value: 'btu'},
                            ]
                        })
                    }
                ],
            },
        ],
        buttons: [
            new Ext.Button({
                text: 'Reset',
                handler: function() {
                    this.findParentByType(Ext.form.FormPanel).getForm().reset();
                }
            }),
            new Ext.Button({
                text: 'Submit',
                handler: function () {
                    var formPanel = this.findParentByType(Ext.form.FormPanel);
                    if (! formPanel.getForm().isValid()) {
                        Ext.MessageBox.alert('Errors', 'Please fix form errors noted.');
                        return;
                    }
                    //formPanel.getForm().setValues({
                    //'account': selected_account,
                    //'sequence': selected_sequence,
                    //'interval-meter-csv-field': 'new value',
                    //});
                    formPanel.getForm().submit({
                        params: {
                            'account': selected_account,
                            'sequence': selected_sequence,
                            'register_identifier': ubRegisterGrid.getSelectionModel().getSelected().data.register_id,
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
                            //
                        }
                    })
                }
            }),
        ],
    });
    
    var UBVersionMenu = Ext.extend(Ext.form.ComboBox, {
        //A list of all UBVersionMenus in existance, so that they can all
        //be updated at the same time.
        ubVersionMenus: [],
        //A toggle that is set after the select of one menu is fired,
        //so that other menus don't trigger it again
        inSelect: false,
        //stores_to_reload is a list of stores to reload when the dropdown is selected for this menu
        constructor: function (stores_to_reload) {
            UBVersionMenu.superclass.constructor.call(this, {
                editable: false,
                mode: 'local',
                triggerAction: 'all',
                flex: 0,
                
                // this template converts the record in the Datastore to a string:
                // "current" when the value of "sequence" in the record is null, and
                // sequence-version otherwise
                tpl: new Ext.XTemplate(
                    '<tpl for="."><div class="x-combo-list-item">',
                    '<tpl if="sequence == null">Current version</tpl>',
                    '<tpl if="sequence != null">Reebill {sequence}-{version}: {issue_date}</tpl>',
                    '</div></tpl>'
                ),
                
                listeners: {
                    select: function (cb, record, index) {
                        //If we're already in the middle of a select, this method
                        //doesn't need to run.
                        if(UBVersionMenu.prototype.inSelect) {
                            return;
                        }
                        UBVersionMenu.prototype.inSelect = true;
                        menus = cb.ubVersionMenus;
                        for (var i = 0;i < menus.length;i++) {
                            //Set the value to the correct string by extracting it from what the template generates
                            menus[i].setRawValue(/>(.*)</.exec(menus[i].tpl.apply(record.data))[1]);
                            menus[i].selected_record = record;
                            //For each menu but the one clicked on, make sure the select event gets fired
                            if (menus[i] != cb) {
                                menus[i].fireEvent('select', menus[i], record, index);
                            }
                        }
                        for (var i = 0;i < stores_to_reload.length;i++) {
                            stores_to_reload[i].load();
                        }
                        UBVersionMenu.prototype.inSelect = false;
                    },
                },
                store: new Ext.data.ArrayStore({
                    fields: [
                        //These can be any type, since it isn't specified
                        {'name': 'sequence'},
                        {'name': 'version'},
                        {'name': 'issue_date'},
                    ],
                    data:[[null, null, null]],
                }),
            });
            this.selected_record = this.store[0];
            UBVersionMenu.prototype.ubVersionMenus.push(this);
        }
    });

    measuredUsageUBVersionMenu = new UBVersionMenu([ubRegisterStore]);
    
    //
    // Instantiate the Utility Bill Meters and Registers panel
    //
    var ubMeasuredUsagesPanel = new Ext.Panel({
        id: 'ubMeasuredUsagesTab',
        title: 'Meters and Registers',
        disabled: usagePeriodsPanelDisabled,
        layout: 'vbox',
        layoutConfig : {
            pack : 'start',
            align : 'stretch',
        },
        items: [measuredUsageUBVersionMenu, ubRegisterGrid, intervalMeterFormPanel], // configureUBMeasuredUsagesForm sets this
    });

    ubMeasuredUsagesPanel.on('activate', function(panel) {
        ubRegisterStore.reload();
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    /*ubMeasuredUsagesPanel.on('activate', function (panel) {

        // because this tab is being displayed, demand the form that it contain 
        // be populated
        // disable it during load, the datastore re-enables when loaded.
        ubMeasuredUsagesPanel.setDisabled(true);

        // get the meter read dates for each service
        ubMeasuredUsagesDataConn.request({
            params: {account: selected_account, sequence: selected_sequence},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false)
                    {
                        Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                    } else {
                        configureUBMeasuredUsagesForms(selected_account, selected_sequence, jsonData);
                    } 
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    ubMeasuredUsagesPanel.setDisabled(false);
                }
            },
            failure: function() {
                try {
                    Ext.MessageBox.alert('Server Error', result.responseText);
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    ubMeasuredUsagesPanel.setDisabled(false);
                }
            },
            disableCaching: true,
        });
    });*/


    ////////////////////////////////////////////////////////////////////////////
    // Charges tab
    //


    /////////////////////////////////
    // support for the actual charges

    // initial data loaded into the grid before a bill is loaded
    // populate with data if initial pre-loaded data is desired
    var initialActualCharges = {
        rows: [
        ]
    };

    var aChargesReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        idProperty: 'uuid',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'chargegroup', mapping: 'chargegroup'},
            {name: 'uuid', mapping: 'uuid'},
            {name: 'rsi_binding', mapping: 'rsi_binding'},
            {name: 'description', mapping: 'description'},
            {name: 'quantity', mapping: 'quantity'},
            {name: 'quantity_units', mapping: 'quantity_units'},
            {name: 'rate', mapping: 'rate'},
            {name: 'rate_units', mapping: 'rate_units'},
            {name: 'total', mapping: 'total', type: 'float'},
            {name: 'processingnote', mapping:'processingnote'},
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

    // make a connections instance so that it may be specifically aborted
    var aChargesStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/actualCharges',
        disableCaching: true,
    })
    aChargesStoreProxyConn.autoAbort = true;

    var aChargesStoreProxy = new Ext.data.HttpProxy(aChargesStoreProxyConn);

    var aChargesStore = new Ext.data.GroupingStore({
        proxy: aChargesStoreProxy,
        autoSave: true,
        reader: aChargesReader,
        //root: 'rows',
        //idProperty: 'uuid',
        writer: aChargesWriter,
        data: initialActualCharges,
        sortInfo:{field: 'chargegroup', direction: 'ASC'},
        groupField:'chargegroup'
    });


    aChargesStore.on('save', function () {
        //aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(true);
    });
    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    aChargesStore.on('update', function(){
        //aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(false);
    });

    aChargesStore.on('beforeload', function (store, options) {
        aChargesGrid.setDisabled(true);
        aChargesStore.setBaseParam("utilbill_id", selected_utilbill.id);
        
        //Include the reebill's associated sequence and version if the utilbill is associated with one
        record = chargesUBVersionMenu.selected_record
        //If there is no sequence or version, don't include those parameters
        if (record.data.sequence == null) {
            if (options.params.reebill_sequence != undefined) {
                delete options.params.reebill_sequence
            }
            if (options.params.reebill_version != undefined) {
                delete options.params.reebill_version
            }
        }
        //Otherwise, get the correct sequence and version
        else {
            options.params.reebill_sequence = record.data.sequence
            options.params.reebill_version = record.data.version
        }

        if (ubRegisterGrid.getSelectionModel().hasSelection()) {
            options.params.current_selected_id = ubRegisterGrid.getSelectionModel().getSelected().id;
        }
    });

    aChargesStore.on('beforewrite', function(store, action, rs, options, arg) {
        //Include the reebill's associated sequence and version if the utilbill is associated with one
        record = chargesUBVersionMenu.selected_record
        //If there is no sequence or version, don't include those parameters
        if (record.data.sequence == null) {
            if (options.params.reebill_sequence != undefined) {
                delete options.params.reebill_sequence
            }
            if (options.params.reebill_version != undefined) {
                delete options.params.reebill_version
            }
        }
        //Otherwise, get the correct sequence and version
        else {
            options.params.reebill_sequence = record.data.sequence
            options.params.reebill_version = record.data.version
        }

        if (ubRegisterGrid.getSelectionModel().hasSelection()) {
            options.params.current_selected_id = ubRegisterGrid.getSelectionModel().getSelected().id;
        }
    });

    // fired when the datastore has completed loading
    aChargesStore.on('load', function (store, records, options) {
        //console.log('aChargesStore load');
        // the grid is disabled by the panel that contains it  
        // prior to loading, and must be enabled when loading is complete
        // the datastore enables when it is done loading
        aChargesGrid.setDisabled(false);
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
                hidden: true,
            },{
                header: 'UUID',
                width: 75,
                sortable: true,
                dataIndex: 'uuid',
                editable: true,
                hidden: true,
            },{
                header: 'RSI Binding',
                width: 75,
                sortable: true,
                dataIndex: 'rsi_binding',
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
                dataIndex: 'quantity_units',
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
                dataIndex: 'rate_units',
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
            },
        ]
    });

    var aChargesToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                id: 'utilbillComputeButton',
                text: 'Recompute All',
                handler: function() {
                    Ext.Ajax.request({
                        url: 'http://'+location.host+'/reebill/compute_utility_bill',
                        params: { utilbill_id: selected_utilbill.id },
                        success: function(result, request) {
                            var jsonData = Ext.util.JSON.decode(result.responseText);
                            if (jsonData.success == true) {
                                aChargesStore.reload();
                            } else {
                                Ext.MessageBox.alert("Error", jsonData.errors.reason +
                                    "\n" + jsonData.errors.details);
                            }
                        },
                        failure: function() {
                            Ext.MessageBox.alert('Ajax failure', 'delete_reebill request failed');
                        },
                    });
                }
            },
            {
                xtype: 'tbseparator'
            },{
                xtype: 'button',

                // ref places a name for this component into the grid so it may be referenced as [name]Grid.insertBtn...
                id: 'aChargesInsertBtn',
                iconCls: 'icon-add',
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
                        quantity_units: 'kWh',
                        rate: 0,
                        rate_units: 'dollars',
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
                    //aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(false);
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as [name]Grid.removeBtn...
                id: 'aChargesRemoveBtn',
                iconCls: 'icon-delete',
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
                    //aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(false);
                }
            },{
                xtype:'tbseparator'
            },{
                xtype: 'button',
                id: 'aChargesAddGroupBtn',
                iconCls: 'icon-add',
                text: 'Add Group',
                enabled: true,
                handler: function() {
                    Ext.Msg.prompt('Add Charge Group',
                            'New charge group name:', function(btn, groupName) {
                        if(btn != 'ok')
                            return;
                        var ChargeItemType = aChargesGrid.getStore().recordType;
                        var c = new ChargeItemType({
                            chargegroup: groupName,
                            description: 'enter description',
                            quantity: 0,
                            quantity_units: 'kWh',
                            rate: 0,
                            rate_units: 'dollars',
                            total: 0,
                        });
            
                        // create new record
                        aChargesStore.insert(aChargesStore.getTotalCount(), c);

                        // select newly inserted record
                        aChargesGrid.getView().refresh();
                        aChargesGrid.getSelectionModel().selectRow(
                                aChargesStore.getTotalCount() - 1);
                    }
                )
            }
        },
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
        flex: 1,
        stripeRows: true,
        autoExpandColumn: 'chargegroup',
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
    
    aChargesGrid.on('activate', function(panel) {
        //console.log("aCharges Grid Activated");
        //console.log(panel);
    });
    aChargesGrid.on('beforeshow', function(panel) {
        //console.log("aChargesGrid beforeshow");
        //console.log(panel);
    });
    aChargesGrid.on('show', function(panel) {
        //console.log("aChargesGrid show");
        //console.log(panel);
    });
    aChargesGrid.on('viewready', function(panel) {
        //console.log("aChargesGrid view ready");
        //console.log(panel);
    });
    aChargesGrid.on('beforeexpand', function (panel, animate) {
        //console.log("aChargesGrid beforeexpand ");
        //console.log(panel);
    });
    aChargesGrid.on('expand', function (panel) {
        //console.log("aChargesGrid expand ");
        //console.log(panel);
    });
    aChargesGrid.on('collapse', function (panel) {
        //console.log("aChargesGrid collapse ");
        //console.log(panel);
    });
    aChargesGrid.on('afterrender', function (panel) {
        //console.log("aChargesGrid afterrender ");
        //console.log(panel);
    });
    aChargesGrid.on('enable', function (panel) {
        //console.log("aChargesGrid enable ");
        //console.log(panel);
    });
    aChargesGrid.on('disable', function (panel) {
        //console.log("aChargesGrid disable ");
        //console.log(panel);
    });

    //
    // Instantiate the Charge Items panel
    //

    chargesUBVersionMenu = new UBVersionMenu([aChargesStore]);

    chargesUBVersionMenu.on('select', function(combo, record, index) {
        //Only allow recomputing when the current version is selected
        if (record.data.sequence == null) {
            aChargesToolbar.getComponent('utilbillComputeButton').setDisabled(false);
        }
        else {
            aChargesToolbar.getComponent('utilbillComputeButton').setDisabled(true);
        }
    });
    
    var chargeItemsPanel = new Ext.Panel({
        id: 'chargeItemsTab',
        title: 'Charges',
        disabled: chargeItemsPanelDisabled,
        xtype: 'panel',
        layout: 'vbox',
        layoutConfig : {
            pack : 'start',
            align : 'stretch',
        },
        items: [
            chargesUBVersionMenu,
            aChargesGrid,
        ]
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    chargeItemsPanel.on('activate', function (panel) {
        //console.log(panel);

        // because this tab is being displayed, demand the grids that it contain 
        // be populated
        aChargesGrid.setDisabled(true);
        //aChargesStore.proxy.getConnection().autoAbort = true;
        aChargesStore.reload({params: {service: Ext.getCmp('service_for_charges').getValue(), account: selected_account, sequence: selected_sequence}});
    });

    chargeItemsPanel.on('expand', function (panel) {
        //console.log("chargeItemsPanel expand");
        //console.log(panel);
    });
    chargeItemsPanel.on('collapse', function (panel) {
        //console.log("chargeItemsPanel collapse");
        //console.log(panel);
    });


    ///////////////////////////////////////
    // Rate Structure Tab


    // the CPRS

    var initialCPRSRSI = {
        rows: [
        ]
    };

    var CPRSRSIReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'uuid',
        //root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'uuid', mapping: 'uuid'},
            {name: 'rsi_binding', mapping: 'rsi_binding'},
            {name: 'description', mapping: 'description'},
            {name: 'quantity', mapping: 'quantity'},
            {name: 'quantityunits', mapping: 'quantityunits'},
            {name: 'rate', mapping: 'rate'},
            {name: 'rateunits', mapping: 'rateunits'},
            {name: 'roundrule', mapping:'roundrule'},
            {name: 'total', mapping: 'total'},
        ]
    });

    var CPRSRSIWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });
    
    var CPRSRSIStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/cprsrsi',
    });
    CPRSRSIStoreProxyConn.autoAbort = true;
    
    var CPRSRSIStoreProxy = new Ext.data.HttpProxy(CPRSRSIStoreProxyConn);

    var CPRSRSIStore = new Ext.data.JsonStore({
        proxy: CPRSRSIStoreProxy,
        autoSave: true,
        reader: CPRSRSIReader,
        writer: CPRSRSIWriter,
        data: initialCPRSRSI,
        root: 'rows',
        idProperty: 'uuid',
        fields: [
            {name: 'uuid'},
            {name: 'rsi_binding'},
            {name: 'description'},
            {name: 'quantity'},
            {name: 'quantityunits'},
            {name: 'rate'},
            {name: 'rateunits'},
            {name: 'roundrule'},
            {name: 'total'},
        ],
    });

    CPRSRSIStore.on('save', function (store, batch, data) {
        //CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(true);
    });

    CPRSRSIStore.on('beforeload', function (store, options) {
        CPRSRSIGrid.setDisabled(true);
        options.params.utilbill_id = selected_utilbill.id;
        //Include the reebill's associated sequence and version if the utilbill is associated with one
        record = chargesUBVersionMenu.selected_record
        //If there is no sequence or version, don't include those parameters
        if (record.data.sequence == null) {
            if (options.params.reebill_sequence != undefined) {
                delete options.params.reebill_sequence
            }
            if (options.params.reebill_version != undefined) {
                delete options.params.reebill_version
            }
        }
        //Otherwise, get the correct sequence and version
        else {
            options.params.reebill_sequence = record.data.sequence
            options.params.reebill_version = record.data.version
        }

        if (ubRegisterGrid.getSelectionModel().hasSelection()) {
            options.params.current_selected_id = ubRegisterGrid.getSelectionModel().getSelected().id;
        }
    });

    CPRSRSIStore.on('beforewrite', function(store, action, rs, options, arg) {
        options.params.utilbill_id = selected_utilbill.id;
        //Include the reebill's associated sequence and version if the utilbill is associated with one
        record = chargesUBVersionMenu.selected_record
        //If there is no sequence or version, don't include those parameters
        if (record.data.sequence == null) {
            if (options.params.reebill_sequence != undefined) {
                delete options.params.reebill_sequence
            }
            if (options.params.reebill_version != undefined) {
                delete options.params.reebill_version
            }
        }
        //Otherwise, get the correct sequence and version
        else {
            options.params.reebill_sequence = record.data.sequence
            options.params.reebill_version = record.data.version
        }

        if (ubRegisterGrid.getSelectionModel().hasSelection()) {
            options.params.current_selected_id = ubRegisterGrid.getSelectionModel().getSelected().id;
        }
    });

    // fired when the datastore has completed loading
    CPRSRSIStore.on('load', function (store, records, options) {
        // the grid is disabled by the panel that contains it  
        // prior to loading, and must be enabled when loading is complete
        // the datastore enables when it is done loading
        CPRSRSIGrid.setDisabled(false);
    });

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    CPRSRSIStore.on('update', function(){
        //CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(false);
    });

    CPRSRSIStore.on('beforesave', function(store, data) {
    });

    var CPRSRSIColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
                header: 'UUID',
                sortable: true,
                dataIndex: 'uuid',
                editable: false,
                editor: new Ext.form.TextField({allowBlank: false}),
                hidden: true,
                width: 50,
            },{
                header: 'RSI Binding',
                sortable: true,
                dataIndex: 'rsi_binding',
                editable: true,
                editor: new Ext.form.TextField({allowBlank: false}),
                width: 150,
            },{
                header: 'Description',
                sortable: true,
                dataIndex: 'description',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 100,
            },{
                header: 'Quantity',
                id: 'quantity',
                sortable: true,
                dataIndex: 'quantity',
                editor: new Ext.form.TextField({allowBlank: true}),
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'quantityunits',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 50,
            },{
                header: 'Rate',
                sortable: true,
                dataIndex: 'rate',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 50,
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'rateunits',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 50,
            },{
                header: 'Round Rule',
                sortable: true,
                dataIndex: 'roundrule',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 100,
            //},{
                //header: 'Total', 
                //sortable: true, 
                //dataIndex: 'total', 
                //summaryType: 'sum',
                //align: 'right',
                //editor: new Ext.form.TextField({allowBlank: true})
            }
        ]
    });

    var CPRSRSIToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as grid.insertBtn...
                id: 'CPRSRSIInsertBtn',
                iconCls: 'icon-add',
                text: 'Insert',
                disabled: false,
                handler: function()
                {
                    CPRSRSIGrid.stopEditing();

                    // grab the current selection - only one row may be selected per singlselect configuration
                    var selection = CPRSRSIGrid.getSelectionModel().getSelected();

                    // make the new record
                    var CPRSRSIType = CPRSRSIGrid.getStore().recordType;
                    var defaultData = 
                    {
                    };
                    var r = new CPRSRSIType(defaultData);
        
                    // select newly inserted record
                    var insertionPoint = CPRSRSIStore.indexOf(selection);
                    CPRSRSIStore.insert(insertionPoint + 1, r);
                    CPRSRSIGrid.startEditing(insertionPoint +1,1);
                    
                    // An inserted record must be saved 
                    //CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(false);
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as aChargesGrid.removeBtn...
                id: 'CPRSRSIRemoveBtn',
                iconCls: 'icon-delete',
                text: 'Remove',
                disabled: true,
                handler: function()
                {
                    CPRSRSIGrid.stopEditing();

                    // TODO single row selection only, test allowing multirow selection
                    var s = CPRSRSIGrid.getSelectionModel().getSelections();
                    for(var i = 0, r; r = s[i]; i++)
                    {
                        CPRSRSIStore.remove(r);
                    }
                    CPRSRSIStore.save(); 
                    //CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(true);
                }
            },{
                xtype:'tbseparator'
            },/*{
                xtype: 'button',
                // places reference to this button in grid.  
                id: 'CPRSRSISaveBtn',
                iconCls: 'icon-save',
                text: 'Save',
                disabled: true,
                handler: function()
                {
                    // disable the save button for the save attempt.
                    // is there a closer place for this to the actual button click due to the possibility of a double
                    // clicked button submitting two ajax requests?
                    CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(true);

                    // stop grid editing so that widgets like comboboxes in rows don't stay focused
                    CPRSRSIGrid.stopEditing();

                    CPRSRSIStore.save(); 

                }
            }*/
        ]
    });

    var CPRSRSIGrid = new Ext.grid.EditorGridPanel({
        tbar: CPRSRSIToolbar,
        colModel: CPRSRSIColModel,
        autoExpandColumn: 'quantity',
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: CPRSRSIStore,
        enableColumnMove: true,
        frame: true,
        stripeRows: true,
        title: 'Individual Rate Structure Items',
        clicksToEdit: 2
    });

    CPRSRSIGrid.getSelectionModel().on('selectionchange', function(sm){
        // if a selection is made, allow it to be removed
        // if the selection was deselected to nothing, allow no 
        // records to be removed.

        CPRSRSIGrid.getTopToolbar().findById('CPRSRSIRemoveBtn').setDisabled(sm.getCount() <1);

        // if there was a selection, allow an insertion
        //CPRSRSIGrid.getTopToolbar().findById('CPRSRSIInsertBtn').setDisabled(sm.getCount() <1);
    });
  
    
    // the UPRS
    var initialUPRSRSI = {
        rows: [
        ]
    };

    var UPRSRSIReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'id',
        //root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'uuid', mapping: 'uuid'},
            {name: 'rsi_binding', mapping: 'rsi_binding'},
            {name: 'description', mapping: 'description'},
            {name: 'quantity', mapping: 'quantity'},
            {name: 'quantityunits', mapping: 'quantityunits'},
            {name: 'rate', mapping: 'rate'},
            {name: 'rateunits', mapping: 'rateunits'},
            {name: 'roundrule', mapping:'roundrule'},
            {name: 'total', mapping: 'total'},
        ]
    });

    var UPRSRSIWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    var UPRSRSIStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/uprsrsi',
        disableCaching: true,
    });
    UPRSRSIStoreProxyConn.autoAbort = true;

    var UPRSRSIStoreProxy = new Ext.data.HttpProxy(UPRSRSIStoreProxyConn);

    var UPRSRSIStore = new Ext.data.JsonStore({
        proxy: UPRSRSIStoreProxy,
        autoSave: true,
        reader: UPRSRSIReader,
        writer: UPRSRSIWriter,
        //baseParams: { account:selected_account, sequence: selected_sequence},
        data: initialUPRSRSI,
        root: 'rows',
        idProperty: 'uuid',
        fields: [
            {name: 'uuid'},
            {name: 'rsi_binding'},
            {name: 'description'},
            {name: 'quantity'},
            {name: 'quantityunits'},
            {name: 'rate'},
            {name: 'rateunits'},
            {name: 'roundrule'},
            {name: 'total'},
        ],
    });

    UPRSRSIStore.on('save', function (store, batch, data) {
        //UPRSRSIGrid.getTopToolbar().findById('UPRSRSISaveBtn').setDisabled(true);
    });

    UPRSRSIStore.on('beforeload', function (store, options) {
        UPRSRSIGrid.setDisabled(true);
        options.params.utilbill_id = selected_utilbill.id;
        
        //Include the reebill's associated sequence and version if the utilbill is associated with one
        record = rsUBVersionMenu.selected_record
        //If there is no sequence or version, don't include those parameters
        if (record.data.sequence == null) {
            if (options.params.reebill_sequence != undefined) {
                delete options.params.reebill_sequence
            }
            if (options.params.reebill_version != undefined) {
                delete options.params.reebill_version
            }
        }
        //Otherwise, get the correct sequence and version
        else {
            options.params.reebill_sequence = record.data.sequence
            options.params.reebill_version = record.data.version
        }

        if (ubRegisterGrid.getSelectionModel().hasSelection()) {
            options.params.current_selected_id = ubRegisterGrid.getSelectionModel().getSelected().id;
        }
    });

    UPRSRSIStore.on('beforewrite', function(store, action, rs, options, arg) {
        options.params.utilbill_id = selected_utilbill.id;
        //Include the reebill's associated sequence and version if the utilbill is associated with one
        record = rsUBVersionMenu.selected_record
        //If there is no sequence or version, don't include those parameters
        if (record.data.sequence == null) {
            if (options.params.reebill_sequence != undefined) {
                delete options.params.reebill_sequence
            }
            if (options.params.reebill_version != undefined) {
                delete options.params.reebill_version
            }
        }
        //Otherwise, get the correct sequence and version
        else {
            options.params.reebill_sequence = record.data.sequence
            options.params.reebill_version = record.data.version
        }

        if (ubRegisterGrid.getSelectionModel().hasSelection()) {
            options.params.current_selected_id = ubRegisterGrid.getSelectionModel().getSelected().id;
        }
    });

    // fired when the datastore has completed loading
    UPRSRSIStore.on('load', function (store, records, options) {
        // the grid is disabled by the panel that contains it  
        // prior to loading, and must be enabled when loading is complete
        // the datastore enables when it is done loading
        UPRSRSIGrid.setDisabled(false);
    });

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    UPRSRSIStore.on('update', function(){
        //UPRSRSIGrid.getTopToolbar().findById('UPRSRSISaveBtn').setDisabled(false);
    });

    UPRSRSIStore.on('beforesave', function() {
    });

    var UPRSRSIColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
                header: 'UUID',
                sortable: true,
                dataIndex: 'uuid',
                editable: false,
                editor: new Ext.form.TextField({allowBlank: false}),
                hidden: true,
                width: 50,
            },{
                header: 'RSI Binding',
                sortable: true,
                dataIndex: 'rsi_binding',
                editable: true,
                editor: new Ext.form.TextField({allowBlank: false}),
                width: 150,
            },{
                header: 'Description',
                sortable: true,
                dataIndex: 'description',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 100,
            },{
                header: 'Quantity',
                id: 'quantity',
                sortable: true,
                dataIndex: 'quantity',
                editor: new Ext.form.TextField({allowBlank: true}),
                // no "width": expand to take up all available space
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'quantityunits',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 50,
            },{
                header: 'Rate',
                sortable: true,
                dataIndex: 'rate',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 50,
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'rateunits',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 50,
            },{
                header: 'Round Rule',
                sortable: true,
                dataIndex: 'roundrule',
                editor: new Ext.form.TextField({allowBlank: true}),
                width: 100,
            //},{
                //header: 'Total', 
                //sortable: true, 
                //dataIndex: 'total', 
                //summaryType: 'sum',
                //align: 'right',
                //editor: new Ext.form.TextField({allowBlank: true})
            }
        ]
    });

    var UPRSRSIToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as grid.insertBtn...
                id: 'UPRSRSIInsertBtn',
                iconCls: 'icon-add',
                text: 'Insert',
                disabled: false,
                handler: function()
                {
                    UPRSRSIGrid.stopEditing();

                    // grab the current selection - only one row may be selected per singlselect configuration
                    var selection = UPRSRSIGrid.getSelectionModel().getSelected();

                    // make the new record
                    var UPRSRSIType = UPRSRSIGrid.getStore().recordType;
                    var defaultData = { };
                    var r = new UPRSRSIType(defaultData);
        
                    // select newly inserted record
                    var insertionPoint = UPRSRSIStore.indexOf(selection);
                    UPRSRSIStore.insert(insertionPoint + 1, r);
                    UPRSRSIGrid.startEditing(insertionPoint +1,1);
                    
                    // An inserted record must be saved 
                    //UPRSRSIGrid.getTopToolbar().findById('UPRSRSISaveBtn').setDisabled(false);
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as aChargesGrid.removeBtn...
                id: 'UPRSRSIRemoveBtn',
                iconCls: 'icon-delete',
                text: 'Remove',
                disabled: true,
                handler: function()
                {
                    UPRSRSIGrid.stopEditing();
                    UPRSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
                    UPRSRSIStore.setBaseParam("account", selected_account);
                    UPRSRSIStore.setBaseParam("sequence", selected_sequence);

                    // TODO single row selection only, test allowing multirow selection
                    var s = UPRSRSIGrid.getSelectionModel().getSelections();
                    for(var i = 0, r; r = s[i]; i++)
                    {
                        UPRSRSIStore.remove(r);
                    }
                    UPRSRSIStore.save(); 
                    //UPRSRSIGrid.getTopToolbar().findById('UPRSRSISaveBtn').setDisabled(true);
                }
            },{
                xtype:'tbseparator'
            },/*{
                xtype: 'button',
                // places reference to this button in grid.  
                id: 'UPRSRSISaveBtn',
                iconCls: 'icon-save',
                text: 'Save',
                disabled: true,
                handler: function()
                {
                    // disable the save button for the save attempt.
                    // is there a closer place for this to the actual button click due to the possibility of a double
                    // clicked button submitting two ajax requests?
                    UPRSRSIGrid.getTopToolbar().findById('UPRSRSISaveBtn').setDisabled(true);

                    // stop grid editing so that widgets like comboboxes in rows don't stay focused
                    UPRSRSIGrid.stopEditing();

                    UPRSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
                    UPRSRSIStore.setBaseParam("account", selected_account);
                    UPRSRSIStore.setBaseParam("sequence", selected_sequence);

                    UPRSRSIStore.save(); 
                }
            }*/
        ]
    });

    var UPRSRSIGrid = new Ext.grid.EditorGridPanel({
        tbar: UPRSRSIToolbar,
        colModel: UPRSRSIColModel,
        autoExpandColumn: 'quantity',
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: UPRSRSIStore,
        enableColumnMove: true,
        frame: true,
        stripeRows: true,
        title: 'Shared Rate Structure Items',
        clicksToEdit: 2
    });

    UPRSRSIGrid.getSelectionModel().on('selectionchange', function(sm){
        // if a selection is made, allow it to be removed
        // if the selection was deselected to nothing, allow no 
        // records to be removed.
        UPRSRSIGrid.getTopToolbar().findById('UPRSRSIRemoveBtn').setDisabled(sm.getCount() <1);
    });
  

    //
    // Instantiate the Rate Structure panel 
    //

    rsUBVersionMenu = new UBVersionMenu([CPRSRSIStore, UPRSRSIStore]);

    var rateStructurePanel = new Ext.Panel({
        id: 'rateStructureTab',
        title: 'Rate Structure',
        disabled: rateStructurePanelDisabled,
        layout: 'vbox',
        layoutConfig : {
            pack : 'start',
            align : 'stretch',
        },
        items: [
            rsUBVersionMenu,
            {
                xtype:'panel',
                flex: 1,
                border: false,
                layout:'border',
                items: [
                    {
                        xtype: 'panel',
                        region: 'north',
                        border: false,
                        split: true,
                        layout: 'fit',
                        items: [UPRSRSIGrid],
                        minHeight: 0,
                        height: 300,
                    },
                    {
                        xtype: 'panel',
                        region: 'center',
                        border: false,
                        split: true,
                        layout: 'fit',
                        items: [CPRSRSIGrid],
                    },
                ],
            },
        ],
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    rateStructurePanel.on('activate', function (panel) {

        // because this tab is being displayed, demand the grids that it contain 
        // be populated
        CPRSRSIStore.reload();

        //URSRSIStore.reload();

        UPRSRSIStore.reload();

    });

    rateStructurePanel.on('expand', function (panel) {
    });
    rateStructurePanel.on('collapse', function (panel) {
    });


    ///////////////////////////////////////
    // Payments Tab

    var initialPayment =  {
        rows: [
        ]
    };

    var paymentReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'id',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'id', mapping: 'id'},
            {name: 'date_applied', mapping: 'date_applied'},
            {name: 'date_received', mapping: 'date_received'},
            {name: 'description', mapping: 'description'},
            {name: 'credit', mapping: 'credit'},
        ]
    });

    var paymentWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    var paymentStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/payment',
    });
    paymentStoreProxyConn.autoAbort = true;

    var paymentStoreProxy = new Ext.data.HttpProxy(paymentStoreProxyConn);

    var paymentStore = new Ext.data.JsonStore({
        proxy: paymentStoreProxy,
        reader: paymentReader,
        writer: paymentWriter,
        autoSave: true,
        // won't be updated when combos change, so do this in event
        // perhaps also can be put in the options param for the ajax request
        baseParams: { account:selected_account, sequence: selected_sequence},
        data: initialPayment,
        root: 'rows',
        idProperty: 'id',
        fields: [
            //{name: 'date_received', type: 'datetime',
                //dateFormat: Date.patterns['ISO8601Long']},
            {name: 'date_received', type: 'date',
                // server formats datetimes like "2011-09-12T00:00:00" and this matches the "c" format, but ext-js doesn't accept it this way
                dateFormat: "c"},
            {name: 'date_applied', type: 'date', dateFormat: 'Y-m-d'},
            {name: 'description'},
            {name: 'credit'},
            {name: 'editable'} // not visible in grid
        ],
    });

    paymentStore.on('load', function (store, records, options) {
        //console.log('paymentStore load');
        // the grid is disabled by the panel that contains it  
        // prior to loading, and must be enabled when loading is complete
        paymentGrid.setDisabled(false);
    });

    paymentStore.on('beforeload', function() {
        paymentGrid.setDisabled(true);
        paymentStore.setBaseParam("account", selected_account);
        paymentStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
    });

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    paymentStore.on('update', function(){
        //paymentGrid.getTopToolbar().findById('paymentSaveBtn').setDisabled(false);
    });

    paymentStore.on('beforesave', function() {
        paymentStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
        paymentStore.setBaseParam("account", selected_account);
    });

    function paymentColRenderer(value, metaData, record, rowIndex, colIndex,
            store) {
        if (record.data.editable) {
            metaData.css = 'payment-grid-editable';
        } else {
            metaData.css = 'payment-grid-frozen';
        }
        return value;
    }
    var paymentColModel = new Ext.grid.ColumnModel({
        columns: [
            new Ext.grid.DateColumn({
                header: 'Date Received',
                sortable: true,
                dataIndex: 'date_received',
                format: Date.patterns['ISO8601Long'],
                renderer: paymentColRenderer,
            }),
            new Ext.grid.DateColumn({
                header: 'Date Applied',
                sortable: true,
                dataIndex: 'date_applied',
                editor: new Ext.form.DateField({
                    allowBlank: false,
                    format: 'Y-m-d',
               }),
            }),
            {
                header: 'Description',
                sortable: true,
                dataIndex: 'description',
                renderer: paymentColRenderer,
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Credit',
                sortable: true,
                dataIndex: 'credit',
                renderer: paymentColRenderer,
                editor: new Ext.form.TextField({allowBlank: true})
            },
        ]
    });

    var paymentToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                id: 'paymentInsertBtn',
                iconCls: 'icon-add',
                text: 'Insert',
                disabled: false,
                handler: function() {
                    paymentGrid.stopEditing();

                    // grab the current selection - only one row may be selected per singlselect configuration
                    var selection = paymentGrid.getSelectionModel().getSelected();

                    // make the new record
                    var paymentType = paymentGrid.getStore().recordType;
                    var defaultData = 
                    {
                    };
                    var r = new paymentType(defaultData);
        
                    // select newly inserted record
                    //var insertionPoint = paymentStore.indexOf(selection);
                    //paymentStore.insert(insertionPoint + 1, r);
                    paymentStore.add([r]);
                    //paymentGrid.startEditing(insertionPoint +1,1);
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as aChargesGrid.removeBtn...
                id: 'paymentRemoveBtn',
                iconCls: 'icon-delete',
                text: 'Remove',
                disabled: true,
                handler: function()
                {
                    paymentGrid.stopEditing();
                    paymentStore.setBaseParam("account", selected_account);

                    // TODO single row selection only, test allowing multirow selection
                    var s = paymentGrid.getSelectionModel().getSelections();
                    for(var i = 0, r; r = s[i]; i++) {
                        paymentStore.remove(r);
                    }
                    paymentStore.save(); 
                }
            }
        ]
    });

    var paymentGrid = new Ext.grid.EditorGridPanel({
        tbar: paymentToolbar,
        colModel: paymentColModel,
        selModel: new Ext.grid.RowSelectionModel({
            singleSelect: true,
            listeners: {
                rowdeselect: function(selModel, index, record) {
                    paymentToolbar.find('id','paymentRemoveBtn')[0].setDisabled(true);
                },
                rowselect: function(selModel, index, record) {
                    paymentToolbar.find('id','paymentRemoveBtn')[0].setDisabled(!record.data.editable);
                },
            },
        }),
        store: paymentStore,
        enableColumnMove: false,
        animCollapse: false,
        stripeRows: true,
        clicksToEdit: 2
    });

/*    paymentGrid.getSelectionModel().on('selectionchange', function(sm){
        //paymentGrid.getTopToolbar().findById('paymentInsertBtn').setDisabled(sm.getCount() <1);
        paymentGrid.getTopToolbar().findById('paymentRemoveBtn').setDisabled(sm.getCount() <1);
    });*/

    // for bid editing of payments that the server says are not "editable"
    paymentGrid.on('beforeedit', function(e) {
        if (!e.record.data.editable) {
            return false;
        }
    });

    //
    // Instantiate the Payments panel
    //
    var paymentsPanel = new Ext.Panel({
        id: 'paymentTab',
        title: 'Payments',
        disabled: paymentPanelDisabled,
        layout: 'fit',
        layoutConfig : {
            pack : 'start',
            align : 'stretch',
        },
        items: [paymentGrid, ],
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed 
    paymentsPanel.on('activate', function (panel) {
        // because this tab is being displayed, demand the grids that it contain 
        // be populated
        // disable it during load, the datastore re-enables when loaded.
        paymentGrid.setDisabled(true);
        paymentStore.reload();

    });
  

    ///////////////////////////////////////
    // Mail Tab
    var mailDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/mail',
    });
    mailDataConn.autoAbort = true;
    mailDataConn.disableCaching = true;
    function mailReebillOperation(sequences) {
        Ext.Msg.prompt('Recipient', 'Enter comma seperated email addresses:', function (btn, recipients) {
            if (btn == 'ok') {
                mailDataConn.request({
                    params: {
                        account: selected_account,
                        recipients: recipients,
                        sequences: sequences,
                    },
                    success: function(response, options) {
                        var o = {};
                        try {
                            o = Ext.decode(response.responseText);}
                        catch(e) {
                            alert("Could not decode JSON data");
                        }
                        if (o.success == true) {
                            Ext.Msg.alert('Success', "mail successfully sent");
                        } else if (o.success !== true && o['corrections'] != undefined) {
                            var result = Ext.Msg.confirm('Corrections must be applied',
                                'Corrections from reebills ' + o.corrections +
                                ' will be applied to this bill as an adjusment of $'
                                + o.adjustment + '. Are you sure you want to issue it?', function(answer) {
                                    if (answer == 'yes') {
                                        mailDataConn.request({
                                            params: { account: selected_account, recipients: recipients, sequences: sequences, corrections: o.corrections},
                                            success: function(response, options) {
                                                var o2 = Ext.decode(response.responseText);
                                                if (o2.success == true)
                                                    Ext.Msg.alert('Success', "mail successfully sent");
                                                else
                                                    Ext.Msg.alert('Error', o2.errors.reason + o2.errors.details);
                                            },
                                            failure: function() {
                                                Ext.Msg.alert('Failure', "mail response fail");
                                            }
                                        });
                                    }
                                });
                        } else {
                            Ext.Msg.alert('Error', o.errors.reason + o.errors.details);
                        }
                    },
                    failure: function () {
                        Ext.Msg.alert('Failure', "mail response fail");
                    }
                });
            }
        });
    }

    var initialMailReebill =  {
        rows: [
        ]
    };

    var mailReebillReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'id',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'sequence', mapping: 'sequence'},
        ]
    });

    var mailReebillWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    var mailReeBillStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/reebill',
    });
    mailReeBillStoreProxyConn.autoAbort = true;
    var mailReeBillStoreProxy = new Ext.data.HttpProxy(mailReeBillStoreProxyConn);

    var mailReeBillStore = new Ext.data.JsonStore({
        proxy: mailReeBillStoreProxy,
        reader: mailReebillReader,
        writer: mailReebillWriter,
        autoSave: true,
        baseParams: { start:0, limit: 25},
        data: initialMailReebill,
        root: 'rows',
        totalProperty: 'results',
        //idProperty: 'sequence',
        fields: [
            {name: 'sequence'},
        ],
    });

    mailReeBillStore.on('beforesave', function() {
    });

    mailReeBillStore.on('update', function(){
    });

    mailReeBillStore.on('save', function () {
    });

    mailReeBillStore.on('beforeload', function (store, options) {

        // disable the grid before it loads
        mailReeBillGrid.setDisabled(true);

        // The Ext API is not clear on the relationship between options and baseParams
        // options appears to override baseParams.  Furthermore, start and limit appear
        // to be treated differently.  Need to scour the Ext source to figure this out.

        // account changed, reset the paging 
        if (store.baseParams.account && store.baseParams.account != selected_account) {
            // TODO: 26143175 start new account selection on the last page
            // reset pagination since it is a new account being loaded.
            options.params.start = 0;
        }

        options.params.account = selected_account;

        // set the current selection into the store's baseParams
        // so that the store can decide to load itself if it wants
        store.baseParams.account = selected_account;

    });

    // fired when the datastore has completed loading
    mailReeBillStore.on('load', function (store, records, options) {
        // was disabled prior to loading, and must be enabled when loading is complete
        mailReeBillGrid.setDisabled(false);
    });

    var mailReebillColModel = new Ext.grid.ColumnModel(
    {
        columns: [{
                header: 'Sequence',
                sortable: true,
                dataIndex: 'sequence',
                editor: new Ext.form.TextField({allowBlank: true})
            },
        ]
    });

    var mailReebillToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as aChargesGrid.removeBtn...
                id: 'mailReebillBtn',
                iconCls: 'icon-mail-go',
                text: 'Mail',
                disabled: false,
                handler: function()
                {
                    var sequences = [];
                    var s = mailReeBillGrid.getSelectionModel().getSelections();
                    for(var i = 0, r; r = s[i]; i++)
                    {
                        sequences.push(r.data.sequence);
                    }

                    mailReebillOperation(sequences);
                }
            }
        ]
    });

    // in the mail tab
    var mailReeBillGrid = new Ext.grid.GridPanel({
        flex: 1,
        tbar: mailReebillToolbar,
        bbar: new Ext.PagingToolbar({
            // TODO: constant
            pageSize: 25,
            store: mailReeBillStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No ReeBills to display",
        }),
        colModel: mailReebillColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: false}),
        store: mailReeBillStore,
        enableColumnMove: false,
        frame: true,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
    });

    mailReeBillGrid.getSelectionModel().on('selectionchange', function(sm){
    });
  
    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    mailReeBillStore.on('update', function(){
    });

    mailReeBillStore.on('beforesave', function() {
    });

    //
    // Instantiate the Mail panel
    //
    var mailPanel = new Ext.Panel({
        id: 'mailTab',
        title: 'Mail',
        disabled: mailPanelDisabled,
        layout: 'fit',
        layoutConfig : {
            align : 'stretch',
            pack : 'start'
        },
        items: [mailReeBillGrid, ]
    });
    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    mailPanel.on('activate', function (panel) {

        mailReeBillStore.reload();

    });


    ///////////////////////////////////////
    // Accounts Tab

    ///////////////////////////////////////
    // account status
    // TODO keep this as an example
    //function sortType(value){ 
    //    return parseInt(value.match(/\d+$/),10);
    //}
    var accountReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'id',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'account', mapping: 'account'},
            {name: 'fullname', mapping: 'fullname'},
            {name: 'dayssince', mapping: 'dayssince'/*, type:sortType*/},
            {name: 'lastissuedate'},
            {name: 'lastevent'},
            {name: 'provisionable', mapping: 'provisionable'},
        ]
    });

    var accountStoreProxyConn = new Ext.data.Connection({
        url: 'http://' + location.host + '/reebill/retrieve_account_status',
    });
    accountStoreProxyConn.autoAbort = true;
    var accountStoreProxy = new Ext.data.HttpProxy(accountStoreProxyConn);

    var accountStore = new Ext.data.JsonStore({
        proxy: accountStoreProxy,
        root: 'rows',
        totalProperty: 'results',
        remoteSort: true,
        paramNames: {start: 'start', limit: 'limit'},
        sortInfo: {
            field: defaultAccountSortField,
            direction: defaultAccountSortDir,
        },
        autoLoad: {params:{start: 0, limit: 30}},
        reader: accountReader,
        fields: [
            {name: 'account'},
            {name: 'codename'},
            {name: 'casualname'},
            {name: 'primusname'},
            {name: 'utilityserviceaddress'},
            {name: 'dayssince'},
            {name: 'lastevent'},
            {name: 'lastissuedate'},
            {name: 'provisionable'},
        ],
    });

    accountStore.on('beforeload', function(store, options) {
        accountGrid.setDisabled(true);
    });

    accountStore.on('load', function(store, options) {
        accountGrid.setDisabled(false);
    });

    /* This function controls the style of cells in the account grid. */
    var accountGridColumnRenderer = function(value, metaData, record, rowIndex, colIndex, store) {
        // probably the right way to do this is to set metaData.css to a CSS class name, but setting metaData.attr works for me.
        // see documentation for "renderer" config option of Ext.grid.Column

        // show text for accounts that don't yet exist in billing in gray;
        // actual billing accounts are black
        //if (record.data.provisionable) {
            //metaData.attr = 'style="color:gray"';
        //} else {
            //metaData.attr = 'style="color:black"';
        //}
        if (record.data.provisionable) {
            metaData.css = 'account-grid-gray';
        } else {
            metaData.css = 'account-grid-black';
        }
        return value;
    }

    var accountColModel = new Ext.grid.ColumnModel({
        columns: [
            {
                header: 'Account',
                sortable: true,
                dataIndex: 'account',
                renderer: accountGridColumnRenderer,
            },{
                header: 'Codename',
                sortable: true,
                dataIndex: 'codename',
                renderer: accountGridColumnRenderer,
            },{
                header: 'Casual Name',
                sortable: true,
                dataIndex: 'casualname',
                renderer: accountGridColumnRenderer,
            },{
                header: 'Primus Name',
                sortable: true,
                dataIndex: 'primusname',
                renderer: accountGridColumnRenderer,
            },{
                header: 'Utility Service Address',
                sortable: true,
                dataIndex: 'utilityserviceaddress',
                renderer: accountGridColumnRenderer,
            },{
                header: 'Last Issued',
                sortable: true,
                dataIndex: 'lastissuedate',
                renderer: accountGridColumnRenderer,
            },{
                header: 'Days Since Utility Bill',
                sortable: true,
                dataIndex: 'dayssince',
                renderer: accountGridColumnRenderer,
            },{
                header: 'Last Event',
                sortable: false,
                dataIndex: 'lastevent',
                renderer: accountGridColumnRenderer,
                width: 350,
            },
        ]
    });

    // this grid tracks the state of the currently selected account
    var accountGrid = new Ext.grid.EditorGridPanel({
        id: 'accountGrid',
        colModel: accountColModel,
        selModel: new Ext.grid.RowSelectionModel({
            singleSelect: true,
            listeners: {
                rowselect: function (selModel, index, record) {
                    loadReeBillUIForAccount(record.data.account);
                    return false;
                },
                rowdeselect: function(selModel, index, record) {
                    loadReeBillUIForAccount(null);
                    reeBillGrid.getSelectionModel().clearSelections();
                }
            },
        }),
        store: accountStore,
        enableColumnMove: false,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },

        title: 'Account Processing Status',

        // paging bar on the bottom
        bbar: new Ext.PagingToolbar({
            pageSize: 30,
            store: accountStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No statuses to display",
        }),
        clicksToEdit: 2,
    });

    accountGrid.getSelectionModel().on('beforerowselect', function(selModel, rowIndex, keepExisting, record) {
        return ! record.data.provisionable;
    });


    ///////////////////////////////////////
    // account ree_charges status

    var accountReeValueReader = new Ext.data.JsonReader({
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'account', mapping: 'account'},
            {name: 'olap_id', mapping: 'olap_id'},
            {name: 'casual_name', mapping: 'casual_name'},
            {name: 'primus_name', mapping: 'primus_name'},
            {name: 'ree_charges', mapping: 'ree_charges'},
            {name: 'actual_charges', mapping: 'actual_charges'},
            {name: 'hypothetical_charges', mapping: 'hypothetical_charges'},
            {name: 'total_energy', mapping: 'total_energy'},
            {name: 'average_ree_rate', mapping: 'average_ree_rate'},
            {name: 'outstandingbalance', mapping: 'outstandingbalance'},
            {name: 'days_late', mapping: 'days_late'},
        ]
    });

    var accountReeValueProxyConn = new Ext.data.Connection({
        url: 'http://' + location.host + '/reebill/summary_ree_charges',
    });
    accountReeValueProxyConn.autoAbort = true;
    var accountReeValueProxy = new Ext.data.HttpProxy(accountReeValueProxyConn);

    var accountReeValueOutstandingBalanceSort = function(value) {
        return parseFloat(value.substr(1));
    };

    var accountReeValueStore = new Ext.data.JsonStore({
        proxy: accountReeValueProxy,
        root: 'rows',
        totalProperty: 'results',
        //pageSize: 25,
        paramNames: {start: 'start', limit: 'limit'},
        //autoLoad: {params:{start: 0, limit: 25}},
        autoLoad: false,
        reader: accountReeValueReader,
        fields: [
            {name: 'account'},
            {name: 'olap_id'},
            {name: 'casual_name'},
            {name: 'primus_name'},
            {name: 'ree_charges'},
            {name: 'actual_charges'},
            {name: 'hypothetical_charges'},
            {name: 'total_energy'},
            {name: 'average_ree_rate'},
            {name: 'outstandingbalance', sortType: accountReeValueOutstandingBalanceSort},
            {name: 'days_late'},
        ],
    });

    var accountReeValueColModel = new Ext.grid.ColumnModel({
        columns: [
            {
                header: 'Account',
                sortable: true,
                dataIndex: 'account',
                editable: false,
            },{
                header: 'OLAP ID',
                sortable: true,
                dataIndex: 'olap_id',
                editable: false,
            },{
                header: 'Casual Name',
                sortable: true,
                dataIndex: 'casual_name',
                editable: false,
            },{
                header: 'Primus Name',
                sortable: true,
                dataIndex: 'primus_name',
                editable: false,
            },{
                header: 'REE Charges',
                sortable: true,
                dataIndex: 'ree_charges',
                editable: false,
            },{
                header: 'Total Utility Charges',
                sortable: true,
                dataIndex: 'actual_charges',
                editable: false,
            },{
                header: 'Hypothesized Utility Charges',
                sortable: true,
                dataIndex: 'hypothetical_charges',
                editable: false,
            },{
                header: 'Total Energy',
                sortable: true,
                dataIndex: 'total_energy',
                editable: false,
            },{
                header: 'Average Value per Therm of RE',
                sortable: true,
                dataIndex: 'average_ree_rate',
                editable: false,
            },{
                header: 'Outstanding Balance',
                sortable: true,
                dataIndex: 'outstandingbalance',
                //editable: false,
            },
            {
                header: 'Days Overdue',
                sortable: true,
                dataIndex: 'days_late',
            }
        ]
    });

    var accountReeValueToolbar = new Ext.Toolbar({
        items: [
            {
                id: 'accountReeValueExportCSVBtn',
                iconCls: 'icon-application-go',
                xtype: 'linkbutton',
                href: "http://"+location.host+"/reebill/reebill_details_xls",
                text: 'Export ReeBill XLS',
                disabled: false,
            },{
                id: 'exportButton',
                iconCls: 'icon-application-go',
                // TODO:25227403 - export one account at a time 
                xtype: 'linkbutton',
                href: "http://"+location.host+"/reebill/excel_export",
                text: 'Export All Utility Bills to XLS',
                disabled: false,
            },{
                id: 'exportAccountButton',
                iconCls: 'icon-application-go',
                xtype: 'linkbutton',
                // account parameter for URL is set in loadReeBillUIForAccount()
                href: "http://"+location.host+"/reebill/excel_export",
                text: "Export Selected Account's Utility Bills to XLS",
                disabled: true, // disabled until account is selected
            }]
    });

    // this grid tracks the state of the currently selected account

    var accountReeValueGrid = new Ext.grid.GridPanel({
        id: 'accountReeValueGrid',
        colModel: accountReeValueColModel,
        selModel: new Ext.grid.RowSelectionModel({
            singleSelect: true,
            listeners: {
                rowselect: function (selModel, index, record) {
                    loadReeBillUIForAccount(record.data.account);
                }
            }
        }),
        store: accountReeValueStore,
        enableColumnMove: false,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        title: 'Summary and Export',
        tbar: accountReeValueToolbar,
        bbar: new Ext.PagingToolbar({
            pageSize: 25,
            store: accountReeValueStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No statuses to display",
        }),
    });

    ///////////////////////////////////////
    // Create New Account 
    var newAccountTemplateStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/listAccounts',
    });
    newAccountTemplateStoreProxyConn.autoAbort = true;
    var newAccountTemplateStoreProxy = new Ext.data.HttpProxy(newAccountTemplateStoreProxyConn);

    // TODO: 26169525 lazy load
    var newAccountTemplateStore = new Ext.data.JsonStore({
        storeId: 'newAccountTemplateStore',
        autoDestroy: true,
        autoLoad: true,
        proxy: newAccountTemplateStoreProxy,
        root: 'rows',
        idProperty: 'account',
        fields: ['account', 'name'],
    });

    var newAccountTemplateCombo = new Ext.form.ComboBox({
        store: newAccountTemplateStore,
        fieldLabel: 'Based on',
        displayField:'name',
        valueField:'account',
        typeAhead: true,
        triggerAction: 'all',
        emptyText:'Select...',
        selectOnFocus:true,
        readOnly: false,
    });

    var newAccountFieldDataConn = new Ext.data.Connection({
        url: 'http://' + location.host + '/reebill/get_next_account_number',
    });
    newAccountFieldDataConn.autoAbort = true;
    newAccountFieldDataConn.disableCaching = true;
    var newAccountField = new Ext.form.TextField({
        fieldLabel: 'Account',
        name: 'account',
        allowBlank: false,
    });
    newAccountField.on('afterrender', function() {
        var nextAccount = '';
        newAccountFieldDataConn.request({
            success: function(result, request) {
                // check success status
                var jsonData = Ext.util.JSON.decode(result.responseText);
                newAccountField.setValue(jsonData['account']);
            },
            failure: function() {
                 Ext.MessageBox.alert('Ajax failure', 'http://' + location.host
                     + '/reebill/get_next_account_number');
            },
        });
    });

    var newNameField = new Ext.form.TextField({
        fieldLabel: 'Name',
        name: 'name',
        allowBlank: false,
    });
    var newDiscountRate = new Ext.form.TextField({
        fieldLabel: 'Discount Rate',
        name: 'discount_rate',
        allowBlank: false,
    });
    var newLateChargeRate = new Ext.form.TextField({
        fieldLabel: 'Late Charge Rate',
        name: 'late_charge_rate',
        allowBlank: false,
    });

    var moreAccountsCheckbox = new Ext.form.Checkbox({
        id: "newAccountCheckbox",
        boxLabel: "Make another account",
    });

    var newAccountDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/new_account',
    });
    newAccountDataConn.autoAbort = true;
    newAccountDataConn.disableCaching = true;
    var newAccountFormPanel = new Ext.FormPanel({
        id: 'newAccountFormPanel',
        url: 'http://'+location.host+'/reebill/new_account',
        labelWidth: 120, // label settings here cascade unless overridden
        frame: true,
        title: 'Create New Account',
        defaults: {
            anchor: '95%',
            xtype: 'textfield',
        },
        defaultType: 'textfield',
        items: [
            {
                xtype: 'fieldset',
                title: 'Account Information',
                id: 'accountInfoSet',
                collapsible: false,
                defaults: {
                    anchor: '0',
                },
                items: [
                    newAccountTemplateCombo, newAccountField, newNameField, newDiscountRate, newLateChargeRate,
                ],
            },
            {
                xtype: 'fieldset',
                title: 'Skyline Billing Address',
                id: 'billingAddressSet',
                collapsible: false,
                defaults: {
                    anchor: '0',
                },
                items: [
                    {
                        xtype: 'textfield',
                        id: 'new_ba_addressee',
                        fieldLabel: 'Addressee',
                        name: 'new_ba_addressee',
                    },{
                        xtype: 'textfield',
                        id: 'new_ba_street',
                        fieldLabel: 'Street',
                        name: 'new_ba_street',
                    },{
                        xtype: 'textfield',
                        id: 'new_ba_city',
                        fieldLabel: 'City',
                        name: 'new_ba_city',
                    },{
                        xtype: 'textfield',
                        id: 'new_ba_state',
                        fieldLabel: 'State',
                        name: 'new_ba_state',
                    },{
                        xtype: 'textfield',
                        id: 'new_ba_postal_code',
                        fieldLabel: 'Postal Code',
                        name: 'new_ba_postal_code',
                    },
                ]
            },{
                xtype: 'fieldset',
                title: 'Skyline Service Address',
                id: 'serviceAddressSet',
                collapsible: false,
                defaults: {
                    anchor: '0',
                },
                items: [
                    {
                        xtype: 'textfield',
                        id: 'new_sa_addressee',
                        fieldLabel: 'Addressee',
                        name: 'new_sa_addressee',
                    },{
                        xtype: 'textfield',
                        id: 'new_sa_street',
                        fieldLabel: 'Street',
                        name: 'new_sa_street',
                    },{
                        xtype: 'textfield',
                        id: 'new_sa_city',
                        fieldLabel: 'City',
                        name: 'new_sa_city',
                    },{
                        xtype: 'textfield',
                        id: 'new_sa_state',
                        fieldLabel: 'State',
                        name: 'new_sa_state',
                    },{
                        xtype: 'textfield',
                        id: 'new_sa_postal_code',
                        fieldLabel: 'Postal Code',
                        name: 'new_sa_postal_code',
                    },
                ]
            },
        ],
        buttons: [
            moreAccountsCheckbox,
            new Ext.Button({
                id: 'newAccountSaveButton',
                text: 'Save',
                handler: function(b, e) {
                    b.setDisabled(true);
                    // TODO 22645885 show progress during post
                    newAccountDataConn.request({
                        params: { 
                          'name': newNameField.getValue(),
                          'account': newAccountField.getValue(),
                          'template_account': newAccountTemplateCombo.getValue(), //obj.valueField
                          'discount_rate': newDiscountRate.getValue(),
                          'late_charge_rate': newLateChargeRate.getValue(),
                          'ba_addressee': Ext.getCmp('new_ba_addressee').getValue(),
                          'ba_street': Ext.getCmp('new_ba_street').getValue(),
                          'ba_city': Ext.getCmp('new_ba_city').getValue(),
                          'ba_state': Ext.getCmp('new_ba_state').getValue(),
                          'ba_postal_code': Ext.getCmp('new_ba_postal_code').getValue(),
                          'sa_addressee': Ext.getCmp('new_sa_addressee').getValue(),
                          'sa_street': Ext.getCmp('new_sa_street').getValue(),
                          'sa_city': Ext.getCmp('new_sa_city').getValue(),
                          'sa_state': Ext.getCmp('new_sa_state').getValue(),
                          'sa_postal_code': Ext.getCmp('new_sa_postal_code').getValue(),
                        },
                        success: function(result, request) {
                            var jsonData = null;
                            try {
                                jsonData = Ext.util.JSON.decode(result.responseText);
                                var nextAccount = jsonData['nextAccount'];
                                if (jsonData.success == false) {
                                    Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                                    console.log('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                                } else {
                                    Ext.Msg.alert('Success', "New account created");
                                    accountGrid.getSelectionModel().clearSelections();
                                    if (moreAccountsCheckbox.getValue()) {
                                        newNameField.reset();
                                        // don't reset any other fields
                                    } else {
                                        // update next account number shown in field
                                        accountsPanel.getLayout().setActiveItem('accountGrid');
                                        accountStore.setDefaultSort('account','DESC');
                                        pageSize = accountGrid.getBottomToolbar().pageSize;
                                        accountStore.load({params: {start: 0, limit: pageSize}, callback: function() {
                                            accountGrid.getSelectionModel().selectFirstRow();
                                        }});
                                        // reload grid to show new account
                                        // TODO "load" gets no records, "reload" gets records, but neither one causes the grid to update
                                        reeBillStore.reload({
                                            //callback: function(records, options, success) {
                                            //    alert('loaded!');
                                            //    console.log(records);
                                            //}
                                        });
                                        //Reset account info
                                        newAccountTemplateCombo.reset();
                                        //Addresses all have 'xtype' == 'textfield'
                                        var sets = newAccountFormPanel.findByType('fieldset')
                                        for (var i = 0;i < sets.length;i++) {
                                            var fields = sets[i].findByType('textfield');
                                            for (var j = 0;j < fields.length;j++) {
                                                fields[j].reset();
                                            }
                                        }
                                    }
                                    newAccountField.setValue(nextAccount);
                                }
                            } catch (err) {
                                Ext.MessageBox.alert('ERROR', 'Local:  '+ err + ' Remote: ' + result.responseText);
                            }
                            
                            b.setDisabled(false);
                            // TODO 22645885 confirm save and clear form
                        },
                        failure: function () {
                            Ext.Msg.alert("Create new account request failed");
                            b.setDisabled(false);
                        }
                    });
                }
            }),
        ],
    });


    //
    // Instantiate the Accounts panel
    //
    var accountsPanel = new Ext.Panel({
        id: 'statusTab',
        title: 'Accounts',
        disabled: accountsPanelDisabled,
        layout: 'accordion',
        items: [accountGrid, accountReeValueGrid, newAccountFormPanel, ]
    });

    ///////////////////////////////////////////////////////////////////////////
    // preferences tab
    // bill image resolution field in preferences tab (needs a name so its
    // value can be gotten)

    var billImageResolutionField = new Ext.ux.form.SpinnerField({
      id: 'billresolutionmenu',
      fieldLabel: 'Bill image resolution',
      name: 'billresolution',
      value: DEFAULT_RESOLUTION,
      minValue: 50,
      maxValue: 200,
      allowDecimals: false,
      decimalPrecision: 10,
      incrementValue: 10,
      alternateIncrementValue: 2.1,
      accelerate: true
    });

    var setPreferencesDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/setBillImageResolution',
    });
    setPreferencesDataConn.autoAbort = true;
    setPreferencesDataConn.disableCaching = true;
    var preferencesFormPanel = new Ext.FormPanel({
      labelWidth: 240, // label settings here cascade unless overridden
      frame: true,
      title: 'Image Resolution Preferences',
      bodyStyle: 'padding:5px 5px 0',
      //width: 610,
      defaults: {width: 435},
      layout: 'fit', 
      defaultType: 'textfield',
      items: [
        billImageResolutionField,
      ],
      buttons: [
        new Ext.Button({
            text: 'Save',
            handler: function() {
                setPreferencesDataConn.request({
                    params: { 'resolution': billImageResolutionField.getValue() },
                    success: function(result, request) {
                        var jsonData = null;
                        try {
                            jsonData = Ext.util.JSON.decode(result.responseText);
                            if (jsonData.success == false) {
                                Ext.Msg.alert("setBillImageResolution failed: " + jsonData.errors)
                            }
                            // handle failure here if necessary
                        } catch (err) {
                            Ext.MessageBox.alert('ERROR', 'Local:  '+ err + ' Remote: ' + result.responseText);
                        }
                    },
                    failure: function () {
                        Ext.Msg.alert("setBillImageResolution request failed");
                    }
                });
            }
        }),
      ],
    });

    // get initial value of this field from the server
    var getPreferencesDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/getBillImageResolution',
    });
    getPreferencesDataConn.autoAbort = true;
    getPreferencesDataConn.disableCaching = true;
    // TODO: 22360193 populating a form from Ajax creates a race condition.  
    // What if the network doesn't return and user enters a value nefore the callback is fired?
    var resolution = null;
    getPreferencesDataConn.request({
        success: function(result, request) {
            var jsonData = null;
            try {
                jsonData = Ext.util.JSON.decode(result.responseText);
                if (jsonData.success == true) {
                    resolution = jsonData['resolution'];
                    billImageResolutionField.setValue(resolution);
                } else {
                    // handle success:false here if needed
                }
            } catch (err) {
                Ext.MessageBox.alert('ERROR', 'Local:  '+ err + ' Remote: ' + result.responseText);
            }
        },
        failure: function () {
            Ext.Msg.alert("getBillImageResolution request failed");
        }
    });

    var differenceThresholdField = new Ext.ux.form.SpinnerField({
      id: 'differencethresholdmenu',
      fieldLabel: '$ Difference Allowed between Utility Bill and ReeBill',
      name: 'differencethreshold',
      value: DEFAULT_DIFFERENCE_THRESHOLD,
      minValue: 0,
      allowDecimals: true,
      decimalPrecision: 2,
      incrementValue: 1,
      accelerate: true
    });

    var setThresholdDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/setDifferenceThreshold',
    });
    setThresholdDataConn.autoAbort = true;
    setThresholdDataConn.disableCaching = true;
    var thresholdFormPanel = new Ext.FormPanel({
      labelWidth: 240, // label settings here cascade unless overridden
      frame: true,
      title: '$ Difference Allowed between Utility Bill and ReeBill',
      bodyStyle: 'padding:5px 5px 0',
      //width: 610,
      defaults: {width: 435},
      layout: 'fit', 
      defaultType: 'textfield',
      items: [
        differenceThresholdField,
      ],
      buttons: [
        new Ext.Button({
            text: 'Save',
            handler: function() {
                setThresholdDataConn.request({
                    params: { 'threshold': differenceThresholdField.getValue()},
                    success: function(result, request) {
                        var jsonData = null;
                        try {
                            jsonData = Ext.util.JSON.decode(result.responseText);
                            if (jsonData.success == false) {
                                Ext.Msg.alert("setDifferenceThreshold failed: " + jsonData.errors)
                            }
                            // handle failure here if necessary
                        } catch (err) {
                            Ext.MessageBox.alert('ERROR', 'Local:  '+ err + ' Remote: ' + result.responseText);
                        }
                    },
                    failure: function () {
                        Ext.Msg.alert("setDifferencethreshold request failed");
                    }
                });
            }
        }),
      ],
    });

    // get initial value of this field from the server
    var getThresholdDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/getDifferenceThreshold',
    });
    getThresholdDataConn.autoAbort = true;
    getThresholdDataConn.disableCaching = true;
    // TODO: 22360193 populating a form from Ajax creates a race condition.  
    // What if the network doesn't return and user enters a value nefore the callback is fired?
    var threshold = null;
    getThresholdDataConn.request({
        success: function(result, request) {
            var jsonData = null;
            try {
                jsonData = Ext.util.JSON.decode(result.responseText);
                if (jsonData.success == true) {
                    resolution = jsonData['threshold'];
                    differenceThresholdField.setValue(resolution);
                } else {
                    // handle success:false here if needed
                }
            } catch (err) {
                Ext.MessageBox.alert('ERROR', 'Local:  '+ err + ' Remote: ' + result.responseText);
            }
        },
        failure: function () {
            Ext.Msg.alert("getDifferenceThreshold request failed");
        }
    });
    
    //
    // Instantiate the Preference panel
    //
    var preferencesPanel = new Ext.Panel({
        id: 'preferencesTab',
        title: 'Preferences',
        disabled: preferencesPanelDisabled,
        layout: 'vbox',
        layoutConfig : {
            pack : 'start',
            align : 'stretch',
        },
        items: [preferencesFormPanel, thresholdFormPanel],
    });

    ///////////////////////////////////////
    // Journal Tab

    var initialjournal =  {
        rows: [
        ]
    };

    var journalReader = new Ext.data.JsonReader({
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: '_id', mapping: '_id'},
            {name: 'date', mapping: 'date'},
            {name: 'account', mapping: 'account'},
            {name: 'sequence', mapping: 'sequence'},
            {name: 'msg', mapping: 'msg'},
        ]
    });

    var journalWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    var journalStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/journal',
        timeout: 60000,
    });
    journalStoreProxyConn.autoAbort = true;
    var journalStoreProxy = new Ext.data.HttpProxy(journalStoreProxyConn);

    var journalStore = new Ext.data.JsonStore({
        proxy: journalStoreProxy,
        autoSave: false,
        reader: journalReader,
        writer: journalWriter,
        autoSave: true,
        data: initialjournal,
        root: 'rows',
        idProperty: '_id',
        sortInfo: {field: 'date', direction: 'DESC'},
        fields: [
            {name: '_id'},
            {
                name: 'date',
                type: 'date',
                //dateFormat: 'Y-m-d'
            },
            {name: 'user'},
            {name: 'account'},
            {name: 'sequence'},
            {name: 'event'},
            {name: 'msg'},
            //{name: 'extra'},
        ],
    });

    journalStore.on('beforesave', function() {
    });

    journalStore.on('update', function(){
    });

    journalStore.on('save', function () {
    });

    journalStore.on('beforeload', function (store, options) {
        journalGrid.setDisabled(true);

        // The Ext API is not clear on the relationship between options and baseParams
        // options appears to override baseParams.  Furthermore, start and limit appear
        // to be treated differently.  Need to scour the Ext source to figure this out.

        // account changed, reset the paging 
        if (store.baseParams.account && store.baseParams.account != selected_account) {
            // TODO: 26143175 start new account selection on the last page
            // reset pagination since it is a new account being loaded.
            options.params.start = 0;
        }

        options.params.account = selected_account;

        // set the current selection into the store's baseParams
        // so that the store can decide to load itself if it wants
        store.baseParams.account = selected_account;

    });

    // fired when the datastore has completed loading
    journalStore.on('load', function (store, records, options) {
        // was disabled prior to loading, and must be enabled when loading is complete
        journalGrid.setDisabled(false);
    });

    var journalColModel = new Ext.grid.ColumnModel({
        columns: [
            {
                header: 'Date',
                sortable: true,
                dataIndex: 'date',
                renderer: function(date) { if (date) return date.format(Date.patterns['ISO8601Long']); },
                editor: new Ext.form.DateField({
                    allowBlank: false,
                    format: Date.patterns['ISO8601Long'],
               }),
            },{
                header: 'User',
                sortable: true,
                dataIndex: 'user',
            },{
                header: 'Account',
                sortable: true,
                dataIndex: 'account',
                //hidden: true,
            },{
                header: 'Sequence',
                sortable: true,
                dataIndex: 'sequence',
            },{
                header: 'Event',
                sortable: true,
                dataIndex: 'event',
                width: 600,
            },/*{
                header: 'Data', // misc key-value pairs
                sortable: true,
                dataIndex: 'extra',
            },*/
        ]
    });
    /* TODO: 20493983 enable for admin user
    var journalToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                id: 'journalInsertBtn',
                iconCls: 'icon-add',
                text: 'Insert',
                disabled: false,
                handler: function()
                {
                    journalGrid.stopEditing();

                    // grab the current selection - only one row may be selected per singlselect configuration
                    var selection = journalGrid.getSelectionModel().getSelected();

                    // make the new record
                    var journalType = journalGrid.getStore().recordType;
                    var defaultData = 
                    {
                    };
                    var r = new journalType(defaultData);
        
                    // select newly inserted record
                    //var insertionPoint = journalStore.indexOf(selection);
                    //journalStore.insert(insertionPoint + 1, r);
                    journalStore.add([r]);
                    //journalGrid.startEditing(insertionPoint +1,1);
                    
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as aChargesGrid.removeBtn...
                id: 'journalRemoveBtn',
                iconCls: 'icon-delete',
                text: 'Remove',
                disabled: true,
                handler: function()
                {
                    journalGrid.stopEditing();
                    journalStore.setBaseParam("account", selected_account);

                    // TODO single row selection only, test allowing multirow selection
                    var s = journalGrid.getSelectionModel().getSelections();
                    for(var i = 0, r; r = s[i]; i++)
                    {
                        journalStore.remove(r);
                    }
                    journalStore.save(); 
                }
            }
        ]
    });
    journalGrid.getSelectionModel().on('selectionchange', function(sm){
        //journalGrid.getTopToolbar().findById('journalInsertBtn').setDisabled(sm.getCount() <1);
        journalGrid.getTopToolbar().findById('journalRemoveBtn').setDisabled(sm.getCount() <1);
    });
  
    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    journalStore.on('update', function(){
        //journalGrid.getTopToolbar().findById('journalSaveBtn').setDisabled(false);
    });

    */

    var journalGrid = new Ext.grid.GridPanel({
        flex: 1,
        //tbar: journalToolbar,
        colModel: journalColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: journalStore,
        enableColumnMove: false,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        // this is actually set in loadReeBillUIForAccount()
        title: 'Journal Entries for All Accounts',
        clicksToEdit: 2
    });

    //
    // Set up the journal memo widget
    //
    // account field
    var journalEntryField = new Ext.form.TextArea({
        fieldLabel: 'Journal',
        name: 'entry',
        flex: 1,
        allowBlank: false,
    });
    var journalEntryAccountField = new Ext.form.Hidden({
        name: 'account',
    });
    var journalEntrySequenceField = new Ext.form.Hidden({
        name: 'sequence',
    });
    // buttons
    var journalEntryResetButton = new Ext.Button({
        text: 'Reset',
        handler: function() {this.findParentByType(Ext.form.FormPanel).getForm().reset(); }
    });
    var journalEntrySubmitButton = new Ext.Button({
        text: 'Submit',
        // TODO: 20513861 clear form on success
        // TODO: 20514019 reload journal grid on success
        handler: function(b,e) {
            saveForm(b, e, function(b,e) {
                journalEntryField.reset();
                if (tabPanel.getActiveTab() == journalPanel) {
                    journalStore.reload();
                }
            })
        },
    });
    var journalFormPanel = new Ext.form.FormPanel({
        url: 'http://'+location.host+'/reebill/save_journal_entry',
        frame: true,
        border: false,
        height: 100,
        layout: 'vbox',
        anchor: '100% 100%',
        layoutConfig : {
            align: 'stretch',
            pack : 'start'
        },

        items: [
            journalEntryField, 
            journalEntryAccountField,
            journalEntrySequenceField,

            // a panel containing the buttons so they can be horizontal
            {
                xtype: 'panel',
                layout: 'hbox',
                layoutConfig : {
                    pack : 'end'
                },
                items: [
                    journalEntryResetButton,
                    journalEntrySubmitButton,
                ],
            }
        ],
        // hideLabels: false,
        // labelAlign: 'left',   // or 'right' or 'top'
        // labelSeparator: '', // takes precedence over layoutConfig value
        // labelWidth: 65,       // defaults to 100
        // labelPad: 8           // defaults to 5, must specify labelWidth to be honored
    });

    //
    // Instantiate the Journal panel
    //
    var journalPanel = new Ext.Panel({
        id: 'journalTab',
        title: 'Journal',
        disabled: journalPanelDisabled,
        xtype: 'panel',

        layout: 'vbox',
        layoutConfig : {
            align : 'stretch',
            pack : 'start'
        },

        items: [
            {
                xtype: 'panel',
                title: 'Add a Note',

                layout: 'anchor',
                anchor: '100%',
                align : 'stretch',
                pack : 'start',

                items: [
                    //{xtype: 'tbtext', text: 'Journal Entry'},
                    journalFormPanel,
                ],
                layoutConfig: {
                    align: 'stretch',
                    pack : 'start'
                },
                //height: 200,
            },
            journalGrid,
        ],
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    journalPanel.on('activate', function (panel) {

        journalStore.reload();

    });



    ///////////////////////////////////////////
    // Report Tab
    //


    // reconciliation report

    var reconciliationProxyConn = new Ext.data.Connection({
        url: 'http://' + location.host + '/reebill/get_reconciliation_data',
    });
    reconciliationProxyConn.autoAbort = true;
    var reconciliationProxy = new Ext.data.HttpProxy(reconciliationProxyConn);

    var reconciliationGridStore = new Ext.data.JsonStore({
        proxy: reconciliationProxy,
        root: 'rows',
        totalProperty: 'results',
        //baseParams: {},
        paramNames: {start: 'start', limit: 'limit'},
        // TODO enable autoload
        //autoLoad: {params:{start: 0, limit: 25}},
        // toolbar loads grid, so pagesize  doesn't have to be set
        //pageSize: 30,

        // default sort
        sortInfo: {field: 'sequence', direction: 'ASC'}, // descending is DESC
        remoteSort: true,
        fields: [
            {name: 'account'},
            {name: 'sequence'},
            {name: 'bill_therms'},
            {name: 'olap_therms'},
            {name: 'oltp_therms'},
            {name: 'errors'}
        ],
    });

    reconciliationGridStore.on('exception', function(type, action, options, response, arg) {
        //if (type == 'remote' && action == 'read' && response.success != true) {
            //// reconciliation report file is missing
            //Ext.Msg.alert('Error', response.raw.errors.reason + " " +
                    //response.raw.errors.details);
        //} else {
            //alert('reconciliationGridStore error');
            //// some other error
            //console.log(type)
            //console.log(action)
            //console.log(options)
            //console.log(response)
            //console.log(arg)
        //}
        // the above does not work because Ext sets 'type' to 'response'
        // instead of 'remote' even though the server returns 200 with
        // {success: false}
        Ext.Msg.alert('Error', 'Reconciliation report is not available (report file may not have been generated on the server).')
    });

    var reconciliationGrid = new Ext.grid.GridPanel({
        title:'Reconcilation Report: reebills with >0.1% difference from OLTP or errors',
        store: reconciliationGridStore,
        trackMouseOver:false,
        layout: 'fit',
        sortable: true,
        autoExpandColumn: 'errors',
        frame: true,
        // grid columns
        columns:[{
                id: 'account',
                header: 'Account',
                dataIndex: 'account',
                width: 80
            },
            {
                id: 'sequence',
                header: 'Sequence',
                dataIndex: 'sequence',
                width: 80
            },
            {
                id: 'bill_energy',
                header: 'Bill Energy (therms)',
                dataIndex: 'bill_therms',
                width: 150
            },
            {
                id: 'olap_energy',
                header: 'OLAP Energy (therms)',
                dataIndex: 'olap_therms',
                width: 150
            },
            {
                id: 'oltp_energy',
                header: 'OLTP Energy (therms)',
                dataIndex: 'oltp_therms',
                width: 150
            },
            {
                id: 'errors',
                header: 'Errors (see reconcilation log for details)',
                dataIndex: 'errors',
                forceFit:true
            },
        ],
        // paging bar on the bottom
        bbar: new Ext.PagingToolbar({
            pageSize: 30,
            store: reconciliationGridStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "Click the refresh button to show some data.",
        }),
    });

    // "Estimated Revenue" grid

    var revenueProxyConn = new Ext.data.Connection({
        url: 'http://' + location.host + '/reebill/get_estimated_revenue_data',
        timeout: 60000,
    });
    revenueProxyConn.autoAbort = true;
    var revenueProxy = new Ext.data.HttpProxy(revenueProxyConn);

    var revenueGridStore = new Ext.data.JsonStore({
        proxy: revenueProxy,
        root: 'rows',
        totalProperty: 'results',
        //baseParams: {},
        paramNames: {start: 'start', limit: 'limit'},
        // TODO enable autoload
        //autoLoad: {params:{start: 0, limit: 25}},
        //pageSize: 30,

        // default sort
        sortInfo: {field: 'sequence', direction: 'ASC'}, // descending is DESC
        remoteSort: true,
        fields: [
            {name: 'account', mapping: 'account'},
            {name: 'revenue_11_months_ago'},
            {name: 'revenue_10_months_ago'},
            {name: 'revenue_9_months_ago'},
            {name: 'revenue_8_months_ago'},
            {name: 'revenue_7_months_ago'},
            {name: 'revenue_6_months_ago'},
            {name: 'revenue_5_months_ago'},
            {name: 'revenue_4_months_ago'},
            {name: 'revenue_3_months_ago'},
            {name: 'revenue_2_months_ago'},
            {name: 'revenue_1_months_ago'},
            {name: 'revenue_0_months_ago'},
        ],
    });

    revenueGridStore.on('exception', function(type, action, options, response, arg) {
        // TODO  28823361 better error message when server hangs up on us
        Ext.Msg.alert('Error', 'An error occurred while generating the report');
    });

    var revenueColumnRenderer = function(value, metaData, record, rowIndex, colIndex, store) {
        // revenueGridStore records are objects containing keys "value",
        // "error" and/or "estimated". set the style according to that data,
        // then set the actual text to display to the value of the "value" key
        // in the record
        if (value.value.indexOf("ERROR") == 0) {
            metaData.css = 'revenue-grid-error';
            return value.value;
        }

        if (value.estimated) {
            metaData.css = 'revenue-grid-estimated';
        } else {
            metaData.css = 'revenue-grid-normal';
        }
        return "$" + value.value;
    }

    /* dynamically generate estimated revenue grid columns */
    var revenueGridColumns = [{
        id: 'account',
        header: 'Account',
        dataIndex: 'account',
        forceFit:true,
    }];
    var monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
        'Sep', 'Oct', 'Nov', 'Dec'];
    var now = new Date();
    var curYear = now.getUTCFullYear();
    var curMonth = now.getUTCMonth();
    var year; var month; var ago = 11;
    if (curMonth == 11) { // December (months are numbered from 0)
        year = curYear;
        month = 1;
    } else {
        year = curYear - 1;
        month = curMonth + 1;
    }
    while (year < curYear || (year == curYear && month <= curMonth)) {
        month_str = monthNames[month] + " " + year;
        revenueGridColumns.push({
            id: ago.toString() + '_months_ago',
            header: month_str,
            dataIndex: 'revenue_' + ago + '_months_ago',
            width: 95, 
            renderer: revenueColumnRenderer,
        });
        if (month == 11) {
            year++;
            month = 0;            
        } else {
            month++;
        }
        ago--;
    }

    var revenueGrid = new Ext.grid.GridPanel({
        title:'12-Month Estimated Revenue',
        store: revenueGridStore,
        trackMouseOver:false,
        layout: 'fit',
        sortable: true,
        autoExpandColumn: 'account',
        frame: true,

        // grid columns
        columns: revenueGridColumns,

        // toolbar on the top with a download button
        tbar: new Ext.Toolbar({
            items: [
                {
                    id: 'estimatedRevenueDownloadButton',
                    iconCls: 'icon-application-go',
                    xtype: 'linkbutton',
                    href: "http://"+location.host+"/reebill/estimated_revenue_xls",
                    text: 'Download Excel Spreadsheet',
                    disabled: false,
                },]
        }),

        // paging bar on the bottom
        bbar: new Ext.PagingToolbar({
            pageSize: 30,
            store: revenueGridStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "Click the refresh button to generate the report (may take a few minutes).",
        }),
    });

    // reebill export XLS report (with date ranges)

    var reebillExportComboBox = new Ext.form.ComboBox({
        store: newAccountTemplateStore,
        fieldLabel: 'Account',
        displayField:'account', //will be submitted by default, by a form post
        valueField:'name', //must get at this with a myStore.getValue() call
        typeAhead: true,
        triggerAction: 'all',
        emptyText:'All',
        selectOnFocus:true,
        readOnly: false,
        width: 500,
    });
   
    // date fields
    var reebillExportStartDateField = new Ext.form.DateField({
        fieldLabel: 'Begin Date',
        name: 'begin_date',
        width: 90,
        allowBlank: true,
        format: 'Y-m-d'
    });

    var reebillExportEndDateField = new Ext.form.DateField({
        fieldLabel: 'End Date',
        name: 'end_date',
        width: 90,
        allowBlank: true,
        format: 'Y-m-d'
    });

    var reebillExportSubmitButton = new Ext.Button({
        text: 'Download XLS',
        handler: function(b, e) {
            //You cannot simply call saveForm, because it needs to be able to find its parent.
            //Using 'this' as the scope tells it that it is not just in an anonymus function.
            saveForm(b, e, function(b,e) {
                //TODO: 36276789 redirect (or something) to trigger a download of the spreadsheet that gets returned by the WSGI method
            })
        },
    });

    var reebillExportPanel = new Ext.form.FormPanel({
        id: 'reebillExportPanel',
        url: 'http://'+location.host+'/reebill/reebill_details_xls',
        labelwidth: 120,
        frame: true,
        title: "Export ReeBill XLS",
        border: false,
        defaults: {
            anchor: '95%',
            xtype: 'textfield',
        },
        defaultType: 'textfield',
        items: [
            {
                xtype: 'fieldset',
                id: 'reebillExportPanelForm',
                collapsible: false,
                defaults: {
                    anchor: '0',
                },
                items: [
                    reebillExportComboBox,
                    reebillExportStartDateField,
                    reebillExportEndDateField,
                ],
            },
        ],
        buttons: [
            reebillExportSubmitButton,
            ]

    });


    //
    // Instantiate the Report panel
    //
    var reportPanel = new Ext.Panel({
        id: 'reportTab',
        title: 'Reports',
        disabled: reportPanelDisabled,
        //xtype: 'panel',
        layout: 'accordion',
        items: [reconciliationGrid, revenueGrid, reebillExportPanel],
    });

    ///////////////////////////////////////////
    // About Tab
    //
    var aboutPanel = new Ext.Panel({
        id: 'aboutTab',
        title: 'About',
        disabled: aboutPanelDisabled,
    });

    // end of tab widgets
    ////////////////////////////////////////////////////////////////////////////

    ///////////////////////////////////////////////////////////////////////////
    //Issuable Reebills Tab
    //Show all unissued reebills, show the reebills whose totals match their
    //  utilbills first
    
    var initialIssuable = {
        rows: [
        ]
    };

    var issuableReader = new Ext.data.JsonReader({
        root: 'rows',
        totalProperty: 'total',
        fields: [
            {name: 'id', mapping: 'id'},
            {name: 'account', mapping: 'account'},
            {name: 'sequence', mapping: 'sequence'},
            {name: 'mailto', mapping: 'mailto'},
            {name: 'util_total', mapping: 'util_total'},
            {name: 'reebill_total', mapping: 'reebill_total'},
            {name: 'matching', mapping: 'matching'},
            {name: 'difference', mapping: 'difference'},
        ],
    });

    var issuableWriter = new Ext.data.JsonWriter({
        encode: true,
        writeAllFields: true
    });

    var issuableStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/issuable'
    });
    issuableStoreProxyConn.autoAbort = true;
    issuableStoreProxyConn.disableCaching = true;
    
    var issuableStoreProxy = new Ext.data.HttpProxy(issuableStoreProxyConn);

    var issuableStore = new Ext.data.GroupingStore({
        proxy: issuableStoreProxy,
        reader: issuableReader,
        writer: issuableWriter,
        autoSave: true,
        baseParams: {start: 0, limit: 25},
        data: initialIssuable,
        groupField: 'matching',
        sortInfo:{field: 'account', direction: 'ASC'},
        remoteSort: true,
    });
    
    issuableStore.on('beforeload', function () {
        issuableGrid.setDisabled(true);
    });
    
    issuableStore.on('load', function() {
        issuableGrid.setDisabled(false);
    });

    issuableMailListRegex = new RegExp("^[\\w!#$%&'*+\\-/=?^_`{\\|}~](\\.?[\\w!#$%&'*+\\-/=?^_`{\\|}~])*@[\\w-](\\.?[\\w-])*(,\\s*[\\w!#$%&'*+\\-/=?^_`{\\|}~](\\.?[\\w!#$%&'*+\\-/=?^_`{\\|}~])*@[\\w-](\\.?[\\w-])*)*$")

    var issuableColModel = new Ext.grid.ColumnModel({
        columns: [
            {
                id: 'matching',
                header: '',
                width: 160,
                sortable: true,
                dataIndex: 'matching',
                hidden: true,
            },{
                id: 'account',
                header: 'Account',
                width: 75,
                sortable: true,
                groupable: false,
                dataIndex: 'account',
                editable: false,
                editor: new Ext.form.TextField(),
            },{
                id: 'sequence',
                header: 'Sequence',
                width: 75,
                sortable: false,
                groupable: false,
                dataIndex: 'sequence',
                editable: false,
                editor: new Ext.form.TextField(),
            },{
                id: 'mailto',
                header: 'Recipients',
                sortable: false,
                groupable: false,
                dataIndex: 'mailto',
                editable: true,
                editor: new Ext.form.TextField({
                    //regex: issuableMailListRegex,
                }),
                renderer: function(v, params, record)
                {
                    if (Ext.isEmpty(record.data.mailto))
                    {
                        return "<i>Enter a recipient for this bill before issuing</i>";
                    }
                    return record.data.mailto;
                }
            },{
                id: 'util_total',
                header: 'Total From Utility Bill',
                width: 140,
                sortable: false,
                groupable: false,
                dataIndex: 'util_total',
                editable: false,
                editor: new Ext.form.NumberField(),
                renderer: function(v, params, record)
                {
                    return Ext.util.Format.usMoney(record.data.util_total);
                },
            },{
                id: 'reebill_total',
                header: 'Computed Total',
                width: 140,
                sortable: false,
                groupable: false,
                dataIndex: 'reebill_total',
                editable: false,
                editor: new Ext.form.NumberField(),
                renderer: function(v, params, record)
                {
                    return Ext.util.Format.usMoney(record.data.reebill_total);
                },
            },{
                id: 'difference',
                header: '$ Difference',
                width: 125,
                sortable: true,
                groupable: false,
                dataIndex: 'difference',
                editable: false,
                editor: new Ext.form.NumberField(),
                renderer: function(v, params, record)
                {
                    return Ext.util.Format.usMoney(record.data.util_total - record.data.reebill_total);
                },
            },
        ],
    });

    var issueDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/issue_and_mail',
    });
    issueDataConn.autoAbort = true;
    issueDataConn.disableCaching = true;
    
    var issuableCurrentlyEditing = false;
    
    var issueReebillButton = new Ext.Button({
        xtype: 'button',
        id: 'issueReebillBtn',
        iconCls: 'icon-mail-go',
        text: 'Issue',
        disabled: true,
        handler: function()
        {
            var r = issuableGrid.getSelectionModel().getSelected();
            issuableGrid.setDisabled(true);
            issueDataConn.request({
                params: {
                    account: r.data.account,
                    sequence: r.data.sequence,
                    apply_corrections: false,
                },
                success: function (response, options) {
                    var o = {};
                    try {
                        o = Ext.decode(response.responseText);
                    }
                    catch(e) {
                        Ext.Msg.alert("Data Error", "Could not decode response from server");
                        return;
                        issuableStore.reload();
                        issuableGrid.setDisabled(false);
                    }
                    if (o.success == true) {
                        Ext.Msg.alert("Success", "Mail successfully sent");
                        issuableGrid.getSelectionModel().clearSelections();
                        issuableStore.reload();
                        issuableGrid.setDisabled(false);
                    }
                    else if (o.success !== true && o.corrections != undefined) {
                        var result = Ext.Msg.confirm('Corrections must be applied',
                                                     'Corrections from reebills ' + o.corrections +
                                                     ' will be applied to this bill as an adjusment of $'
                                + o.adjustment + '. Are you sure you want to issue it?', function(answer) {
                                    if (answer == 'yes') {
                                        issueDataConn.request({
                                            params: { account: r.data.account, sequence: r.data.sequence, apply_corrections: true},
                                            success: function(response, options) {
                                                var o2 = Ext.decode(response.responseText);
                                                if (o2.success == true) {
                                                    Ext.Msg.alert("Success", "Mail successfully sent");
                                                    issuableGrid.getSelectionModel().clearSelections();
                                                }
                                                else
                                                    Ext.Msg.alert('Error', o2.errors.reason + "\n" + o2.errors.details);
                                                issuableStore.reload();
                                                issuableGrid.setDisabled(false);
                                            },
                                            failure: function() {
                                                Ext.Msg.alert('Failure', "Connection Failure");
                                                issuableStore.reload();
                                                issuableGrid.setDisabled(false);
                                            }
                                        });
                                    }
                                });
                    }
                    else {
                        Ext.Msg.alert('Error', o.errors.reason + "\n" + o.errors.details);
                        issuableStore.reload();
                        issuableGrid.setDisabled(false);
                    }
                },
                failure: function () {
                    Ext.Msg.alert('Failure', "Connection Failure");
                    issuableStore.reload();
                    issuableGrid.setDisabled(false);
                }
            });
        },
    });
    
    var issueReebillToolbar = new Ext.Toolbar({
        items: [
            issueReebillButton,
        ],
    });
    
    var issuableGrid = new Ext.grid.EditorGridPanel({
        colModel: issuableColModel,
        selModel: new Ext.grid.RowSelectionModel({
            singleSelect: true,
            moveEditorOnEnter: false,
            listeners: {
                rowselect: function (selModel, index, record) {
                    issueReebillButton.setDisabled(!issuableMailListRegex.test(record.data.mailto));
                    loadReeBillUIForAccount(record.data.account);
                },
                rowdeselect: function (selModel, index, record) {
                    issueReebillButton.setDisabled(true);
                    accountGrid.getSelectionModel().clearSelections();
                    reeBillGrid.getSelectionModel().clearSelections();
                },
            },
        }),
        tbar: issueReebillToolbar,
        bbar: new Ext.PagingToolbar({
            pageSize: 25,
            store: issuableStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: 'No ReeBills to display',
        }),
        store: issuableStore,
        enableColumnMove: false,
        view: new Ext.grid.GroupingView({
            forceFit: false,
            groupTextTpl: '{[values.gvalue==true?"Reebill"+(values.rs.length>1?"s":"")+" with Matching Totals":"Reebill"+(values.rs.length>1?"s":"")+" without Matching Totals"]}',
            showGroupName: false,
        }),
        frame: true,
        animCollapse: false,
        stripeRows: true,
        autoExpandColumn: 'mailto',
        height: 900,
        width: 1000,
        clicksToEdit: 2,
        forceValidation: true,
    });
    
    issuableGrid.on('validateedit', function (e /*{grid, record, field, value, originalValue, row, column}*/ ) {
        oldAllowed = issuableMailListRegex.test(e.originalValue)
        allowed = issuableMailListRegex.test(e.value);
        issueReebillButton.setDisabled((!allowed && !oldAllowed) || e.value == '');
        if (!allowed && e.value != '') {
            Ext.Msg.alert('Invalid Input','Please input a comma seperated list of email addresses.')
        }
        return allowed || e.value == ''
    });

    issuableGrid.on('beforeedit', function () {
        issueReebillButton.setDisabled(true);
    });
    
    var  issuablePanel = new Ext.Panel({
        id: 'issuableTab',
        title: 'Issuable Reebills',
        disabled: issuablePanelDisabled,
        layout: 'fit',
        layoutConfig : { align : 'stretch', pack : 'start' },
        items: [issuableGrid,],
    });

    issuablePanel.on('activate', function(panel) {
        issuableStore.reload();
    });


    ////////////////////////////////////////////////////////////////////////////
    // Reebill Charges tab
    //

    var hChargesReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        idProperty: 'uuid',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'chargegroup', mapping: 'chargegroup'},
            {name: 'uuid', mapping: 'uuid'},
            {name: 'rsi_binding', mapping: 'rsi_binding'},
            {name: 'description', mapping: 'description'},
            {name: 'actual_quantity', mapping: 'actual_quantity'},
            {name: 'quantity', mapping: 'quantity'},
            {name: 'quantity_units', mapping: 'quantity_units'},
            {name: 'actual_rate', mapping: 'actual_rate'},
            {name: 'rate', mapping: 'rate'},
            {name: 'rate_units', mapping: 'rate_units'},
            {name: 'actual_total', mapping: 'actual_total', type: 'float'},
            {name: 'total', mapping: 'total', type: 'float'},
            {name: 'processingnote', mapping:'processingnote'},
        ]
    });
    
    var hChargesWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });
    
    var hChargesStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/hypotheticalCharges',
        disableCaching: true,
    })
    hChargesStoreProxyConn.autoAbort = true;

    var hChargesStoreProxy = new Ext.data.HttpProxy(hChargesStoreProxyConn);

    var hChargesStore = new Ext.data.GroupingStore({
        proxy: hChargesStoreProxy,
        autoSave: true,
        reader: hChargesReader,
        //root: 'rows',
        //idProperty: 'uuid',
        writer: hChargesWriter,
        data: {rows:[]},
        sortInfo:{field: 'chargegroup', direction: 'ASC'},
        groupField:'chargegroup'
    });

    hChargesStore.on('beforeload', function (store, options) {
        hChargesGrid.setDisabled(true);
        options.params.service = Ext.getCmp('service_for_charges').getValue();
        options.params.account = selected_account;
        options.params.sequence = selected_sequence;
    });
    
    hChargesStore.on('load', function (store, records, options) {
        hChargesGrid.setDisabled(false);
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
                hidden: true,
            },{
                header: 'UUID',
                width: 75,
                sortable: true,
                dataIndex: 'uuid',
                hidden: true,
            },{
                header: 'RSI Binding',
                sortable: true,
                dataIndex: 'rsi_binding',
            },{
                header: 'Description',
                width: 75,
                sortable: true,
                dataIndex: 'description',
            },{
                header: 'Actual Quantity',
                width: 75,
                sortable: true,
                dataIndex: 'actual_quantity',
            },{
                header: 'Hypo Quantity',
                width: 75,
                sortable: true,
                dataIndex: 'quantity',
            },{
                header: 'Units',
                width: 75,
                sortable: true,
                dataIndex: 'quantity_units',
            },{
                header: 'Actual Rate',
                width: 75,
                sortable: true,
                dataIndex: 'actual_rate',
            },{
                header: 'Hypo Rate',
                width: 75,
                sortable: true,
                dataIndex: 'rate',
            },{
                header: 'Units',
                width: 75,
                sortable: true,
                dataIndex: 'rate_units',
            },{
                header: 'Actual Total', 
                width: 75, 
                sortable: true, 
                summaryType: 'sum',
                align: 'right',
                renderer: function(v, params, record)
                {
                    return Ext.util.Format.usMoney(record.data.actual_total);
                }
            },{
                header: 'Hypo Total', 
                width: 75, 
                sortable: true, 
                summaryType: 'sum',
                align: 'right',
                renderer: function(v, params, record)
                {
                    return Ext.util.Format.usMoney(record.data.total);
                }
            },
        ]
    });
    
    var hChargesGrid = new Ext.grid.GridPanel({
        colModel: hChargesColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: hChargesStore,
        enableColumnMove: false,
        view: new Ext.grid.GroupingView({
            forceFit:true,
            groupTextTpl: '{text} ({[values.rs.length]} {[values.rs.length > 1 ? "Items" : "Item"]})'
        }),
        plugins: hChargesSummary,
        flex: 1,
        stripeRows: true,
        autoExpandColumn: 'rsi_binding',
    });

    reebillChargesPanel = new Ext.Panel({
        id: 'hChargesPanelTab',
        title: 'Reebill Charges',
        disabled: reebillChargesPanelDisabled,
        layout: 'vbox',
        layoutConfig : {
            align : 'stretch',
            pack : 'start'
        },
        items: [
            hChargesGrid,
        ],
    });
    
    reebillChargesPanel.on('activate', function (panel) {
        // because this tab is being displayed, demand the grids that it contain 
        // be populated
        hChargesStore.load();
    });
    

    ////////////////////////////////////////////////////////////////////////////
    // Status bar displayed at footer of every panel in the tabpanel

    var statusBar = new Ext.ux.StatusBar({
        defaultText: 'No REE Bill Selected',
        id: 'statusbar',
        statusAlign: 'right', // the magic config
        
        //items: [{xtype: 'tbtext', text: 'Journal Entry'},journalFormPanel]
        items: [],
    });

    ////////////////////////////////////////////////////////////////////////////
    // construct tabpanel and the panels it contains for the viewport

    // Assemble all of the above panels into a parent tab panel
    var tabPanel = new Ext.TabPanel({
        id: 'tabPanel',
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
            accountsPanel,
            utilityBillPanel,
            ubMeasuredUsagesPanel,
            rateStructurePanel,
            chargeItemsPanel,
            paymentsPanel,
            reeBillPanel,
            reebillChargesPanel,
            issuablePanel,
            mailPanel,
            journalPanel,
            reportPanel,
            preferencesPanel,
            aboutPanel,
        ]
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
            bodyStyle: 'background-image:url("green_stripe.jpg");',
            html: '<div id="header" style=""><table style="border-collapse: collapse;"><tr><td><img src="skyline_logo.png"/></td><td><img src="reebill_logo.png"/></td><td style="width: 85%; text-align: right;"><img src="money_chaser.png"/></td></tr></table></div>',
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
            bodyStyle: 'background-image:url("green_stripe.jpg");',
            html: '<div id="footer" style="padding-top:7px;"><div style="display: inline; float: left;">&#169;2009-2012 <a href="http://www.skylineinnovations.com">Skyline Innovations Inc.</a></div><div id="LOGIN_INFO" style="display: inline; padding:0px 15px 0px 15px;">LOGIN INFO</div><div id="SKYLINE_VERSIONINFO" style="display: inline; float: right; padding:0px 15px 0px 15px;">VERSION INFO</div><div id="SKYLINE_DEPLOYENV" style="display: inline; float: right;">DEPLOYMENT ENV</div></div>',
          },
        ]
      }
    );

    // update selection in statusbar
    function updateStatusbar(account, sequence, branch)
    {

        var sb = Ext.getCmp('statusbar');
        var selStatus = "No REE Bill Selected";
        if (account != null && sequence != null && branch != null)
            selStatus = account + "-" + sequence + "-" + branch;
        else if (account != null && sequence != null)
            selStatus = account + "-" + sequence;
        else if (account != null)
            selStatus = account;

        sb.setStatus({
            text: selStatus
        });
    }

    // whenever an account is selected from the Account tab,
    // update all other dependent widgets

    var lastUtilBillEndDateDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/last_utilbill_end_date',
    });
    lastUtilBillEndDateDataConn.autoAbort = true;
    lastUtilBillEndDateDataConn.disableCaching = true;

    // load things global to the account
    function loadReeBillUIForAccount(account) {
        selected_account = account;
        selected_sequence = null;

        // a new account has been selected, deactivate subordinate tabs
        ubMeasuredUsagesPanel.setDisabled(true);
        rateStructurePanel.setDisabled(true);
        chargeItemsPanel.setDisabled(true);
        accountInfoFormPanel.setDisabled(true);
        Ext.getCmp('service_for_charges').getStore().removeAll();
        Ext.getCmp('service_for_charges').clearValue();
        Ext.getCmp('service_for_charges').setDisabled(true);

        //journalPanel.setDisabled(true);

        // TODO: 25226989 ajax cancelled???
        // unload previously loaded utility and reebill images
        // TODO 25226739: don't overwrite if they don't need to be updated.  Causes UI to flash.
        Ext.DomHelper.overwrite('utilbillimagebox', getImageBoxHTML(null, 'Utility bill', 'utilbill', NO_UTILBILL_SELECTED_MESSAGE), true);
        Ext.DomHelper.overwrite('reebillimagebox', getImageBoxHTML(null, 'Reebill', 'reebill', NO_REEBILL_SELECTED_MESSAGE), true);

        //Update the buttons on the reebill tab
        deleteButton.setDisabled(true)
        versionButton.setDisabled(true);
        if (account == null) {
            /* no account selected */
            updateStatusbar(null, null, null)
            journalGrid.setTitle('Journal Entries for All Accounts');
            return;
        }

        // update list of ReeBills (for mailing) for this account
        //mailReeBillStore.setBaseParam("account", account)

        // paging tool bar params must be passed in to keep store in sync with toolbar paging calls - autoload params lost after autoload
        //mailReeBillStore.reload({params:{start:0, limit:25}});


        // add the account to the upload_account field
        upload_account.setValue(account)

        // set begin date for next utilbill in upload form panel to end date of
        // last utilbill, if there is one
        // TODO 25226989:tId not tracked! 
        lastUtilBillEndDateDataConn.request({
            params: {account: account},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false) {
                        // handle failure here if necessary
                    } else {
                        // server returns null for the date if there is no utilbill
                        if (jsonData['date'] == null) {
                            // clear out date that was there before, if any
                            uploadStartDateField.setValue('');
                        } else {
                            var lastUtilbillDate = new Date(jsonData['date']);
                            // field automatically converts Date into a string
                            // according to its 'format' property
                            uploadStartDateField.setValue(lastUtilbillDate);
                        }
                    } 
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err + ' Remote: ' + result.responseText);
                }
            },
            failure: function() {alert("ajax failure")},
        });

        // update the journal form panel so entries get submitted to currently selected account
        // need to set account into a hidden field here since there is no data store behind the form
        journalFormPanel.getForm().findField("account").setValue(account)
        // TODO: 20513861 clear reebill data when a new account is selected
        journalFormPanel.getForm().findField("sequence").setValue(null)

        updateStatusbar(account, null, null);


        // enable export buttons 
        Ext.getCmp('exportAccountButton').setDisabled(false);
        Ext.getCmp('exportAccountButton').setParams({'account': account});
        Ext.getCmp('dailyAverageEnergyExportButton').setDisabled(false);
        Ext.getCmp('dailyAverageEnergyExportButton').setParams({'account': account});
        //Ext.getCmp('exportButton').setDisabled(false);
        Ext.getCmp('accountReeValueExportCSVBtn').setDisabled(false);

        // an account has been selected, so enable tabs that act on an account
        reeBillPanel.setDisabled(false);
        paymentsPanel.setDisabled(false);
        utilityBillPanel.setDisabled(false);
        journalPanel.setDisabled(false);
        mailPanel.setDisabled(false);

        journalGrid.setTitle('Journal Entries for Account ' + account);
    }


    //
    // configure data connections for widgets that are not managed by 
    // datastores.
    //
    var ubMeasuredUsagesDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/ubMeasuredUsages',
    });
    ubMeasuredUsagesDataConn.autoAbort = true;
    ubMeasuredUsagesDataConn.disableCaching = true;



    var reeBillImageDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/getReeBillImage',
    });
    reeBillImageDataConn.autoAbort = true;
    reeBillImageDataConn.disableCaching = true;

    function loadReeBillUIForSequence(account, sequence) {
        /* null argument means no sequence is selected */

        // get selected reebill's record and the predecessor's record
        var record = reeBillGrid.getSelectionModel().getSelected();
        if (record != null) {
            var prevRecord = reeBillStore.queryBy(function(record, id) {
                return record.data.sequence == sequence - 1;
            }).first();
            if (prevRecord == undefined)
                prevRecord = null;

            var isLastSequence = reeBillStore.queryBy(function(record, id) {
                    return record.data.sequence == sequence + 1; }).first() ==
                    undefined;

            // the following rule determined when the "Delete selected reebill"
            // button would be enabled/disabled to enforce the rule that
            // corrections must always occur in a contiguous block ending at
            // the latest bill. this was removed in
            // https://www.pivotaltracker.com/story/show/54786706
            //deleteButton.setDisabled(!(isLastSequence && record.data.issued == 0 ||
                                        //(record.data.issued == false && record.data.max_version > 0 &&
                                         //(prevRecord == null || prevRecord.data.issued == true))));
            // delete button requires selected unissued correction whose predecessor
            // is issued, or an unissued reebill whose sequence is the last one
            deleteButton.setDisabled(record.data.issued == true);

            ubRegisterGrid.setEditable(sequence != null  && record.data.issued == false);
            // new version button requires selected issued reebill
            versionButton.setDisabled(sequence == null || record.data.issued == false);
        }

        selected_account = account;
        selected_sequence = sequence;

        // update the journal form panel so entries get submitted to currently selected account
        journalFormPanel.getForm().findField("account").setValue(account)
        journalFormPanel.getForm().findField("sequence").setValue(sequence)
        
        /* the rest of this applies only for a valid sequence */
        if (sequence == null) {
            updateStatusbar(selected_account, null, null);
            deleteButton.setDisabled(true);
            accountInfoFormPanel.setDisabled(true);
            reebillChargesPanel.setDisabled(true);
            Ext.getCmp('service_for_charges').getStore().removeAll();
            Ext.getCmp('service_for_charges').clearValue();
            Ext.getCmp('service_for_charges').setDisabled(true);
            return;
        }
        //Enable the reebill charges panel when a reebill is selected
        reebillChargesPanel.setDisabled(false);
        // enable or disable the reebill delete button depending on whether the
        // selected reebill is issued: only un-issued bills should be
        // deletable.
        // apparently there is no way to get the selected index of a combobox;
        // you have to get the value of the selection and then search for it in
        // the data store. better hope the values are unique.
        // http://stackoverflow.com/questions/6014593/how-do-i-get-the-selected-index-of-an-extjs-combobox
        // TODO: enable/disable delete button
        // TODO: 25419697
        //var sequenceRecordIndex = sequencesStore.find('sequence', sequence);
        //var sequenceRecord = sequencesStore.getAt(sequenceRecordIndex);
        //deleteButton.setDisabled(sequenceRecord.get('committed'))
        
        // TODO:23046181 abort connections in progress
        services = record.data.services;
        for (var i = 0;i < services.length;i++) {
            services[i] = [services[i]];
        }
        Ext.getCmp('service_for_charges').getStore().loadData(services);
        if (services.length > 0) {
            Ext.getCmp('service_for_charges').setValue(services[0]);
            Ext.getCmp('service_for_charges').setDisabled(false);
        } else {
            Ext.getCmp('service_for_charges').clearValue();
            Ext.getCmp('service_for_charges').setDisabled(true);
        }
            
        // image rendering resolution
        var menu = document.getElementById('reebillresolutionmenu');
        if (menu) {
            resolution = menu.value;
        } else {
            resolution = DEFAULT_RESOLUTION;
        }

        // while waiting for the next ajax request to finish, show a loading message
        // in the utilbill image box
        Ext.DomHelper.overwrite('reebillimagebox', {tag: 'div', html:LOADING_MESSAGE, id: 'reebillimage'}, true);
        
        // ajax call to generate image, get the name of it, and display it in a
        // new window
        // abort previous transaction
        reeBillImageDataConn.request({
            disablecaching: true,
            params: {account: selected_account, sequence: selected_sequence, resolution: resolution},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    var imageUrl = '';
                    if (jsonData.success == true) {
                        imageUrl = 'http://' + location.host + '/utilitybillimages/' + jsonData.imageName;
                    }
                    // handle failure if needed
                    Ext.DomHelper.overwrite('reebillimagebox', getImageBoxHTML(imageUrl, 'Reebill', 'reebill', NO_REEBILL_SELECTED_MESSAGE), true);

                } catch (err) {
                    Ext.MessageBox.alert('error', err);
                }
            },
            // this is called when the server returns 500 as well as when there's no response
            failure: function() { 
                Ext.MessageBox.alert('ajax failure loading bill image'); 

                // replace reebill image with a missing graphic
                Ext.DomHelper.overwrite('reebillimagebox', {tag: 'div',
                    html: NO_REEBILL_FOUND_MESSAGE, id: 'reebillimage'}, true);
            },
        });


        // Now that a ReeBill has been loaded, enable the tabs that act on a ReeBill
        // These enabled tabs will then display widgets that will pull data based on
        // the global account and sequence selection
        journalPanel.setDisabled(false);
        mailPanel.setDisabled(false);
        accountInfoFormPanel.setDisabled(false);

        /* TODO re-enable service suspension checkboxes
         * https://www.pivotaltracker.com/story/show/29557205
        // create checkboxes in Sequential Account Information form for
        // suspending services of the selected reebill
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/get_reebill_services?',
            params: { account: selected_account, sequence: selected_sequence },
            success: function(result, request) {
                var jsonData = Ext.util.JSON.decode(result.responseText);
                var services = jsonData.services;
                var suspended_services = jsonData.suspended_services;

                // create a checkbox for each service, checked iff that service
                // is in the bill's suspended_services (there's no handler
                // because checkbox values are automatically submitted with
                // "Sequential Account Information" form data)
                var checkboxes = [];
                for (i = 0; i < services.length; i++) {
                    checkboxes.push({
                        'boxLabel': services[i],
                        'name': services[i] + '_suspended',
                        'checked': suspended_services.indexOf(services[i].toLowerCase()) != -1,
                    });
                }
                console.log(selected_account + ', ' + selected_sequence + ' checkboxes: '+checkboxes);

                // replace the existing checkbox group in accountInfoFormPanel (if present) with a new one
                accountInfoFormPanel.remove('suspended-services');
                var suspendedServiceCheckboxGroup = new Ext.form.CheckboxGroup({
                    id: 'suspended-services',
                    itemCls: 'x-check-group-alt',
                    fieldLabel: 'Suspended Services',
                    columns: 1,
                    items: checkboxes,
                });
                accountInfoFormPanel.insert(accountInfoFormPanel.items.getCount(), suspendedServiceCheckboxGroup);
                // FIXME: accountInfoFormPanel sometimes does not show the
                // checkbox group even though it and its checkboxes have been
                // correctly generated. clicking the accordion bar again to
                // re-show the panel makes it appear.
                // the following did not help:
                //accountInfoFormPanel.render();
                //accountInfoFormPanel.update();
            },
            failure: function() {
                 Ext.MessageBox.alert('Ajax failure', 'get_reebill_services request failed');
            },
        });
        */

        // finally, update the status bar with current selection
        updateStatusbar(selected_account, selected_sequence, 0);
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


/**
* Used by Ajax calls to block the UI
* by setting global Ajax listeners for the duration
* of the call.
* Since there is only one block to the UI and possibly
* more than one Ajax call, we keep a counter.
var blockUICounter = 0;

function registerAjaxEvents()
{
    Ext.Ajax.addListener('beforerequest', this.showSpinnerBeforeRequest, this);
    Ext.Ajax.addListener('requestcomplete', this.hideSpinnerRequestComplete, this);
    Ext.Ajax.addListener('requestexception', this.hideSpinnerRequestException, this);
    Ext.Ajax.addListener('requestaborted', this.hideSpinnerRequestAborted, this);
}

function unregisterAjaxEvents()
{
    Ext.Ajax.removeListener('beforerequest', this.showSpinner, this);
    Ext.Ajax.removeListener('requestcomplete', this.hideSpinner, this);
    Ext.Ajax.removeListener('requestexception', this.hideSpinnerException, this);
    Ext.Ajax.removeListener('requestaborted', this.hideSpinnerRequestAborted, this);
}

function showSpinnerBeforeRequest(conn, options)
{
    //console.log("showSpinnerBeforeRequest " + blockUICounter)
    blockUICounter++;
    Ext.Msg.show({title: "Please Wait...", closable: false});
}

function hideSpinnerRequestComplete(conn, options)
{
    blockUICounter--;
    //console.log("hideSpinnerRequestComplete " + blockUICounter)
    if (!blockUICounter) {
        Ext.Msg.hide();
    }
}

function hideSpinnerRequestException(conn, response, options)
{
    blockUICounter--;
    //console.log("hideSpinnerRequestException " + blockUICounter)
    if (!blockUICounter) {
        Ext.Msg.hide();
    }
}

function hideSpinnerRequestAborted(conn, response, options)
{
    blockUICounter--;
    //console.log("hideSpinnerRequestAborted " + blockUICounter)
    if (!blockUICounter) {
        Ext.Msg.hide();
    }
}
*/


var NO_UTILBILL_SELECTED_MESSAGE = '<div style="display: block; margin-left: auto; margin-right: auto;"><table style="height: 100%; width: 100%;"><tr><td style="text-align: center;"><img src="select_utilbill.png"/></td></tr></table></div>';
var NO_UTILBILL_FOUND_MESSAGE = '<div style="display: block; margin-left: auto; margin-right: auto;"><table style="height: 100%; width: 100%;"><tr><td style="text-align: center;"><img src="select_utilbill_notfound.png"/></td></tr></table></div>';
var NO_REEBILL_SELECTED_MESSAGE = '<div style="display: block; margin-left: auto; margin-right: auto;"><table style="height: 100%; width: 100%;"><tr><td style="text-align: center;"><img src="select_reebill.png"/></td></tr></table></div>';
var NO_REEBILL_FOUND_MESSAGE = '<div style="display: block; margin-left: auto; margin-right: auto;"><table style="height:100%; width: 100%;"><tr><td style="text-align: center;"><img src="select_reebill_notfound.png"/></td></tr></table></div>';
var LOADING_MESSAGE = '<div style="display: block; margin-left: auto, margin-right: auto;"><table style="height: 100%; width: 100%;"><tr><td style="text-align: center;"><img src="rotologo_white.gif"/></td></tr></table></div>';

// TODO: 17613609  Need to show bill image, error not found image, error does not exist image
function getImageBoxHTML(url, label, idPrefix, errorHTML) {
    if (url) {
        // TODO default menu selection
        return {tag: 'img', src: url, width: '100%', id: idPrefix + 'image'}
    } else {
        return {tag: 'div', id: idPrefix + 'imagebox', children: [{tag: 'div', html: errorHTML,
            id: 'utilbillimage'}] };
    }
}

function loadDashboard()
{
    // pass configuration information to containing webpage
    // 'UNSPECIFIED' is expanded to a version string by deployment script
    var SKYLINE_VERSIONINFO="UNSPECIFIED"
    var SKYLINE_DEPLOYENV="UNSPECIFIED"
    versionInfo = Ext.get('SKYLINE_VERSIONINFO');
    versionInfo.update(SKYLINE_VERSIONINFO);
    deployEnv = Ext.get('SKYLINE_DEPLOYENV');
    deployEnv.update(SKYLINE_DEPLOYENV);

    title = Ext.get('pagetitle');
    title.update("Skyline ReeBill - " + SKYLINE_DEPLOYENV)

    // show username & logout link in the footer
    var logoutLink = '<a href="http://' + location.host + '/reebill/logout">log out</a>';

    var usernameDataConn = new Ext.data.Connection({
        url: 'http://' + location.host + '/reebill/getUsername',
    });
    usernameDataConn.autoAbort = true;
    usernameDataConn.disableCaching = true;

    usernameDataConn.request({
        success: function(result, request) {
            // check success status
            var jsonData = Ext.util.JSON.decode(result.responseText);
            // handle failure if needed
            var username = jsonData['username'];
            Ext.DomHelper.overwrite('LOGIN_INFO',
                "You're logged in as <b>" + username + "</b>; " + logoutLink)
        },
        failure: function() {
             Ext.MessageBox.alert('Ajax failure', 'http://' + location.host + '/getUsername');
        },
    });
}
