Ext.define('ReeBill.controller.UtilityBills', {
    extend: 'Ext.app.Controller',

    stores: [
        'UtilityBills',
        'ReeBillVersions',
        'RateClasses',
        'Suppliers',
        'Utilities',
        'Services',
        'SupplyGroups'
    ],

    views: [
        'utilitybills.UtilityBills',
        'utilitybills.UploadUtilityBill'
    ],
    
    refs: [{
        ref: 'uploadUtilityBillForm',
        selector: 'uploadUtilityBill'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'utilbillCompute',
        selector: '[action=utilbillCompute]'
    },{
        ref: 'utilbillRemove',
        selector: '[action=utilbillRemove]'
    },{
        ref: 'utilbillToggleProcessed',
        selector: '[action=utilbillToggleProcessed]'
    }],    
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.handleRowSelect
            },
            'panel[name=utilityBillsTab]': {
                activate: this.handleActivate
            },
            '[action=resetUploadUtilityBillForm]': {
                click: this.handleReset
            },
            '[action=submitUploadUtilityBillForm]': {
                click: this.handleSubmit
            },
            '[action=utilbillCompute]': {
                click: this.handleCompute
            },
            '[action=utilbillRemove]': {
                click: this.handleDelete
            },
            '[action=utilbillToggleProcessed]': {
                click: this.handleToggleProcessed
            },
            '#utility_combo':{
                blur: this.handleUtilityBlur,
                focus: this.handleUtilityComboFocus
            },
            '#rate_class_combo': {
                expand: this.handleRateClassExpand,
                focus: this.handleRateClassComboFocus,
                blur: this.handleRateClassBlur
            },
            '#supplier_combo': {
                blur: this.handleSupplierBlur,
                focus: this.handleSupplierComboFocus
            },
            '#supply_group_combo': {
                focus: this.handleSupplyGroupComboFocus,
                expand: this.handleSupplyGroupComboExpand,
                blur: this.handleSupplyGroupBlur
            }

        });

        this.getUtilityBillsStore().on({
            beforeload: function(store){
                var grid = this.getUtilityBillsGrid();
                grid.setLoading(true);
            },
            load: function(store) {
                var grid = this.getUtilityBillsGrid();
                grid.setLoading(false);
                this.initalizeUploadForm();
            },
            beforesync: function(options, eOpts){
                console.log('utilitybills before sync', options, eOpts)
            },
            scope: this
        });

        this.getRateClassesStore().on({
            beforesync: function(options, eOpts){
                console.log('rateclasses before sync', options, eOpts)
            }
                                      })
        this.getUtilitiesStore().on({
            beforesync: function(options, eOpts){
                console.log('utilities before sync', options, eOpts)
            }
                                      })
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function(combo, recs) {
        var hasSelections = recs.length > 0;
        var selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        if (selected != null)
        {
            var processed = selected.get('processed')
            //console.log(selected[0].get('processed'));
            this.getUtilbillCompute().setDisabled(!hasSelections || selected.get('processed'));
            this.getUtilbillToggleProcessed().setDisabled(!hasSelections);

            var hasReebill = false;
            Ext.each(recs, function (rec) {
                if (rec.get('reebills').length > 0)
                    hasReebill = true;
            });

            this.getUtilbillRemove().setDisabled(!hasSelections || hasReebill || processed);
            var utility_id = selected.data.utility;
            rate_class_store = Ext.getStore("RateClasses");
            rate_class_store.clearFilter(true);
            rate_class_store.filter('utility_id', utility_id);
    }
        else
        {
            this.getUtilbillCompute().setDisabled(true);
            this.getUtilbillToggleProcessed().setDisabled(!hasSelections);
            this.getUtilbillRemove().setDisabled(!hasSelections);
        }
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();
        var store = this.getUtilityBillsStore();

        if (!selectedAccount || !selectedAccount.length)
            return;

        var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();
        store.getProxy().setExtraParam('account', selectedAccount[0].get('account'));
        store.reload();
    },

    /**
     * Initialize the upload form.
     */
    initalizeUploadForm: function() {
        var form = this.getUploadUtilityBillForm(),
            selected = this.getAccountsGrid().getSelectionModel().getSelection(),
            accountField = form.down('[name=account]'),
            startDateField = form.down('[name=begin_date]'),
            endDateField = form.down('[name=end_date]');
        var store = this.getUtilityBillsStore();

        form.getForm().reset();

        if (!selected || !selected.length)
            return;
        var lastEndDate = store.getLastEndDate();
        // If there is no record in the store set the date to one month ago from today
        if(!lastEndDate){
            lastEndDate = Ext.Date.add(new Date(), Ext.Date.MONTH, -1);
        }
        accountField.setValue(selected[0].get('account'));
        startDateField.setValue(lastEndDate);
        endDateField.setValue(Ext.Date.add(lastEndDate, Ext.Date.MONTH, 1));
    },

    /**
     * Handle the compute button being clicked.
     */
    handleReset: function() {
        this.initalizeUploadForm(); 
    },

    /**
     * Handle the submit button being clicked.
     */
    handleSubmit: function() {
        var scope = this,
            store = this.getUtilityBillsStore();

        this.getUploadUtilityBillForm().getForm().submit({
            url: 'http://'+window.location.host+'/reebill/utilitybills',
            success: function() {
                scope.initalizeUploadForm();
                store.reload();
            },
            failure: function(form, action) {
                utils.makeServerExceptionWindow(
                    'Unknown', 'Error', action.response.responseXML.body.innerHTML);
            }
        }); 
    },

    /**
     * Handle the compute button being clicked.
     */
    handleCompute: function() {
        var scope = this,
            selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];

        if (!selected)
            return;

        selected.set('action', 'compute');
    },

    /**
     * Handle the delete button being clicked.
     */
    handleDelete: function() {
        var scope = this,
            store = this.getUtilityBillsStore(),
            grid = this.getUtilityBillsGrid(),
            selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];

        if (!selected)
            return;

        Ext.Msg.confirm('Confirm deletion',
            'Are you sure you want to delete the selected Utility Bill(s)?',
            function(answer) {
                if (answer == 'yes') {
                    store.remove(selected)
                    grid.fireEvent('deselect', selected, 0);
                }
            });
    },
    
    /**
     * Handle the toggle processed button being clicked.
     */
    handleToggleProcessed: function() {
        var grid = this.getUtilityBillsGrid(),
            selected = grid.getSelectionModel().getSelection()[0];

        if (!selected)
            return;
        selected.set('processed', !selected.get('processed'));
        var processed = selected.get('processed');
        this.getUtilbillCompute().setDisabled(processed);
    },

    handleUtilityComboFocus: function(combo) {
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        combo.setValue(selected.get('utility').name);
    },

    handleRateClassComboFocus: function(combo) {
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        combo.setValue(selected.get('rate_class').name);
    },

    handleSupplierComboFocus: function(combo) {
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        combo.setValue(selected.get('supplier').name);
    },

    handleSupplyGroupComboFocus: function(combo) {
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        combo.setValue(selected.get('supply_group').name);
    },

    handleRateClassExpand: function(combo, record, index){
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        var rate_class_store = Ext.getStore('RateClasses');
        rate_class_store.clearFilter(true);
        rate_class_store.filter({property:"utility_id", type: 'int',
                                    value: selected.get('utility_id'),
                                    exactMatch:true});
    },

    handleSupplyGroupComboExpand: function(combo, record, index){
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        var supply_group_store = Ext.getStore('SupplyGroups');
        supply_group_store.clearFilter(true);
        supply_group_store.filter({property:"supplier_id", type: 'int',
                                    value: selected.get('supplier_id'),
                                    exactMatch:true});
    },

    handleRateClassBlur: function(combo, event, opts){
        var rateClassStore = this.getRateClassesStore();
        if (combo.getRawValue() == '') {
            rateClassStore.rejectChanges();
            this.getUtilityBillsStore().rejectChanges();
            return;
        }
        var selected = combo.findParentByType('grid').getSelectionModel().getSelection()[0];
        if (rateClassStore.findRecord('id', combo.getValue()) === null){
            var utilBillsStore = this.getUtilityBillsStore();
            utilBillsStore.suspendAutoSync();
            rateClassStore.suspendAutoSync();
            rateClassStore.add({name: combo.getRawValue(),
                               utility_id: selected.get('utility_id'),
                               service: selected.get('service')});
            rateClassStore.sync({
                success: function(batch, options){
                    this.getUtilityBillsStore().resumeAutoSync();
                    selected.set('rate_class_id', batch.operations[0].records[0].get('id'));
                },
                failure: function(){
                    this.getUtilityBillsStore().resumeAutoSync();
                },
                scope: this
            });
            rateClassStore.resumeAutoSync();
        }
    },

    handleSupplierBlur: function(combo, event, opts){
        var supplierStore = this.getSuppliersStore();
        if (combo.getRawValue() == "") {
            supplierStore.rejectChanges();
            this.getUtilityBillsStore().rejectChanges();
            return;
        }
        console.log('supplier blur')
        var selected = combo.findParentByType('grid').getSelectionModel().getSelection()[0];
        if (supplierStore.findRecord('id', combo.getValue()) === null){
            var utilBillsStore = this.getUtilityBillsStore();
            utilBillsStore.suspendAutoSync();
            supplierStore.suspendAutoSync();
            //supplierStore.clearFilter(true);
            //var supplier = supplierStore.findRecord('name', combo.getRawValue());
            //if (supplier !== null)
            //{
            //    this.getUtilityBillsStore().resumeAutoSync();
            //    supplierStore.resumeAutoSync();
            //    return;
            //}
            supplierStore.add({name: combo.getRawValue()});
            supplierStore.sync({
                success: function(batch, options){
                    this.getUtilityBillsStore().resumeAutoSync();
                    selected.set('supplier_id', batch.operations[0].records[0].get('id'));
                },
                failure: function(){
                    this.getUtilityBillsStore().resumeAutoSync();
                },
                scope: this
            });
            supplierStore.resumeAutoSync();
        }
    },

    handleSupplyGroupBlur: function(combo, event, opts){
        var supplyGroupStore = this.getSupplyGroupsStore();
        var supply_group = supplyGroupStore.findRecord('id', combo.getValue());
        if (combo.getRawValue() == '') {
            supplyGroupStore.rejectChanges();
            this.getUtilityBillsStore().rejectChanges();
            return;
        }
        var selected = combo.findParentByType('grid').getSelectionModel().getSelection()[0];
        var service = selected.get('service');
        if (service == 'Unknown' && supply_group === null) {
            Ext.Msg.alert('Status', 'supply_group cannot be created if service is Unknown');
            supplyGroupStore.rejectChanges();
            return;
        }
        if (supply_group === null){
            var utilBillsStore = this.getUtilityBillsStore();
            utilBillsStore.suspendAutoSync();
            supplyGroupStore.suspendAutoSync();


            supplyGroupStore.add({name: combo.getRawValue(),
                                 supplier_id: selected.get('supplier_id'),
                                 service: service});
            supplyGroupStore.sync({
                success: function(batch, options){
                    this.getUtilityBillsStore().resumeAutoSync();
                    selected.set('supply_group_id', batch.operations[0].records[0].get('id'));
                },
                failure: function(){
                    this.getUtilityBillsStore().resumeAutoSync();
                },
                scope: this
            });
            supplyGroupStore.resumeAutoSync();
        }
    },

    handleUtilityBlur: function(combo, event, opts){
        var utilityStore = this.getUtilitiesStore();
        if (combo.getRawValue() == '') {
            utilityStore.rejectChanges();
            this.getUtilityBillsStore().rejectChanges();
            return;
        }
        var selected = combo.findParentByType('grid').getSelectionModel().getSelection()[0];
        if (utilityStore.findRecord('id', combo.getValue()) === null){
            var utilBillsStore = this.getUtilityBillsStore();
            utilBillsStore.suspendAutoSync();
            utilityStore.suspendAutoSync();
            var supply_group_id = utilBillsStore.findRecord('id', selected.get('id')).get('supply_group_id');
            utilityStore.add({name: combo.getRawValue(),
                                 supply_group_id: supply_group_id});
            utilityStore.sync({
                success: function(batch, options){
                    this.getUtilityBillsStore().resumeAutoSync();
                    selected.set('utility_id', batch.operations[0].records[0].get('id'));
                },
                failure: function(){
                    this.getUtilityBillsStore().resumeAutoSync();
                },
                scope: this
            });
            utilityStore.resumeAutoSync();
        }
    }



});