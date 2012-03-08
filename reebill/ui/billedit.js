var DEFAULT_RESOLUTION = 100; 

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

function renderWidgets()
{
    //registerAjaxEvents();
    // global ajax timeout

    // global declaration of account and sequence variable
    // these variables are updated by various UI's and represent
    // the current Reebill Account-Sequence being acted on
    var selected_account = null;
    var selected_sequence = null;

    // handle global success:false responses
    Ext.util.Observable.observeClass(Ext.data.Connection); 
    Ext.data.Connection.on('requestcomplete', function(dataconn, response) { 
        try {
            var jsonData = Ext.util.JSON.decode(response.responseText);
            // handle the various failure modes
            if (jsonData.success == false) {
                if (jsonData.errors.reason == "No Session") {
                    console.log("Not logged in, redirecting");
                    Ext.MessageBox.alert("Authentication", "Not logged in, or session expiration", function(){ document.location = "../"});
                } else {
                    // turn on to log application failures
                    //console.log(response.responseText);
                }
                
            }

        } catch (e) {
            console.log("Unexpected failure while processing requestcomplete");
            console.log(response);
            // TODO: evaluate response to see if the object is well formed
            Ext.MessageBox.alert("Unexpected failure while processing requestcomplete: " + response.responseText);
        }
    });

    // pass configuration information to containing webpage
    var SKYLINE_VERSIONINFO="UNSPECIFIED"
    var SKYLINE_DEPLOYENV="UNSPECIFIED"
    versionInfo = Ext.get('SKYLINE_VERSIONINFO');
    versionInfo.update(SKYLINE_VERSIONINFO);
    deployEnv = Ext.get('SKYLINE_DEPLOYENV');
    deployEnv.update(SKYLINE_DEPLOYENV);

    // show username & logout link in the footer
    var logoutLink = '<a href="http://' + location.host + '/reebill/logout">log out</a>';
    //TODO: 25593817
    Ext.Ajax.request({
        url: 'http://' + location.host + '/reebill/getUsername',
        success: function(result, request) {
            // check success status
            var jsonData = Ext.util.JSON.decode(result.responseText);
            var username = jsonData['username'];
            Ext.DomHelper.overwrite('LOGIN_INFO',
                "You're logged in as <b>" + username + "</b>; " + logoutLink)
            // handle failure if needed
        },
        failure: function() {
             Ext.MessageBox.alert('Ajax failure', 'http://' + location.host + '/getUsername');
        },
        disableCaching: true,
    });

    title = Ext.get('pagetitle');
    title.update("Skyline ReeBill - " + SKYLINE_DEPLOYENV)

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
            //allowBlank: false,
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

    var utilbillReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'id',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'name', mapping: 'name'},
            {name: 'account', mapping: 'account'},
            {name: 'period_start', mapping: 'period_start'},
            {name: 'period_end', mapping: 'period_end'},
            {name: 'sequence', mapping: 'sequence'},
            {name: 'state', mapping: 'state'},
        ]
    });

    var utilbillWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    var utilbillStoreDataConn = new Ext.data.Connection({
        method: 'GET',
        prettyUrls: false,
        url: 'http://'+location.host+'/reebill/utilbill_grid',
        disableCaching: true,
    });
    utilbillStoreDataConn.autoAbort = true;

    var utilbillStoreProxy = new Ext.data.HttpProxy(utilbillStoreDataConn);

    var utilbillGridStore = new Ext.data.JsonStore({
        proxy: utilbillStoreProxy,
        autoSave: true,
        reader: utilbillReader,
        writer: utilbillWriter,
        autoSave: true,
        baseParams: { start:0, limit: 25, account: null},
        data: initialutilbill,
        root: 'rows',
        totalProperty: 'results',
        // defaults to id? probably should explicity state it until we are ext experts
        //idProperty: 'sequence',
        fields: [
        {name: 'name'},
        {name: 'account'},
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
        {name: 'sequence'},
        {name: 'state'},
        {name: 'editable'},
        ],
    });

    utilbillGridStore.on('load', function (store, records, options) {
        // the grid is disabled by the panel that contains it  
        // prior to loading, and must be enabled when loading is complete
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

        if (options.params.account && options.params.account != selected_account) {
            // account changed, reset the paging 
            options.params.start = 0;
            options.params.limit = 25;
        }

        options.params.account = selected_account;

        // set the current selection into the store's baseParams
        // so that the store can decide to load itself if it wants
        store.baseParams.account = selected_account;
    });

    var utilbillColModel = new Ext.grid.ColumnModel(
    {
        columns:[{
                id: 'name',
                header: 'Name',
                dataIndex: 'name',
                width:300,
            },
            new Ext.grid.DateColumn({
                header: 'Start Date',
                dataIndex: 'period_start',
                dateFormat: 'Y-m-d',
                editable: true,
                editor: new Ext.form.DateField({allowBlank: false, format: 'Y-m-d'})
            }),
            new Ext.grid.DateColumn({
                header: 'End Date',
                dataIndex: 'period_end',
                dateFormat: 'Y-m-d',
                editable: true,
                editor: new Ext.form.DateField({allowBlank: false, format: 'Y-m-d'})
            }),
            {
                id: 'sequence',
                header: 'Sequence',
                dataIndex: 'sequence',
            },
            {
                id: 'state',
                header: 'State',
                dataIndex: 'state',
            },
        ],
    });


    // put this by the other dataconnection instantiations
    var utilbillImageDataConn = new Ext.data.Connection({
        url: 'http://' + location.host + '/reebill/getUtilBillImage',
        disableCaching: true,
    });
    utilbillImageDataConn.autoAbort = true;

    // in the mail tab
    var utilbillGrid = new Ext.grid.EditorGridPanel({
        flex: 1,
        bbar: new Ext.PagingToolbar({
            // TODO: constant
            pageSize: 25,
            store: utilbillGridStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No Utility Bills to display",
        }),
        colModel: utilbillColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: false}),
        store: utilbillGridStore,
        enableColumnMove: false,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        title: 'Utility Bills',
        clicksToEdit: 2,
        selModel: new Ext.grid.RowSelectionModel({
            singleSelect: true,
            listeners: {
                rowselect: function (selModel, index, record) {

                    // a row was selected in the UI, update subordinate ReeBill Data
                    if (record.data.sequence != null) {
                        loadReeBillUIForSequence(record.data.account, record.data.sequence);
                    }
                    // convert the parsed date into a string in the format expected by the back end
                    var formatted_begin_date_string = record.data.period_start.format('Y-m-d');
                    var formatted_end_date_string = record.data.period_end.format('Y-m-d');


                    // image rendering resolution
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
                }
            }
        }),
    });

    utilbillGrid.getSelectionModel().on('selectionchange', function(sm){
        //utilbillGrid.getTopToolbar().findById('utilbillInsertBtn').setDisabled(sm.getCount() <1);
    });
  

    // disallow rowediting of utility bills that are associated to reebills
    utilbillGrid.on('beforeedit', function(e) {
        if (!e.record.data.editable) {
            Ext.Msg.alert("Utility bill date ranges cannot be edited once associated to a ReeBill.");
            return false;
        }

    });

    //
    // Instantiate the Utility Bill panel
    //
    var utilityBillPanel = new Ext.Panel({
        id: 'utilityBillTab',
        title: 'Utility Bill',
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

        // because this tab is being displayed, demand the grids that it contain 
        // be populated
        utilbillGrid.setDisabled(true);

        // override options - none of this worked, still need to research API
        /*lastOptions = {params:{}};
        if (utilbillGridStore.lastOptions) {
            Ext.apply(lastOptions.params, {
                account: selected_account,
                start: lastOptions.params.start,
                limit: lastOptions.params.limit,
            });
            utilbillGridStore.reload(lastOptions);
        }*/

        /*utilbillGridStore.reload({params: {
            account: selected_account,
            //service: Ext.getCmp('service_for_charges').getValue(),
            start: 0,
            limit: 25
        }});*/

        // demand that the store load itself
        // we do not configure it here, it configures itself
        utilbillGridStore.reload();

    });

          
    ////////////////////////////////////////////////////////////////////////////
    // ReeBill Tab
    //

    // Select ReeBill

    var sequencesStore = new Ext.data.JsonStore({
        // store configs
        autoDestroy: true,
        autoLoad:false,
        url: 'http://'+location.host+'/reebill/listSequences',
        storeId: 'sequencesStore',
        root: 'rows',
        idProperty: 'sequence',
        fields: ['sequence', 'issued'],
    });

    sequencesStore.on('load', function() {
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
                {text: 'Bind Interval Meter Data', handler: bindREEOperation},
                {text: 'Compute Bill', handler: bindRSOperation},
                {text: 'Attach Utility Bills to Reebill', handler: attachOperation},
                {text: 'Render', handler: renderOperation},
            ]
        })
    });


    // TODO: 25795091 datastore data is being deleted wrong
    var deleteButton = new Ext.Button({
        text: 'Delete selected reebill',
        //disabled: true, // TODO should be disabled when there's no reebill selected or the currently-selected bill is not deletable
        handler: function() {
            // TODO: 25593817
            var deleteBillRequest = Ext.Ajax.request({
                url: 'http://' + location.host + '/reebill/delete_reebill',
                params: {
                    account: selected_account,
                    sequence: selected_sequence
                },
                success: function(result, request) {
                    var jsonData = null;
                    try {
                        jsonData = Ext.util.JSON.decode(result.responseText);
                        var imageUrl = '';
                        if (jsonData.success == true) {
                            // TODO reload a lot of stuff?
                        }
                        // handle failure if needed
                    } catch (err) {
                        Ext.MessageBox.alert('delete reebill ERROR', err);
                    }
                },
                // this is called when the server returns 500 as well as when there's no response
                failure: function() { Ext.MessageBox.alert('Ajax failure', 'delete reebill'); },
                disableCaching: true,
            });
        }
    })

    var initialReebill =  {
        rows: [
        ]
    };

    var reeBillReader = new Ext.data.JsonReader({
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

    var reeBillWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    var reeBillStoreDataConn = new Ext.data.Connection({
        method: 'GET',
        prettyUrls: false,
        url: 'http://'+location.host+'/reebill/reebill',
        disableCaching: true,
    });
    reeBillStoreDataConn.autoAbort = true;
    reeBillStoreDataConn.on('beforerequest', function(conn, options) {
    });

    var reeBillStoreProxy = new Ext.data.HttpProxy(reeBillStoreDataConn);

    var reeBillStore = new Ext.data.JsonStore({
        proxy: reeBillStoreProxy,
        autoSave: false,
        reader: reeBillReader,
        writer: reeBillWriter,
        autoSave: true,
        autoLoad: {params:{start: 0, limit: 25}},
        // won't be updated when combos change, so do this in event
        // perhaps also can be put in the options param for the ajax request
        //baseParams: { account:"none"},
        paramNames: {start: 'start', limit: 'limit'},
        data: initialReebill,
        root: 'rows',
        totalProperty: 'results',
        //idProperty: 'sequence',
        fields: [
            {name: 'sequence'},
        ],
    });

    reeBillStore.on('beforesave', function() {
    });

    reeBillStore.on('update', function(){
    });

    // this event is never fired because we manually save the aCharges
    reeBillStore.on('save', function () {
    });

    reeBillStore.on('beforeload', function () {
        reeBillStore.setBaseParam("start", 0);
        reeBillStore.setBaseParam("limit", 25);
        reeBillStore.setBaseParam("account", selected_account);
        reeBillStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
    });

    // fired when the datastore has completed loading
    reeBillStore.on('load', function (store, records, options) {
        // the grid is disabled by the panel that contains it  
        // prior to loading, and must be enabled when loading is complete
        // the datastore enables when it is done loading
        reeBillGrid.setDisabled(false);
    });

    var reeBillColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
                header: 'Sequence',
                sortable: true,
                dataIndex: 'sequence',
                editor: new Ext.form.TextField({allowBlank: true})
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
                        store: ['Gas', 'Electric'],
                        value: 'Gas',
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
            { xtype: 'tbseparator' },
            {
                xtype: 'panel',
                items: [
                    deleteButton,
                ],
            },
        ]
    });

    var reeBillGrid = new Ext.grid.EditorGridPanel({
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
                rowselect: function (selModel, index, record) {
                    // TODO: have other widgets pull when this selection is made
                    loadReeBillUIForSequence(selected_account, record.data.sequence);
                }
            }
        }),
        store: reeBillStore,
        enableColumnMove: false,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        title: 'ReeBills',
        clicksToEdit: 2
    });

    reeBillGrid.getSelectionModel().on('selectionchange', function(sm){
    });


    /////////////////////////////////////////////////////
    // Functions for ReeBill Structure Editor event

    // uses ajax to edit reebill structure
    // three operations use this: insert a new node, delete a node and edit a node
    // for the edit a node operation, the newly edited value is also passed in
    function editReeBillStructureNode(action, new_text)
    {
        var cmp = Ext.getCmp('reeBillEditorTree');
        var selNode = cmp.getSelectionModel().getSelectedNode();
        if (selNode == null || selNode.parentNode == null) {
            Ext.Msg.alert("No node selected.")
            return; 
        }

        // so that we can track the parent in case selNode is to be removed 
        var parentNode = selNode.parentNode;

        // determine if we have enough information to act on this node
        if (!("service" in selNode.attributes && "account" in selNode.attributes 
            && "sequence" in selNode.attributes && "node_type" in selNode.attributes
            && "node_key" in selNode.attributes && "text" in selNode.attributes)) {

            Ext.Msg.alert("Selected node uneditable.")
            return;
        }

        // TODO: 22792659 disabled widgets have to be reenabled if there is an exception 
        cmp.disable();

        // TODO:25593817 this has to be converted to a data.connection
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/' + action,
            params: { 
                // note, we dont pass in selNode.id. This is because the unique id's
                // are only used by the client side gui code.
                'service': selNode.attributes.service,
                'account': selNode.attributes.account,
                'sequence': selNode.attributes.sequence,
                'node_type': selNode.attributes.node_type,
                'node_key': selNode.attributes.node_key,
                // if a new value was passed in, update to this new value
                'text': new_text == null ? selNode.attributes.text : new_text,
            },
            disableCaching: true,
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false) {
                        // handle failure here if necessary
                    } else {
                        if (action == 'insert_reebill_sibling_node') {
                            var newNode = jsonData.node
                            // TreePanel will fire insert event
                            parentNode.appendChild(newNode);
                        } else if (action == 'delete_reebill_node') {
                            selNode.remove(true);
                        } else if (action == 'update_reebill_node') {
                            var updatedNode = jsonData.node
                            parentNode.replaceChild(updatedNode,selNode);  
                        }
                    }
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err + ' Remote: ' + result.responseText);
                }

                cmp.enable();
                // TODO:  22827425 expand after edit - seems an exception is thrown in ext here
                //parentNode.expandChildNodes();
            },
            failure: function () {
                Ext.Msg.alert("Edit ReeBill Request Failed.");
                cmp.enable();
            }
        });
    }

    function configureReeBillEditor(account, sequence)
    {

        var reeBillTab = tabPanel.getItem('reeBillTab');

        var reeBillEditorTree = Ext.getCmp('reeBillEditorTree');

        // lazily create it if it does not exist
        if (reeBillEditorTree === undefined) {

            var reeBillEditorTreeToolbar = new Ext.Toolbar({
                
                items: [
                    {
                        xtype: 'button',

                        // ref places a name for this component into the grid so it may be referenced as [name]Grid.insertBtn...
                        id: 'nodeInsertBtn',
                        iconCls: 'icon-add',
                        text: 'Insert',
                        disabled: false,
                        handler: function() {
                            editReeBillStructureNode('insert_reebill_sibling_node', null);
                        },
                    },{
                        xtype: 'tbseparator'
                    },{
                        xtype: 'button',
                        // ref places a name for this component into the grid so it may be referenced as [name]Grid.removeBtn...
                        id: 'nodeRemoveBtn',
                        iconCls: 'icon-delete',
                        text: 'Remove',
                        disabled: false,
                        handler: function() {
                            editReeBillStructureNode('delete_reebill_node', null);
                        },
                    }
                ]
            });

            onTreeNodeDblClick = function(n) {
                reeBillEditorTreeEditor.editNode = n;
                reeBillEditorTreeEditor.startEdit(n.ui.textNode);
            }

            var reeBillEditorTreeLoader = new Ext.tree.TreeLoader({
                //dataUrl:'http://'+location.host+'/reebill/reebill_structure_editor',
                dataUrl:'http://'+location.host+'/reebill/reebill_structure',
                // defaults to true
                clearOnLoad: true,
            });

            reeBillEditorTree = new Ext.tree.TreePanel({
                id: 'reeBillEditorTree',
                title: 'ReeBill Structure Editor',
                frame: true,
                animate: true, 
                autoScroll: true,
                loader: reeBillEditorTreeLoader,
                enableDD: false,
                containerScroll: true,
                autoWidth: true,
                dropConfig: {appendOnly: true},
                tbar: reeBillEditorTreeToolbar,
                listeners: {
                    dblclick: onTreeNodeDblClick,
                }
            });

            
            // add a tree sorter in folder mode
            new Ext.tree.TreeSorter(reeBillEditorTree, {folderSort:true});
            
            // set the root node
            var reeBillEditorTreeRoot = new Ext.tree.AsyncTreeNode({
                id:'reeBillEditorTreeRoot',
                text: 'ReeBill', 
                draggable:false, // disable root node dragging
            });

            reeBillEditorTree.setRootNode(reeBillEditorTreeRoot);

            //this causes the treeloader to fire a request
            //since we want to lazily create things, don't fire a load request
            //reeBillEditorTreeRoot.expand(false, /*no anim*/ false);

            onTreeEditComplete = function(treeEditor, n, o) {
                //o - oldValue
                //n - newValue
                editReeBillStructureNode('update_reebill_node', n)
            }

            var reeBillEditorTreeEditor = new Ext.tree.TreeEditor(reeBillEditorTree, {}, {
                cancelOnEsc: true,
                completeOnEnter: true,
                selectOnFocus: true,
                allowBlank: false,
                listeners: {
                    complete: onTreeEditComplete
                }
            });

            reeBillTab.add(reeBillEditorTree);
        }

        var loader = reeBillEditorTree.getLoader();

        // cancel ajax if it is running
        if (loader.isLoading()) {
            console.log("Aborting structure editor ajax");
            loader.abort();
        }

        // widgets have been lazily instantiated, now go load them.
        loader.baseParams.account = selected_account;
        loader.baseParams.sequence = selected_sequence;
        loader.load(reeBillEditorTree.root);

    }


    var addressFormPanel = new Ext.FormPanel(
    {
        id: 'billingAddressFormPanel',
        title: 'Billing Address',
        header: true,
        url: 'http://'+location.host+'/reebill/set_addresses',
        border: false,
        frame: true,
        flex: 1,
        bodyStyle:'padding:10px 10px 0px 10px',
        defaults: {
            anchor: '-20',
            allowBlank: false,
        },
        items:[], 
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
    })

    function configureAddressForm(account, sequence, addresses)
    {
        var addressFormPanel = Ext.getCmp('billingAddressFormPanel');

        addressFormPanel.removeAll(true);

        if (addresses) {
            addressFormPanel.add(
            {
                xtype: 'fieldset',
                title: 'Billing Address',
                collapsible: false,
                defaults: {
                    anchor: '-20',
                },
                items: [
                    {
                        xtype: 'textfield',
                        fieldLabel: 'Addressee',
                        name: 'ba_addressee',
                        value: addresses['billing_address']['ba_addressee'],
                    },{
                        xtype: 'textfield',
                        fieldLabel: 'Street',
                        name: 'ba_street1',
                        value: addresses['billing_address']['ba_street1'],
                    },{
                        xtype: 'textfield',
                        fieldLabel: 'City',
                        name: 'ba_city',
                        value: addresses['billing_address']['ba_city'],
                    },{
                        xtype: 'textfield',
                        fieldLabel: 'State',
                        name: 'ba_state',
                        value: addresses['billing_address']['ba_state'],
                    },{
                        xtype: 'textfield',
                        fieldLabel: 'Postal Code',
                        name: 'ba_postal_code',
                        value: addresses['billing_address']['ba_postal_code'],
                    },
                ]
            },{
                xtype: 'fieldset',
                title: 'Service Address',
                collapsible: false,
                defaults: {
                    anchor: '-20',
                },
                items: [
                    {
                        xtype: 'textfield',
                        fieldLabel: 'Addressee',
                        name: 'sa_addressee',
                        value: addresses['service_address']['sa_addressee'],
                    },{
                        xtype: 'textfield',
                        fieldLabel: 'Street',
                        name: 'sa_street1',
                        value: addresses['service_address']['sa_street1'],
                    },{
                        xtype: 'textfield',
                        fieldLabel: 'City',
                        name: 'sa_city',
                        value: addresses['service_address']['sa_city'],
                    },{
                        xtype: 'textfield',
                        fieldLabel: 'State',
                        name: 'sa_state',
                        value: addresses['service_address']['sa_state'],
                    },{
                        xtype: 'textfield',
                        fieldLabel: 'Postal Code',
                        name: 'sa_postal_code',
                        value: addresses['service_address']['sa_postal_code'],
                    },
                ]
            });

            addressFormPanel.doLayout();
        }

        // add base parms for form post
        addressFormPanel.getForm().baseParams = {account: account, sequence: sequence}
    }

    // since this panel depends on data from the reeBillGrid, hook into
    // its activate so that the user has the chance to pick a selected_sequence
    addressFormPanel.on('activate', function (panel) {
        // because this tab is being displayed, demand the form that it contain 
        // be populated
        // disable it during load, the datastore re-enables when loaded.
        addressFormPanel.setDisabled(true);

        // get the address information for this reebill 
        // fire this request when the widget is displayed
        addressesDataConn.request({
            params: {account: selected_account, sequence: selected_sequence},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false) {
                        Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                    } else {
                        configureAddressForm(selected_account, selected_sequence, jsonData);
                    } 
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    addressFormPanel.setDisabled(false);
                }
            },
            failure: function(result, request) {
                try {
                    Ext.MessageBox.alert('Server Error', result.responseText);
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    addressFormPanel.setDisabled(false);
                }
            },
        });
    });


    // finally, set up the tabe that will contain the above widgets
    var reeBillPanel = new Ext.Panel({
        id: 'reeBillTab',
        title: 'ReeBill',
        disabled: reeBillPanelDisabled,
        layout: 'accordion',
        items: [reeBillGrid, addressFormPanel ],
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    reeBillPanel.on('activate', function (panel) {

        // because this tab is being displayed, demand the grids that it contain 
        // be populated
        reeBillGrid.setDisabled(true);
        reeBillStore.reload();

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
            Ext.Msg.alert('Error', o.errors.reason + " " + o.errors.details);
        } else {
            loadReeBillUIForSequence(selected_account, selected_sequence);
        }
    }

    function allOperations()
    {
        Ext.Msg.alert('Notice', "One of the operations on this menu must be selected");
    }

    var bindRSOperationConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/bindrs',
        disableCaching: true,
    });
    bindRSOperationConn.autoAbort = true;
    function bindRSOperation()
    {

        //Ext.Msg.show({title: "Please Wait while RS is bound", closable: false});
        tabPanel.setDisabled(true);

        bindRSOperationConn.request({
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
    function bindREEOperation()
    {
        Ext.Msg.show({title: "Please Wait while OLTP data is fetched", closable: false});

        bindREEOperationConn.request({
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
                    Ext.Msg.hide();
                }
            },
            failure: function(result, request) {
                try {
                    Ext.MessageBox.alert('Server Error', result.responseText);
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    Ext.Msg.hide();
                }
            },
        });
    }

    var rollOperationConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/roll',
        disableCaching: true,
    });
    rollOperationConn.autoAbort = true;
    function rollOperation()
    {
        //Ext.Msg.show({title: "Please Wait while OLTP data is fetched", closable: false});
        tabPanel.setDisabled(true);

        rollOperationConn.request({
            params: {account: selected_account, sequence: selected_sequence},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false) {
                        Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                    } else {
                        // a new sequence has been made, so load it for the currently selected account
                        //sequencesStore.load();
                        // TODO:  25419609 load latest sequence after roll
                    }
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    tabPanel.setDisabled(false);
                }
            },
            failure: function(result, request) {
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

    function renderOperation()
    {
        // TODO: 25593817
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/render',
            params: { 
                account: selected_account,
                sequence: selected_sequence
            },
            disableCaching: true,
            success: successResponse,
            failure: function () {
                alert("Render response fail");
            }
        });
    }

    function attachOperation() {
        /* Finalize association of utilbills with reebill. */
        // TODO: 25593817
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/attach_utilbills',
            params: {
                account: selected_account,
                sequence: selected_sequence,
                disableCaching: true,
                success: successResponse,
                failure: function() {
                    alert("Attach Utility Bills failed");
                }
            },
        });
    }

    function mailReebillOperation(sequences)
    {
        Ext.Msg.prompt('Recipient', 'Enter comma seperated email addresses:', function(btn, recipients){
            if (btn == 'ok')
            {
                // TODO: 25593817
                Ext.Ajax.request({
                    url: 'http://'+location.host+'/reebill/mail',
                    params: {
                        account: selected_account,
                        recipients: recipients,
                        sequences: sequences,
                    },
                    disableCaching: true,
                    success: function(response, options) {
                        var o = {};
                        try {
                            o = Ext.decode(response.responseText);}
                        catch(e) {
                            alert("Could not decode JSON data");
                        }
                        if(true !== o.success) {
                            Ext.Msg.alert('Error', o.errors.reason + o.errors.details);
                        } else {
                            Ext.Msg.alert('Success', "mail successfully sent");
                        }
                    },
                    failure: function () {
                        alert("mail response fail");
                    }
                });
            }
        });
    }

    ////////////////////////////////////////////////////////////////////////////
    //
    // Generic form save handler
    // 
    // TODO: 20496293 accept functions to callback on form post success
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
                    // TODO: 20496293 pass this in as a callback
                    utilbillGrid.getBottomToolbar().doRefresh();
                }
            })

        }else{
            Ext.MessageBox.alert('Errors', 'Please fix form errors noted.');
        }
    }

    //
    ////////////////////////////////////////////////////////////////////////////





    ////////////////////////////////////////////////////////////////////////////
    // Bill Periods tab
    //
    // dynamically create the period forms when a bill is loaded
    //

    function configureUBPeriodsForms(account, sequence, periods)
    {
        var ubPeriodsTab = tabPanel.getItem('ubPeriodsTab');

        ubPeriodsTab.removeAll(true);

        var ubPeriodsFormPanels = [];
        
        for (var service in periods) { 
            var ubPeriodsFormPanel = new Ext.FormPanel({
                id: service + 'UBPeriodsFormPanel',
                title: 'Service ' + service,
                header: true,
                url: 'http://'+location.host+'/reebill/setUBPeriod',
                border: false,
                frame: true,
                labelWidth: 125,
                bodyStyle:'padding:10px 10px 0px 10px',
                items:[], // added by configureUBPeriodsForm()
                buttons: [
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
                    fieldLabel: 'Begin',
                    name: 'begin',
                    value: periods[service].begin,
                    format: 'Y-m-d'
                }),
                new Ext.form.DateField({
                    fieldLabel: 'End',
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
        ubPeriodsTab.doLayout();
    }

    //
    // Instantiate the Utility Bill Periods panel
    //
    var ubBillPeriodsPanel = new Ext.Panel({
        id: 'ubPeriodsTab',
        title: 'Bill Periods',
        disabled: billPeriodsPanelDisabled,
        items: null // configureUBPeriodForm set this
    });

    ubBillPeriodsPanel.on('activate', function () {
        // because this tab is being displayed, demand the form that it contain 
        // be populated
        // disable it during load, the datastore re-enables when loaded.
        ubBillPeriodsPanel.setDisabled(true);

        // get utilbill period information from server
        // TODO: fire this request only when the form is displayed
        ubPeriodsDataConn.request({
            params: {account: selected_account, sequence: selected_sequence},
            success: function(result, request) {
                var jsonData = null;
                try {
                    jsonData = Ext.util.JSON.decode(result.responseText);
                    if (jsonData.success == false)
                    {
                        Ext.MessageBox.alert('Server Error', jsonData.errors.reason + " " + jsonData.errors.details);
                    } else {
                        configureUBPeriodsForms(selected_account, selected_sequence, jsonData);
                    } 
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    ubBillPeriodsPanel.setDisabled(false);
                }
            },
            failure: function() {
                try {
                    Ext.MessageBox.alert('Server Error', result.responseText);
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err);
                } finally {
                    ubBillPeriodsPanel.setDisabled(false);
                }
            },
        });

    });

    ////////////////////////////////////////////////////////////////////////////
    // Measured Usage Tab
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
                    title: 'Meter ' + meter.identifier,
                    header: true,
                    url: 'http://'+location.host+'/reebill/setMeter',
                    border: true,
                    frame: true,
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
                        value: meter.prior_read_date,
                        format: 'Y-m-d'
                    }),
                    new Ext.form.DateField({
                        fieldLabel: service + ' Present Read',
                        name: 'presentreaddate',
                        value: meter.present_read_date,
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
                            title: 'Meter ' + meter.identifier + ' Register ' + register.identifier,
                            header: true,
                            url: 'http://'+location.host+'/reebill/setActualRegister',
                            border: true,
                            frame: true,
                            labelWidth: 125,
                            //bodyStyle:'padding:10px 10px 0px 10px',
                            items:[], // added by configureUBMeasuredUsagesForm()
                            baseParams: null, // added by configureUBMeasuredUsagesForm()
                            autoDestroy: true,
                            //layout: 'form',
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
                                name: 'quantity',
                                value: register.quantity,
                            })
                        );

                        // add base parms for form post
                        registerFormPanel.getForm().baseParams = {account: account, sequence: sequence, service:service, meter_identifier: meter.identifier, register_identifier:register.identifier}

                        ubMeasuredUsagesFormPanels.push(registerFormPanel);
                    }

                })
            })
        }

        var intervalMeterFormPanel = new Ext.form.FormPanel({
            fileUpload: true,
            title: 'Upload Interval Meter CSV',
            url: 'http://'+location.host+'/reebill/upload_interval_meter_csv',
            frame:true,
            bodyStyle: 'padding: 10px 10px 0 10px;',
            defaults: {
                anchor: '95%',
                //allowBlank: false,
                msgTarget: 'side'
            },

            items: [
                //file_chooser - defined in FileUploadField.js
                {
                    xtype: 'fileuploadfield',
                    id: 'interval-meter-csv-field',
                    emptyText: 'Select a file to upload',
                    name: 'csv_file',
                    buttonText: 'Choose file...',
                    buttonCfg: { width:80 },
                    allowBlank: true
                    //disabled: true
                },
                //{
                    //xtype: 'textfield',
                    //id: 'account',
                    //value: selected_account
                //}
            ],

            buttons: [
                new Ext.Button({
                    text: 'Reset',
                    handler: function() {
                        this.findParentByType(Ext.form.FormPanel).getForm().reset();
                    }
                }),
                new Ext.Button({ text: 'Submit', handler: function () {
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
                                'sequence': selected_sequence
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
                 })
            ],
        });
        ubMeasuredUsagesFormPanels.push(intervalMeterFormPanel);

        ubMeasuredUsagesTab.add(ubMeasuredUsagesFormPanels);
        ubMeasuredUsagesTab.doLayout();
    }

    //
    // Instantiate the Utility Bill Measured Usages panel
    //
    var ubMeasuredUsagesPanel = new Ext.Panel({
        id: 'ubMeasuredUsagesTab',
        title: 'Measured Usage',
        disabled: usagePeriodsPanelDisabled,
        layout: 'vbox',
        layoutConfig : {
            pack : 'start',
            align : 'stretch',
        },
        items: null // configureUBMeasuredUsagesForm sets this
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    ubMeasuredUsagesPanel.on('activate', function (panel) {

        // because this tab is being displayed, demand the form that it contain 
        // be populated
        // disable it during load, the datastore re-enables when loaded.
        ubMeasuredUsagesPanel.setDisabled(true);

        // get the measured usage dates for each service
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
    });


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
        //idProperty: 'id',
        root: 'rows',

        // the fields config option will internally create an Ext.data.Record
        // constructor that provides mapping for reading the record data objects
        fields: [
            // map Record's field to json object's key of same name
            {name: 'chargegroup', mapping: 'chargegroup'},
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
        autoSave: false,
        reader: aChargesReader,
        writer: aChargesWriter,
        data: initialActualCharges,
        sortInfo:{field: 'chargegroup', direction: 'ASC'},
        groupField:'chargegroup'
    });

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    aChargesStore.on('update', function(){
        aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(false);
    });

    // this event is never fired because we manually save the aCharges
    aChargesStore.on('save', function () {
    });

    aChargesStore.on('beforeload', function () {
        //console.log('aChargesStore beforeload');
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
                hidden: true 
            }, 
            {
                header: 'RSI Binding',
                width: 75,
                sortable: true,
                dataIndex: 'rsi_binding',
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
        ]
    });

    var aChargesToolbar = new Ext.Toolbar({
        items: [
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
                    aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(false);
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
                    aChargesGrid.getTopToolbar().findById('aChargesSaveBtn').setDisabled(false);
                }
            },{
                xtype:'tbseparator'
            },{
                xtype: 'button',
                // places reference to this button in grid.  
                id: 'aChargesSaveBtn',
                iconCls: 'icon-save',
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

                    // disable the aChargesGrid so that the user cannot interact during the save
                    // the  associated data store's 'load' event re-enables it.
                    // we must do this manually, since our datastore will not give us a beforesave
                    // event
                    aChargesGrid.setDisabled(true);

                    // OK, a little nastiness follows: We cannot rely on the underlying Store to
                    // send records back to the server because it does so intelligently: Only
                    // dirty records go back.  Unfortunately, since there is no entity id for
                    // a record (yet), all records must be returned so that ultimately an
                    // XML grove can be produced with proper document order.
                    //aChargesStore.save(); is what we want to do

                    var jsonData = Ext.encode(Ext.pluck(aChargesStore.data.items, 'data'));

                    // TODO: 25593817
                    Ext.Ajax.request({
                        url: 'http://'+location.host+'/reebill/saveActualCharges',
                        params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence, rows: jsonData},
                        success: function() { 
                            // TODO: check success status in json package

                            // reload the store to clear dirty flags
                            // this causes the load event to fire and re-enable the aChargesGrid
                            aChargesStore.load({params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence}})
                        },
                        failure: function() { alert("ajax fail"); },
                    });
                }
            },{
                xtype:'tbseparator'
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
    


    ///////////////////////////////////////
    // support for the hypothetical charges

    // initial data loaded into the grid before a bill is loaded
    // populate with data if initial pre-loaded data is desired
    var initialHypotheticalCharges = {
        rows: [
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
    var hChargesWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    // This proxy is only used for reading charge item records, not writing.
    // This is due to the necessity to batch upload all records. See Grid Editor save handler.
    // We leave the proxy here for loading data as well as if and when records have entity 
    // id's and row level CRUD can occur.
    var hChargesStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/hypotheticalCharges',
        disableCaching: true,
    })
    hChargesStoreProxyConn.autoAbort = true;
    var hChargesStoreProxy = new Ext.data.HttpProxy(hChargesStoreProxyConn);

    var hChargesStore = new Ext.data.GroupingStore({
        proxy: hChargesStoreProxy,
        autoSave: false,
        reader: hChargesReader,
        writer: hChargesWriter,
        data: initialHypotheticalCharges,
        sortInfo:{field: 'chargegroup', direction: 'ASC'},
        groupField:'chargegroup'
    });

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    hChargesStore.on('update', function(){
        hChargesGrid.getTopToolbar().findById('hChargesSaveBtn').setDisabled(false);
    });

    // this event is never fired because we manually save the aCharges
    hChargesStore.on('save', function () {
    });

    hChargesStore.on('beforeload', function () {
        //console.log('hChargesStore beforeload');
    });

    // fired when the datastore has completed loading
    hChargesStore.on('load', function (store, records, options) {
        //console.log('hChargesStore load');
        // the grid is disabled by the panel that contains it  
        // prior to loading, and must be enabled when loading is complete
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
                hidden: true 
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

    var hChargesToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as hChargesGrid.insertBtn...
                id: 'hChargesInsertBtn',
                iconCls: 'icon-add',
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
                        quantity_units: 'kWh',
                        rate: 0,
                        rate_units: 'dollars',
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
                iconCls: 'icon-delete',
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

                    // disable the aChargesGrid so that the user cannot interact during the save
                    // the  associated data store's 'load' event re-enables it.
                    // we must do this manually, since our datastore will not give us a beforesave
                    // event
                    hChargesGrid.setDisabled(true);

                    // OK, a little nastiness follows: We cannot rely on the underlying Store to
                    // send records back to the server because it does so intelligently: Only
                    // dirty records go back.  Unfortunately, since there is no entity id for
                    // a record (yet), all records must be returned so that ultimately an
                    // XML grove can be produced with proper document order.
                    //hChargesStore.save(); is what we want to do

                    var jsonData = Ext.encode(Ext.pluck(hChargesStore.data.items, 'data'));

                    // TODO: 25593817
                    Ext.Ajax.request({
                        url: 'http://'+location.host+'/reebill/saveHypotheticalCharges',
                        params: {service: Ext.getCmp('service_for_charges').getValue(), account: account, sequence: sequence, rows: jsonData},
                        success: function() { 
                            // TODO: check success status in json package

                            // reload the store to clear dirty flags
                            // this causes the load event to fire and re-enable the hChargesGrid
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
  

    hChargesGrid.on('activate', function(panel) {
        //console.log("hChargesGrid Activated");
        //console.log(panel);
    });
    hChargesGrid.on('beforeshow', function(panel) {
        //console.log("hChargesGrid beforeshow");
        //console.log(panel);
    });
    hChargesGrid.on('show', function(panel) {
        //console.log("hChargesGrid show");
        //console.log(panel);
    });
    hChargesGrid.on('viewready', function(panel) {
        //console.log("hChargesGrid view ready");
    });
    hChargesGrid.on('beforeexpand', function (panel, animate) {
        //console.log("hChargesGrid beforeexpand ");
        //console.log(panel);
    });
    hChargesGrid.on('expand', function (panel) {
        //console.log("hChargesGrid expand ");
        //console.log(panel);
    });
    hChargesGrid.on('collapse', function (panel) {
        //console.log("hChargesGrid collapse ");
        //console.log(panel);
    });
    hChargesGrid.on('afterrender', function (panel) {
        //console.log("hChargesGrid afterrender ");
        //console.log(panel);
    });
    hChargesGrid.on('enable', function (panel) {
        //console.log("hChargesGrid enable ");
        //console.log(panel);
    });
    hChargesGrid.on('disable', function (panel) {
        //console.log("hChargesGrid disable ");
        //console.log(panel);
    });


    //
    // Instantiate the Charge Items panel
    //
    var chargeItemsPanel = new Ext.Panel({
        id: 'chargeItemsTab',
        title: 'Charge Items',
        disabled: chargeItemsPanelDisabled,
        xtype: 'panel',
        layout: 'accordion',
        items: [
            aChargesGrid,
            hChargesGrid,
        ]
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    chargeItemsPanel.on('activate', function (panel) {
        //console.log("chargeItemsPanel activated");
        //console.log(panel);

        // because this tab is being displayed, demand the grids that it contain 
        // be populated
        aChargesGrid.setDisabled(true);
        //aChargesStore.proxy.getConnection().autoAbort = true;
        aChargesStore.reload({params: {service: Ext.getCmp('service_for_charges').getValue(), account: selected_account, sequence: selected_sequence}});

        hChargesGrid.setDisabled(true);
        //hChargesStore.proxy.getConnection().autoAbort = true;
        hChargesStore.reload({params: {service: Ext.getCmp('service_for_charges').getValue(), account: selected_account, sequence: selected_sequence}});
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
        //idProperty: 'id',
        root: 'rows',

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
        disableCaching: true,
    });
    CPRSRSIStoreProxyConn.autoAbort = true;
    
    var CPRSRSIStoreProxy = new Ext.data.HttpProxy(CPRSRSIStoreProxyConn);

    var CPRSRSIStore = new Ext.data.JsonStore({
        proxy: CPRSRSIStoreProxy,
        autoSave: false,
        reader: CPRSRSIReader,
        writer: CPRSRSIWriter,
        // or, autosave must be used to save each action
        //autoSave: true,
        // won't be updated when combos change, so do this in event
        // perhaps also can be put in the options param for the ajax request
        baseParams: { account:selected_account, sequence: selected_sequence},
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

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    CPRSRSIStore.on('update', function(){
        //CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(false);
    });

    CPRSRSIStore.on('save', function (store, batch, data) {
    });

    CPRSRSIStore.on('beforeload', function () {
        CPRSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
        CPRSRSIStore.setBaseParam("account", selected_account);
        CPRSRSIStore.setBaseParam("sequence", selected_sequence);
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
        console.log('CPRSRSIStore update');
        CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(false);
    });

    CPRSRSIStore.on('beforesave', function() {
        CPRSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
        CPRSRSIStore.setBaseParam("account", selected_account);
        CPRSRSIStore.setBaseParam("sequence", selected_sequence);
    });

    var CPRSRSIColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            /*{
                header: 'UUID',
                sortable: true,
                dataIndex: 'uuid',
                editable: false,
                editor: new Ext.form.TextField({allowBlank: false})
            },*/{
                header: 'RSI Binding',
                sortable: true,
                dataIndex: 'rsi_binding',
                editable: true,
                editor: new Ext.form.TextField({allowBlank: false})
            },{
                header: 'Description',
                sortable: true,
                dataIndex: 'description',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Quantity',
                sortable: true,
                dataIndex: 'quantity',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'quantityunits',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Rate',
                sortable: true,
                dataIndex: 'rate',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'rateunits',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Round Rule',
                sortable: true,
                dataIndex: 'roundrule',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Total', 
                sortable: true, 
                dataIndex: 'total', 
                summaryType: 'sum',
                align: 'right',
                editor: new Ext.form.TextField({allowBlank: true})
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
                    CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(false);
                    console.log('enabling save 44444');
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
                    CPRSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
                    CPRSRSIStore.setBaseParam("account", selected_account);
                    CPRSRSIStore.setBaseParam("sequence", selected_sequence);

                    // TODO single row selection only, test allowing multirow selection
                    var s = CPRSRSIGrid.getSelectionModel().getSelections();
                    for(var i = 0, r; r = s[i]; i++)
                    {
                        CPRSRSIStore.remove(r);
                    }
                    CPRSRSIStore.save(); 
                    CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(true);
                    console.log('disabling save 3333');
                }
            },{
                xtype:'tbseparator'
            },{
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
                    console.log('disabling save 2222');
                    CPRSRSIGrid.getTopToolbar().findById('CPRSRSISaveBtn').setDisabled(true);

                    // stop grid editing so that widgets like comboboxes in rows don't stay focused
                    CPRSRSIGrid.stopEditing();

                    CPRSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
                    CPRSRSIStore.setBaseParam("account", selected_account);
                    CPRSRSIStore.setBaseParam("sequence", selected_sequence);

                    CPRSRSIStore.save(); 
                }
            }
        ]
    });

    var CPRSRSIGrid = new Ext.grid.EditorGridPanel({
        tbar: CPRSRSIToolbar,
        colModel: CPRSRSIColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: CPRSRSIStore,
        enableColumnMove: true,
        frame: true,
        collapsible: false,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        title: 'Customer Periodic',
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
        root: 'rows',

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
        autoSave: false,
        reader: UPRSRSIReader,
        writer: UPRSRSIWriter,
        // or, autosave must be used to save each action
        autoSave: true,
        // won't be updated when combos change, so do this in event
        // perhaps also can be put in the options param for the ajax request
        baseParams: { account:selected_account, sequence: selected_sequence},
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

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    UPRSRSIStore.on('update', function(){
        //UPRSRSIGrid.getTopToolbar().findById('UPRSRSISaveBtn').setDisabled(false);
    });

    UPRSRSIStore.on('save', function (store, batch, data) {
    });

    UPRSRSIStore.on('beforeload', function () {
        UPRSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
        UPRSRSIStore.setBaseParam("account", selected_account);
        UPRSRSIStore.setBaseParam("sequence", selected_sequence);
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
        UPRSRSIGrid.getTopToolbar().findById('UPRSRSISaveBtn').setDisabled(false);
    });

    UPRSRSIStore.on('beforesave', function() {
        UPRSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
        UPRSRSIStore.setBaseParam("account", selected_account);
        UPRSRSIStore.setBaseParam("sequence", selected_sequence);
    });

    var UPRSRSIColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            /*{
                header: 'UUID',
                sortable: true,
                dataIndex: 'uuid',
                editable: false,
                editor: new Ext.form.TextField({allowBlank: false})
            },*/{
                header: 'RSI Binding',
                sortable: true,
                dataIndex: 'rsi_binding',
                editable: true,
                editor: new Ext.form.TextField({allowBlank: false})
            },{
                header: 'Description',
                sortable: true,
                dataIndex: 'description',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Quantity',
                sortable: true,
                dataIndex: 'quantity',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'quantityunits',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Rate',
                sortable: true,
                dataIndex: 'rate',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'rateunits',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Round Rule',
                sortable: true,
                dataIndex: 'roundrule',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Total', 
                sortable: true, 
                dataIndex: 'total', 
                summaryType: 'sum',
                align: 'right',
                editor: new Ext.form.TextField({allowBlank: true})
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
                    var defaultData = 
                    {
                    };
                    var r = new UPRSRSIType(defaultData);
        
                    // select newly inserted record
                    var insertionPoint = URSRSIStore.indexOf(selection);
                    UPRSRSIStore.insert(insertionPoint + 1, r);
                    UPRSRSIGrid.startEditing(insertionPoint +1,1);
                    
                    // An inserted record must be saved 
                    UPRSRSIGrid.getTopToolbar().findById('UPRSRSISaveBtn').setDisabled(false);
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
                    UPRSRSIGrid.getTopToolbar().findById('UPRSRSISaveBtn').setDisabled(true);
                }
            },{
                xtype:'tbseparator'
            },{
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
            }
        ]
    });

    var UPRSRSIGrid = new Ext.grid.EditorGridPanel({
        tbar: UPRSRSIToolbar,
        colModel: UPRSRSIColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: UPRSRSIStore,
        enableColumnMove: true,
        frame: true,
        collapsible: false,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        title: 'Utility Periodic',
        clicksToEdit: 2
    });

    UPRSRSIGrid.getSelectionModel().on('selectionchange', function(sm){
        // if a selection is made, allow it to be removed
        // if the selection was deselected to nothing, allow no 
        // records to be removed.

        UPRSRSIGrid.getTopToolbar().findById('UPRSRSIRemoveBtn').setDisabled(sm.getCount() <1);

        // if there was a selection, allow an insertion
        //UPRSRSIGrid.getTopToolbar().findById('UPRSRSIInsertBtn').setDisabled(sm.getCount() <1);
    });
  


    // the URS
    var initialURSRSI = {
        rows: [
        ]
    };

    var URSRSIReader = new Ext.data.JsonReader({
        // metadata configuration options:
        // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
        //idProperty: 'id',
        root: 'rows',

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

    var URSRSIWriter = new Ext.data.JsonWriter({
        encode: true,
        // write all fields, not just those that changed
        writeAllFields: true 
    });

    var URSRSIStoreProxyConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/ursrsi',
        disableCaching: true,
    });
    URSRSIStoreProxyConn.autoAbort = true;

    var URSRSIStoreProxy = new Ext.data.HttpProxy(URSRSIStoreProxyConn);

    var URSRSIStore = new Ext.data.JsonStore({
        proxy: URSRSIStoreProxy,
        autoSave: false,
        reader: URSRSIReader,
        writer: URSRSIWriter,
        // or, autosave must be used to save each action
        autoSave: true,
        // won't be updated when combos change, so do this in event
        // perhaps also can be put in the options param for the ajax request
        baseParams: { account:selected_account, sequence: selected_sequence},
        data: initialURSRSI,
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

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    URSRSIStore.on('update', function(){
        //URSRSIGrid.getTopToolbar().findById('URSRSISaveBtn').setDisabled(false);
    });

    URSRSIStore.on('save', function (store, batch, data) {
    });

    URSRSIStore.on('beforeload', function () {
        URSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
        URSRSIStore.setBaseParam("account", selected_account);
        URSRSIStore.setBaseParam("sequence", selected_sequence);
    });

    // fired when the datastore has completed loading
    URSRSIStore.on('load', function (store, records, options) {
        // the grid is disabled by the panel that contains it  
        // prior to loading, and must be enabled when loading is complete
        // the datastore enables when it is done loading
        URSRSIGrid.setDisabled(false);
    });

    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    URSRSIStore.on('update', function(){

        // disallow editing of the URS
        //URSRSIGrid.getTopToolbar().findById('URSRSISaveBtn').setDisabled(false);
    });

    URSRSIStore.on('beforesave', function() {
        URSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
        URSRSIStore.setBaseParam("account", selected_account);
        URSRSIStore.setBaseParam("sequence", selected_sequence);
    });

    var URSRSIColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            /*{
                header: 'UUID',
                sortable: true,
                dataIndex: 'uuid',
                editable: false,
                editor: new Ext.form.TextField({allowBlank: false})
            },*/{
                header: 'RSI Binding',
                sortable: true,
                dataIndex: 'rsi_binding',
            },{
                header: 'Description',
                sortable: true,
                dataIndex: 'description',
            },{
                header: 'Quantity',
                sortable: true,
                dataIndex: 'quantity',
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'quantityunits',
            },{
                header: 'Rate',
                sortable: true,
                dataIndex: 'rate',
            },{
                header: 'Units',
                sortable: true,
                dataIndex: 'rateunits',
            },{
                header: 'Round Rule',
                sortable: true,
                dataIndex: 'roundrule',
            },{
                header: 'Total', 
                sortable: true, 
                dataIndex: 'total', 
                summaryType: 'sum',
                align: 'right',
            }
        ]
    });

    var URSRSIToolbar = new Ext.Toolbar({
        items: [
            {
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as grid.insertBtn...
                id: 'URSRSIInsertBtn',
                iconCls: 'icon-add',
                text: 'Insert',
                disabled: true,
                handler: function()
                {
                    URSRSIGrid.stopEditing();

                    // grab the current selection - only one row may be selected per singlselect configuration
                    var selection = URSRSIGrid.getSelectionModel().getSelected();

                    // make the new record
                    var URSRSIType = URSRSIGrid.getStore().recordType;
                    var defaultData = 
                    {
                    };
                    var r = new URSRSIType(defaultData);
        
                    // select newly inserted record
                    var insertionPoint = URSRSIStore.indexOf(selection);
                    URSRSIStore.insert(insertionPoint + 1, r);
                    URSRSIGrid.startEditing(insertionPoint +1,1);
                    
                    // An inserted record must be saved 
                    URSRSIGrid.getTopToolbar().findById('URSRSISaveBtn').setDisabled(false);
                }
            },{
                xtype: 'tbseparator'
            },{
                xtype: 'button',
                // ref places a name for this component into the grid so it may be referenced as aChargesGrid.removeBtn...
                id: 'URSRSIRemoveBtn',
                iconCls: 'icon-delete',
                text: 'Remove',
                disabled: true,
                handler: function()
                {
                    URSRSIGrid.stopEditing();
                    URSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
                    URSRSIStore.setBaseParam("account", selected_account);
                    URSRSIStore.setBaseParam("sequence", selected_sequence);

                    // TODO single row selection only, test allowing multirow selection
                    var s = URSRSIGrid.getSelectionModel().getSelections();
                    for(var i = 0, r; r = s[i]; i++)
                    {
                        URSRSIStore.remove(r);
                    }
                    URSRSIStore.save(); 
                    URSRSIGrid.getTopToolbar().findById('URSRSISaveBtn').setDisabled(true);
                }
            },{
                xtype:'tbseparator'
            },{
                xtype: 'button',
                // places reference to this button in grid.  
                id: 'URSRSISaveBtn',
                iconCls: 'icon-save',
                text: 'Save',
                disabled: true,
                handler: function()
                {
                    // disable the save button for the save attempt.
                    // is there a closer place for this to the actual button click due to the possibility of a double
                    // clicked button submitting two ajax requests?
                    URSRSIGrid.getTopToolbar().findById('URSRSISaveBtn').setDisabled(true);

                    // stop grid editing so that widgets like comboboxes in rows don't stay focused
                    URSRSIGrid.stopEditing();

                    URSRSIStore.setBaseParam("service", Ext.getCmp('service_for_charges').getValue());
                    URSRSIStore.setBaseParam("account", selected_account);
                    URSRSIStore.setBaseParam("sequence", selected_sequence);

                    URSRSIStore.save(); 
                }
            }
        ]
    });

    var URSRSIGrid = new Ext.grid.EditorGridPanel({
        tbar: URSRSIToolbar,
        colModel: URSRSIColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: URSRSIStore,
        enableColumnMove: true,
        frame: true,
        collapsible: false,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        title: 'Utility Global',
        clicksToEdit: 2
    });

    URSRSIGrid.getSelectionModel().on('selectionchange', function(sm){
        // if a selection is made, allow it to be removed
        // if the selection was deselected to nothing, allow no 
        // records to be removed.

        // disallow editing of the URS
        //URSRSIGrid.getTopToolbar().findById('URSRSIRemoveBtn').setDisabled(sm.getCount() <1);

        // if there was a selection, allow an insertion
        //URSRSIGrid.getTopToolbar().findById('URSRSIInsertBtn').setDisabled(sm.getCount() <1);
    });
  

    //
    // Instantiate the Rate Structure panel 
    //
    var rateStructurePanel = new Ext.Panel({
        id: 'rateStructureTab',
        title: 'Rate Structure',
        disabled: rateStructurePanelDisabled,
        layout: 'border',
        items: [
        {
            region: 'north',
            layout: 'fit',
            split: true,
            items: [CPRSRSIGrid]
        },{
            region: 'center',
            layout: 'fit',
            split: true,
            items: [UPRSRSIGrid]
        },{
            region:'south',
            layout: 'fit',
            split: true,
            items: [URSRSIGrid]
        }]
    });

    // this event is received when the tab panel tab is clicked on
    // and the panels it contains are displayed in accordion layout
    rateStructurePanel.on('activate', function (panel) {

        // because this tab is being displayed, demand the grids that it contain 
        // be populated
        CPRSRSIGrid.setDisabled(true);
        CPRSRSIStore.reload();

        URSRSIGrid.setDisabled(true);
        URSRSIStore.reload();

        UPRSRSIGrid.setDisabled(true);
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
            {name: 'date', mapping: 'date'},
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
        method: 'GET',
        prettyUrls: false,
        url: 'http://'+location.host+'/reebill/payment',
        disableCaching: true,
    });
    paymentStoreProxyConn.autoAbort = true;

    var paymentStoreProxy = new Ext.data.HttpProxy(paymentStoreProxyConn);

    var paymentStore = new Ext.data.JsonStore({
        proxy: paymentStoreProxy,
        autoSave: false,
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
            {
                name: 'date',
                type: 'date',
                dateFormat: 'Y-m-d'
            },
            {name: 'description'},
            {name: 'credit'},
        ],
    });

    paymentStore.on('load', function (store, records, options) {
        console.log('paymentStore load');
        // the grid is disabled by the panel that contains it  
        // prior to loading, and must be enabled when loading is complete
        paymentGrid.setDisabled(false);
    });

    paymentStore.on('beforeload', function() {
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

    var paymentColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
                header: 'Date',
                sortable: true,
                dataIndex: 'date',
                renderer: function(date) { if (date) return date.format("Y-m-d"); },
                editor: new Ext.form.DateField({
                    allowBlank: false,
                    format: 'Y-m-d',
               }),
            },{
                header: 'Description',
                sortable: true,
                dataIndex: 'description',
                editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Credit',
                sortable: true,
                dataIndex: 'credit',
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
                handler: function()
                {
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
                    for(var i = 0, r; r = s[i]; i++)
                    {
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
        selModel: new Ext.grid.RowSelectionModel({singleSelect: true}),
        store: paymentStore,
        enableColumnMove: false,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        title: 'Payments',
        clicksToEdit: 2
    });

    paymentGrid.getSelectionModel().on('selectionchange', function(sm){
        //paymentGrid.getTopToolbar().findById('paymentInsertBtn').setDisabled(sm.getCount() <1);
        paymentGrid.getTopToolbar().findById('paymentRemoveBtn').setDisabled(sm.getCount() <1);
    });

    //
    // Instantiate the Payments panel
    //
    var paymentsPanel = new Ext.Panel({
        id: 'paymentTab',
        title: 'Pay',
        disabled: paymentPanelDisabled,
        layout: 'accordion',
        items: [paymentGrid, ]
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
        method: 'GET',
        prettyUrls: false,
        url: 'http://'+location.host+'/reebill/reebill',
        disableCaching: true,
    });
    mailReeBillStoreProxyConn.autoAbort = true;
    var mailReebillStoreProxy = new Ext.data.HttpProxy(mailReeBillStoreProxyConn);

    var mailReebillStore = new Ext.data.JsonStore({
        proxy: mailReebillStoreProxy,
        autoSave: false,
        reader: mailReebillReader,
        writer: mailReebillWriter,
        autoSave: true,
        autoLoad: {params:{start: 0, limit: 25}},
        // won't be updated when combos change, so do this in event
        // perhaps also can be put in the options param for the ajax request
        baseParams: { account:"none"},
        paramNames: {start: 'start', limit: 'limit'},
        data: initialMailReebill,
        root: 'rows',
        totalProperty: 'results',
        //idProperty: 'sequence',
        fields: [
            {name: 'sequence'},
        ],
    });

    var mailReebillColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
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
                    var s = mailReebillGrid.getSelectionModel().getSelections();
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
    var mailReebillGrid = new Ext.grid.EditorGridPanel({
        flex: 1,
        tbar: mailReebillToolbar,
        bbar: new Ext.PagingToolbar({
            // TODO: constant
            pageSize: 25,
            store: mailReebillStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No ReeBills to display",
        }),
        colModel: mailReebillColModel,
        selModel: new Ext.grid.RowSelectionModel({singleSelect: false}),
        store: mailReebillStore,
        enableColumnMove: false,
        frame: true,
        collapsible: true,
        animCollapse: false,
        stripeRows: true,
        viewConfig: {
            // doesn't seem to work
            forceFit: true,
        },
        title: 'Mail ReeBills',
        clicksToEdit: 2
    });

    mailReebillGrid.getSelectionModel().on('selectionchange', function(sm){
    });
  
    // grid's data store callback for when data is edited
    // when the store backing the grid is edited, enable the save button
    mailReebillStore.on('update', function(){
    });

    mailReebillStore.on('beforesave', function() {
        reebillStore.setBaseParam("account", selected_account);
    });

    //
    // Instantiate the Mail panel
    //
    var mailPanel = new Ext.Panel({
        id: 'mailTab',
        title: 'Mail',
        disabled: mailPanelDisabled,
        layout: 'vbox',
        layoutConfig : {
            align : 'stretch',
            pack : 'start'
        },
        items: [mailReebillGrid, ]
    });

    ///////////////////////////////////////
    // Accounts Tab

    ///////////////////////////////////////
    // account status

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
            {name: 'dayssince', mapping: 'dayssince'}
        ]
    });

    var accountStore = new Ext.data.JsonStore({
        root: 'rows',
        totalProperty: 'results',
        pageSize: 25,
        paramNames: {start: 'start', limit: 'limit'},
        autoLoad: {params:{start: 0, limit: 25}},
        reader: accountReader,
        fields: [
            {name: 'account'},
            {name: 'fullname'},
            {name: 'dayssince'},
        ],
        url: 'http://' + location.host + '/reebill/retrieve_account_status',
    });


    var accountColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
                header: 'Account',
                sortable: true,
                dataIndex: 'fullname',
                editable: false,
            },{
                header: 'Days since last bill',
                sortable: true,
                dataIndex: 'dayssince',
                editable: false,
            },
        ]
    });

    // this grid tracks the state of the currently selected account
    var accountGrid = new Ext.grid.GridPanel({
        colModel: accountColModel,
        selModel: new Ext.grid.RowSelectionModel({
            singleSelect: true,
            listeners: {
                rowselect: function (selModel, index, record) {
                    loadReeBillUIForAccount(record.data.account);
                }
            }
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
            pageSize: 25,
            store: accountStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No statuses to display",
        }),
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
            {name: 'fullname', mapping: 'fullname'},
            {name: 'ree_charges', mapping: 'ree_charges'},
            {name: 'actual_charges', mapping: 'actual_charges'},
            {name: 'hypothetical_charges', mapping: 'hypothetical_charges'},
            {name: 'total_energy', mapping: 'total_energy'},
            {name: 'marginal_rate_therm', mapping: 'marginal_rate_therm'},
        ]
    });

    var accountReeValueStore = new Ext.data.JsonStore({
        root: 'rows',
        totalProperty: 'results',
        pageSize: 25,
        paramNames: {start: 'start', limit: 'limit'},
        autoLoad: {params:{start: 0, limit: 25}},
        reader: accountReeValueReader,
        fields: [
            {name: 'account'},
            {name: 'fullname'},
            {name: 'ree_charges'},
            {name: 'actual_charges'},
            {name: 'hypothetical_charges'},
            {name: 'total_energy'},
            {name: 'marginal_rate_therm'},
        ],
        url: 'http://' + location.host + '/reebill/summary_ree_charges',
    });


    var accountReeValueColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
                header: 'Account',
                sortable: true,
                dataIndex: 'fullname',
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
                header: 'Marginal Rate per Therm',
                sortable: true,
                dataIndex: 'marginal_rate_therm',
                editable: false,
            },
        ]
    });

    var accountReeValueToolbar = new Ext.Toolbar({
        items: [
            {
                id: 'accountReeValueExportCSVBtn',
                iconCls: 'icon-application-go',
                xtype: 'linkbutton',
                href: "http://"+location.host+"/reebill/all_ree_charges_csv",
                text: 'Export REE Value CSV',
                disabled: true,
            },{
                id: 'exportButton',
                iconCls: 'icon-application-go',
                // TODO:25227403 - export on account at a time 
                xtype: 'linkbutton',
                href: "http://"+location.host+"/reebill/excel_export",
                text: 'Export All Utility Bills to Excel',
                disabled: false,
            },{
                id: 'exportAccountButton',
                iconCls: 'icon-application-go',
                xtype: 'linkbutton',
                // account parameter for URL is set in loadReeBillUIForAccount()
                href: "http://"+location.host+"/reebill/excel_export",
                text: "Export Selected Account's Utility Bills to Excel",
                disabled: true, 
            }
        ]
    });

    // this grid tracks the state of the currently selected account

    var accountReeValueGrid = new Ext.grid.GridPanel({
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

    var newAccountTemplateStore = new Ext.data.JsonStore({
        // store configs
        autoDestroy: true,
        autoLoad: true,
        url: 'http://'+location.host+'/reebill/listAccounts',
        storeId: 'newAccountTemplateStore',
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

    var newAccountField = new Ext.form.TextField({
        fieldLabel: 'Account',
        name: 'account',
        allowBlank: false,
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

    var billStructureTreeLoader = new Ext.tree.TreeLoader({dataUrl:'http://'+location.host+'/reebill/reebill_structure'});
    var billStructureTree = new Ext.tree.TreePanel({
        title: 'Bill Structure Browser',
        frame: true,
        animate:true, 
        autoScroll:true,
        loader: billStructureTreeLoader,
        enableDD:true,
        containerScroll: true,
        border: true,
        //width: 250,
        //height: 300,
        autoWidth: true,
        dropConfig: {appendOnly:true}
    });
    
    // add a tree sorter in folder mode
    new Ext.tree.TreeSorter(billStructureTree, {folderSort:true});
    
    // set the root node
    var billStructureRoot = new Ext.tree.AsyncTreeNode({
        text: 'ReeBill', 
        draggable:false, // disable root node dragging
        id:'bill_structure_root'
    });
    billStructureTree.setRootNode(billStructureRoot);
    
    billStructureRoot.expand(false, /*no anim*/ false);

    // event to link the account selection changes to reload structure tree
    newAccountTemplateCombo.on('select', function(combobox, record, index) {
        billStructureTree.enable();
        billStructureTree.getLoader().dataUrl = 'http://'+location.host+'/reebill/reebill_structure';
        billStructureTree.getLoader().baseParams.account = newAccountTemplateCombo.getValue();
        //billStructureTree.getLoader().baseParams.sequence = null; 
        billStructureTree.getLoader().load(billStructureTree.root);
        billStructureRoot.expand(true, true);
        
    });

    billStructureTreeLoader.on("beforeload", function(treeLoader, node) {
    });

    var newAccountFormPanel = new Ext.FormPanel({
        url: 'http://'+location.host+'/reebill/new_account',
        labelWidth: 95, // label settings here cascade unless overridden
        frame: true,
        title: 'Create New Account',
        defaults: {
            anchor: '95%',
            xtype: 'textfield',
        },
        defaultType: 'textfield',
        items: [newAccountField, newNameField, newDiscountRate, newAccountTemplateCombo, billStructureTree  ],
        buttons: [
            new Ext.Button({
                text: 'Save',
                handler: function() {
                    // TODO 22645885 show progress during post
                    Ext.Ajax.request({
                        url: 'http://'+location.host+'/reebill/new_account',
                        params: { 
                          'name': newNameField.getValue(),
                          'account': newAccountField.getValue(),
                          'template_account': newAccountTemplateCombo.getValue(),
                          'discount_rate': newDiscountRate.getValue()
                        },
                        disableCaching: true,
                        success: function(result, request) {
                            var jsonData = null;
                            try {
                                jsonData = Ext.util.JSON.decode(result.responseText);
                                if (jsonData.success == false) {
                                    // handle failure here if necessary
                                }
                            } catch (err) {
                                Ext.MessageBox.alert('ERROR', 'Local:  '+ err + ' Remote: ' + result.responseText);
                            }
                            // TODO 22645885 confirm save and clear form
                        },
                        failure: function () {
                            Ext.Msg.alert("Create new account request failed");
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
        items: [accountGrid,accountReeValueGrid,newAccountFormPanel, ]
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
                // TODO: 25593817
                Ext.Ajax.request({
                    url: 'http://'+location.host+'/reebill/setBillImageResolution',
                    params: { 'resolution': billImageResolutionField.getValue() },
                    disableCaching: true,
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
    // TODO: 22360193 populating a form from Ajax creates a race condition.  
    // What if the network doesn't return and user enters a value nefore the callback is fired?
    var resolution = null;
    //TODO 25593817
    Ext.Ajax.request({
        url: 'http://'+location.host+'/reebill/getBillImageResolution',
        disableCaching: true,
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
        items: [preferencesFormPanel, ],
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
        method: 'GET',
        prettyUrls: false,
        url: 'http://'+location.host+'/reebill/journal',
        disableCaching: true,
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
        fields: [
            {name: '_id'},
            {
                name: 'date',
                type: 'date',
                //dateFormat: 'Y-m-d'
            },
            {name: 'account'},
            {name: 'sequence'},
            {name: 'msg'},
        ],
    });

    var journalColModel = new Ext.grid.ColumnModel(
    {
        columns: [
            {
                header: 'ObjectId',
                sortable: true,
                dataIndex: '_id',
            },{
                header: 'Date',
                sortable: true,
                dataIndex: 'date',
                renderer: function(date) { if (date) return date.format(Date.patterns['ISO8601Long']); },
                editor: new Ext.form.DateField({
                    allowBlank: false,
                    format: Date.patterns['ISO8601Long'],
               }),
            },{
                header: 'Account',
                sortable: true,
                dataIndex: 'account',
                //editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Sequence',
                sortable: true,
                dataIndex: 'sequence',
                //editor: new Ext.form.TextField({allowBlank: true})
            },{
                header: 'Message',
                sortable: true,
                dataIndex: 'msg',
                //editor: new Ext.form.TextField({allowBlank: true})
            },
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

    journalStore.on('beforesave', function() {
        journalStore.setBaseParam("account", selected_account);
    });
    */

    var journalGrid = new Ext.grid.EditorGridPanel({
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
        title: 'Journal Entries',
        clicksToEdit: 2
    });

    //
    // Set up the journal memo widget
    //
    // account field
    var journalEntryField = new Ext.form.TextField({
        fieldLabel: 'Journal',
        name: 'entry',
        width: 300,
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
        handler: saveForm,
    });
    var journalFormPanel = new Ext.form.FormPanel({
        url: 'http://'+location.host+'/reebill/save_journal_entry',
        frame: true,
        border: false,
        width: 400,
        layout: 'hbox',
        defaults: {
            layout: 'form'
        },
        items: [
            journalEntryField, 
            journalEntryResetButton, journalEntrySubmitButton,
            journalEntryAccountField, journalEntrySequenceField
        ],
        hideLabels: false,
        labelAlign: 'left',   // or 'right' or 'top'
        labelSeparator: '', // takes precedence over layoutConfig value
        labelWidth: 65,       // defaults to 100
        labelPad: 8           // defaults to 5, must specify labelWidth to be honored
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
        items: [journalGrid, ]
    });



    ///////////////////////////////////////////
    // Reconciliation Tab
    //

    var reconciliationGridStore = new Ext.data.JsonStore({
        root: 'rows',
        totalProperty: 'results',
        pageSize: 30,
        //baseParams: {},
        paramNames: {start: 'start', limit: 'limit'},
        //autoLoad: {params:{start: 0, limit: 25}},

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
        url: 'http://' + location.host + '/reebill/get_reconciliation_data',
    });

    var reconciliationGrid = new Ext.grid.GridPanel({
        title:'Reebills with >0.1% difference from OLTP or errors',
        store: reconciliationGridStore,
        trackMouseOver:false,
        layout: 'fit',
        sortable: true,
        autoExpandColumn: 'errors',

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

    //
    // Instantiate the Reconciliation panel
    //
    var reconciliationPanel = new Ext.Panel({
        id: 'reconciliationTab',
        title: 'Reconciliation Report',
        disabled: reconciliationPanelDisabled,
        xtype: 'panel',
        layout: 'fit',
        items: [reconciliationGrid, ],
    });


    ///////////////////////////////////////////
    // About Tab
    //
    var aboutPanel = new Ext.Panel({
        id: 'aboutTab',
        title: 'About',
        disabled: aboutPanelDisabled,
        html: '<table style="width: 100%; border: 0; margin-top:20px;"><tr><td align="center">' + SKYLINE_VERSIONINFO + '</td></tr><tr><td align="center"><img width="50%" src="MrJonas.png"/></td></tr><tr><td align="center"><font style="font-family: impact; font-size:68pt;">Masterbiller</font></td></tr></table>',
    });

    // end of tab widgets
    ////////////////////////////////////////////////////////////////////////////

    ////////////////////////////////////////////////////////////////////////////
    // Status bar displayed at footer of every panel in the tabpanel

    var statusBar = new Ext.ux.StatusBar({
        defaultText: 'No REE Bill Selected',
        id: 'statusbar',
        statusAlign: 'right', // the magic config
        items: [journalFormPanel]
    });

    ////////////////////////////////////////////////////////////////////////////
    // construct tabpanel and the panels it contains for the viewport

    // Assemble all of the above panels into a parent tab panel
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
            accountsPanel,
            paymentsPanel,
            utilityBillPanel,
            reeBillPanel,
            ubBillPeriodsPanel,
            ubMeasuredUsagesPanel,
            rateStructurePanel,
            chargeItemsPanel,
            journalPanel,
            mailPanel,
            reconciliationPanel,
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

    // update selection in statusbar
    function updateStatusbar(account, sequence, branch)
    {

        var sb = Ext.getCmp('statusbar');
        var selStatus;
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

    // load things global to the account
    function loadReeBillUIForAccount(account) {

        selected_account = account;
        selected_sequence = null;

        // a new account has been selected, deactivate subordinate tabs
        ubBillPeriodsPanel.setDisabled(true);
        ubMeasuredUsagesPanel.setDisabled(true);
        rateStructurePanel.setDisabled(true);
        chargeItemsPanel.setDisabled(true);
        journalPanel.setDisabled(true);
        mailPanel.setDisabled(true);

        // TODO: 25226989 ajax cancelled???

        // unload previously loaded utility and reebill images
        // TODO 25226739: don't overwrite if they don't need to be updated.  Causes UI to flash.
        Ext.DomHelper.overwrite('utilbillimagebox', getImageBoxHTML(null, 'Utility bill', 'utilbill', NO_UTILBILL_SELECTED_MESSAGE), true);
        Ext.DomHelper.overwrite('reebillimagebox', getImageBoxHTML(null, 'Reebill', 'reebill', NO_REEBILL_SELECTED_MESSAGE), true);

        // update list of ReeBills (for mailing) for this account
        mailReebillStore.setBaseParam("account", account)

        // paging tool bar params must be passed in to keep store in sync with toolbar paging calls - autoload params lost after autoload
        mailReebillStore.reload({params:{start:0, limit:25}});

        // update list of journal entries for this account
        journalStore.reload({params: {account: account}});

        // update the journal form panel so entries get submitted to currently selected account
        // need to set account into a hidden field here since there is no data store behind the form
        journalFormPanel.getForm().findField("account").setValue(account)
        // TODO: 1320091681504 if an account is selected w/o a sequence, a journal entry can't be made

        // add the account to the upload_account field
        upload_account.setValue(account)

        // set begin date for next utilbill in upload form panel to end date of
        // last utilbill, if there is one
        // TODO 25226989:tId not tracked! 
        Ext.Ajax.request({
            url: 'http://'+location.host+'/reebill/last_utilbill_end_date',
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
                            upload_begin_date.setValue('');
                        } else {
                            var lastUtilbillDate = new Date(jsonData['date']);
                            // field automatically converts Date into a string
                            // according to its 'format' property
                            upload_begin_date.setValue(lastUtilbillDate);
                        }
                    } 
                } catch (err) {
                    Ext.MessageBox.alert('ERROR', 'Local:  '+ err + ' Remote: ' + result.responseText);
                }
            },
            failure: function() {alert("ajax failure")},
            disableCaching: true,
        });

        // clear reebill data when a new account is selected
        // TODO: 1320091681504 if an account is selected w/o a sequence, a journal entry can't be made
        journalFormPanel.getForm().findField("sequence").setValue(null)
        configureUBPeriodsForms(null, null, null);
        configureUBMeasuredUsagesForms(null, null, null);
        configureAddressForm(null, null, null);
        configureReeBillEditor(null, null);
        aChargesStore.loadData({rows: 0, success: true});
        hChargesStore.loadData({rows: 0, succes: true});
        CPRSRSIStore.loadData({rows: 0, success: true});
        URSRSIStore.loadData({rows: 0, success: true});
        UPRSRSIStore.loadData({rows: 0, success: true});

        updateStatusbar(account, null, null);


        // enable export buttons 
        Ext.getCmp('exportAccountButton').setDisabled(false);
        Ext.getCmp('exportAccountButton').setParams({'account': account});
        //Ext.getCmp('exportButton').setDisabled(false);
        Ext.getCmp('accountReeValueExportCSVBtn').setDisabled(false);

        // an account has been selected, so enable tabs that act on an account
        reeBillPanel.setDisabled(false);
        paymentsPanel.setDisabled(false);
        utilityBillPanel.setDisabled(false);

    }


    //
    // configure data connections for widgets that are not managed by 
    // datastores.
    //
    var ubPeriodsDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/ubPeriods',
        disableCaching: true,
    });
    ubPeriodsDataConn.autoAbort = true;

    var ubMeasuredUsagesDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/ubMeasuredUsages',
        disableCaching: true,
    });
    ubMeasuredUsagesDataConn.autoAbort = true;

    var addressesDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/addresses',
        disableCaching: true,
    });
    addressesDataConn.autoAbort = true;


    var reeBillImageDataConn = new Ext.data.Connection({
        url: 'http://'+location.host+'/reebill/getReeBillImage',
        disableCaching: true,
    });
    reeBillImageDataConn.autoAbort = true;

    function loadReeBillUIForSequence(account, sequence) {

        // TODO: 25227109 properly reset reebill UI if no sequence is selected

        if (account == null || sequence == null) {
            throw "Account and Sequence must be set";
        }

        selected_account = account;
        selected_sequence = sequence;

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

        // update the journal form panel so entries get submitted to currently selected account
        // need to set account into a hidden field here since there is no data store behind the form
        journalFormPanel.getForm().findField("sequence").setValue(sequence)




        // TODO:23046181 abort connections in progress
        configureReeBillEditor(selected_account, selected_sequence);

        // image rendering resolution
        var menu = document.getElementById('reebillresolutionmenu');
        if (menu) {
            resolution = menu.value;
        } else {
            resolution = DEFAULT_RESOLUTION;
        }
       
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

        // while waiting for the ajax request to finish, show a loading message
        // in the utilbill image box
        Ext.DomHelper.overwrite('reebillimagebox', {tag: 'div', html:LOADING_MESSAGE, id: 'reebillimage'}, true);

        // Now that a ReeBill has been loaded, enable the tabs that act on a ReeBill
        // These enabled tabs will then display widgets that will pull data based on
        // the global account and sequence selection
        ubBillPeriodsPanel.setDisabled(false);
        ubMeasuredUsagesPanel.setDisabled(false);
        rateStructurePanel.setDisabled(false);
        chargeItemsPanel.setDisabled(false);
        journalPanel.setDisabled(false);
        mailPanel.setDisabled(false);

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


var NO_UTILBILL_SELECTED_MESSAGE = '<div style="position:absolute; top:30%;"><table style="width: 100%;"><tr><td style="text-align: center;"><img src="select_utilbill.png"/></td></tr></table></div>';
var NO_UTILBILL_FOUND_MESSAGE = '<div style="position:absolute; top:30%;"><table style="width: 100%;"><tr><td style="text-align: center;"><img src="select_utilbill_notfound.png"/></td></tr></table></div>';
var NO_REEBILL_SELECTED_MESSAGE = '<div style="position:absolute; top:30%;"><table style="width: 100%;"><tr><td style="text-align: center;"><img src="select_reebill.png"/></td></tr></table></div>';
var NO_REEBILL_FOUND_MESSAGE = '<div style="position:absolute; top:30%;"><table style="width: 100%;"><tr><td style="text-align: center;"><img src="select_reebill_notfound.png"/></td></tr></table></div>';
var LOADING_MESSAGE = '<div style="position:absolute; top:30%;"><table style="width: 100%;"><tr><td style="text-align: center;"><img src="rotologo_white.gif"/></td></tr></table></div>';

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
