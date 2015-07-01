Ext.define('BillEntry.view.uploadbills.Dropzone', {
    extend: 'Ext.form.Panel',

    alias: 'widget.dropzone',

    titleCollapse: true,
    floatable: false,

    initComponent: function() {
        var me = this,
            userItems = me.items || [];

        userItems.push({
                           itemId: 'bills-upload-form',
                           xtype: 'container',
                           width: '100%',
                           height: '100%',
                           html: '<iframe src="dropzone.html" id="dropzoneIFrame" style="border:0px;width:100%;height:100%"></iframe>'
                       });
        me.items = userItems;

        me.callParent(arguments);
    }
})
