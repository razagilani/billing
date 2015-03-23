Ext.define('BillEntry.view.reports.BillDetails', {
    extend: 'BillEntry.view.utilitybills.UtilityBills',
    alias: 'widget.billDetails',
    store: 'UtilityBills',
    title: 'Utility Bills',

    plugins: [],
    dockedItems: []

    //plugins: [
    //    Ext.create('Ext.grid.plugin.CellEditing', {
    //        clicksToEdit: 2,
    //        listeners: {
    //            beforeedit: function (e, editor) {
    //                if (editor.record.get('processed'))
    //                    return false;
    //            }
    //        }
    //    })
    //],

});