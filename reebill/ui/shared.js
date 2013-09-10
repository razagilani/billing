/* This file contains constructor functions for UI widgets and other objects
 * that are shared between ReeBill and XBill UIs. */


var NO_UTILBILL_SELECTED_MESSAGE = '<div style="display: block; margin-left: auto; margin-right: auto;"><table style="height: 100%; width: 100%;"><tr><td style="text-align: center;"><img src="select_utilbill.png"/></td></tr></table></div>';
var NO_UTILBILL_FOUND_MESSAGE = '<div style="display: block; margin-left: auto; margin-right: auto;"><table style="height: 100%; width: 100%;"><tr><td style="text-align: center;"><img src="select_utilbill_notfound.png"/></td></tr></table></div>';
var LOADING_MESSAGE = '<div style="display: block; margin-left: auto, margin-right: auto;"><table style="height: 100%; width: 100%;"><tr><td style="text-align: center;"><img src="rotologo_white.gif"/></td></tr></table></div>';

var selected_account = null;












var accountStoreProxyConn = new Ext.data.Connection({
    url: 'http://' + location.host + '/reebill/retrieve_account_status',
});
accountStoreProxyConn.autoAbort = true;
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
var accountStoreProxy = new Ext.data.HttpProxy(accountStoreProxyConn);
var accountStore = new Ext.data.JsonStore({
    proxy: accountStoreProxy,
    root: 'rows',
    totalProperty: 'results',
    remoteSort: true,
    paramNames: {start: 'start', limit: 'limit'},
    //sortInfo: {
        //field: defaultAccountSortField,
        //direction: defaultAccountSortDir,
    //},
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


/* 'title': label text shown above grid
 * 'columnNames': list of names of columns to include in the grid
 * 'initialSortInfo': {field: <name of column to sort by>, direction: <"ASC" or "DESC">}
 */
function CustomerAccountGrid(title, columnNames, initialSortInfo) {
    /* config objects for Ext.grid.Columns that can go in a grid of customer
     * account information. The grid inheriting from this constructor specifies
     * a list of names to choose which columns should be shown. */
    var standardColumns = {
        'account': {
            header: 'Account',
            sortable: true,
            dataIndex: 'account',
            renderer: accountGridColumnRenderer,
        },
        'codename': {
            header: 'Codename',
            sortable: true,
            dataIndex: 'codename',
            renderer: accountGridColumnRenderer,
        },
        'casualname': {
            header: 'Casual Name',
            sortable: true,
            dataIndex: 'casualname',
            renderer: accountGridColumnRenderer,
        },
        'primusname': {
            header: 'Primus Name',
            sortable: true,
            dataIndex: 'primusname',
            renderer: accountGridColumnRenderer,
        },
        'utilityserviceaddress': {
            header: 'Utility Service Address',
            sortable: true,
            dataIndex: 'utilityserviceaddress',
            renderer: accountGridColumnRenderer,
        },
        'lastissuedate': {
            header: 'Last Issued',
            sortable: true,
            dataIndex: 'lastissuedate',
            renderer: accountGridColumnRenderer,
        },
        'dayssince': {
            header: 'Days Since Utility Bill',
            sortable: true,
            dataIndex: 'dayssince',
            renderer: accountGridColumnRenderer,
        },
        'lastevent': {
            header: 'Last Event',
            sortable: false,
            dataIndex: 'lastevent',
            renderer: accountGridColumnRenderer,
            width: 350,
        }
    }

    this.title = title;

    var the_columns = [];
    for (var i = 0; i < columnNames.length; i++) {
        the_columns.push(standardColumns[columnNames[i]]);
    }
    this.colModel = new Ext.grid.ColumnModel({columns: the_columns});

    this.selModel = new Ext.grid.RowSelectionModel({singleSelect:true});

    this.store = accountStore;

    this.store = new Ext.data.JsonStore({
        proxy: accountStoreProxy,
        root: 'rows',
        totalProperty: 'results',
        remoteSort: true,
        paramNames: {start: 'start', limit: 'limit'},
        sortInfo: initialSortInfo,
        autoLoad: {params:{start: 0, limit: 30}},
        reader: accountReader,
        fields: columnNames,
    });
    this.frame = true;
    this.collapsible = true;
};

CustomerAccountGrid.prototype = new Ext.grid.EditorGridPanel(
    /* the properties defined here apparently can't be defined by
     * "this. ... = ..." as above */

    {
        viewConfig: { forceFit: true, },

        bbar: new Ext.PagingToolbar({
            pageSize: 30,
            store: accountStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No statuses to display",
        }),
})







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
        {name: 'rate_structure', mapping: 'rate_structure'},
        {name: 'utility', mapping: 'utility'},
        {name: 'account', mapping: 'account'},
        {name: 'period_start', mapping: 'period_start'},
        {name: 'period_end', mapping: 'period_end'},
        {name: 'total_charges', mapping: 'total_charges'},
        {name: 'sequence', mapping: 'sequence'},
        {name: 'state', mapping: 'state'},
    ]
});

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
    reader: utilbillReader,
    writer: utilbillWriter,
    baseParams: { start:0, limit: 25},
    data: initialutilbill,
    root: 'rows',
    totalProperty: 'results',
    // defaults to id? probably should explicity state it until we are ext experts
    //idProperty: 'sequence',
    fields: [
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
    {name: 'sequence'},
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
            header: 'Sequence',
            dataIndex: 'sequence',
            width: 70,
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
            // ref places a name for this component into the grid so it may be referenced as [name]Grid.removeBtn...
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
        }]
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
                //loadReeBillUIForSequence(record.data.account, null);
            },
            
            rowselect: function (selModel, index, record) {

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
            }
        }
    }),
});

