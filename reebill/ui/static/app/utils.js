/**
 * Created by thoffmann on 9/9/14.
 */
var utils = function() {
    var makeProxyExceptionHandler = function(storeName) {
        /* Creates a function which rejects changes in the store storeName and
         shows and appropriate error message box */
        return function (proxy, response, operation) {
            if (response.status === 0) {
                var statusText = 'Connection Refused';
                var responseText = 'The server has refused the connection!';
                var cls = ''
            } else {
                var statusText = response.statusText;
                var responseText = response.responseText;
                var cls = 'messageBoxOverflow'
            }

            Ext.getStore(storeName).rejectChanges();
            Ext.MessageBox.show({
                title: "Server error - " + response.status + " - " + statusText,
                msg: responseText,
                icon: Ext.MessageBox.ERROR,
                buttons: Ext.Msg.OK,
                cls: cls
            });
        }
    };

    return {makeProxyExceptionHandler: makeProxyExceptionHandler};
}();
