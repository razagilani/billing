/**
 * Created by thoffmann on 9/9/14.
 */
var utils = function() {
    var makeServerExceptionWindow = function(statusCode, statusText, content){
        var win = Ext.create('Ext.window.Window', {
            modal: true,
            autoScroll: true,
            width: 850,
            maxHeight: 650,
            cls: 'messageBoxOverflow',
            title: "Server error - " + statusCode + " - " + statusText,
            layout     : {
                type  : 'hbox',
                align : 'stetch'
            },
            items      : [
                {
                    html : content,
                    flex : 1
                }
            ]
        });
        win.show();
        win.center();
    };

    var makeGridFilterTextField = function(field_name){
        /*
         * Creates a Textbox for a GridColumn with proper keyup listener that
         * updates the filter of the Grid's store whenever the textfield changes.
         * field_name is the field name of the stre that should be filtered by
         */
        return {
            xtype: 'textfield',
            flex : 1,
            margin: 2,
            emptyText: 'Filter',
            enableKeyEvents: true,
            listeners: {
                keyup: function() {
                    var store = this.up('tablepanel').store;
                    var filterid = 'filter' + field_name;
                    // Remove previous filter if one exists
                    if(store.filters.getByKey(filterid) != undefined) {
                        store.removeFilter(filterid, !this.value);
                    }
                    if (this.value) {
                        store.filter({
                            id: filterid,
                            property     : field_name,
                            value         : this.value,
                            anyMatch      : true,
                            caseSensitive : false
                        });
                    }
                },
                buffer: 150
            }
        };
    };

    var makeProxyExceptionHandler = function(storeName) {
        /* Creates a function which rejects changes in the store storeName and
         shows and appropriate error message box */
        return function (proxy, response, operation) {
            var statusText, responseText;
            if (response.status === 0) {
                statusText = 'Connection Refused';
                responseText = 'The server has refused the connection!';
            } else {
                statusText = response.statusText;
                responseText = response.responseText;
            }

            Ext.getStore(storeName).rejectChanges();
            makeServerExceptionWindow(response.status, statusText, responseText)
        }
    };

    return {
        makeProxyExceptionHandler: makeProxyExceptionHandler,
        makeServerExceptionWindow: makeServerExceptionWindow,
        makeGridFilterTextField: makeGridFilterTextField
    };
}();
