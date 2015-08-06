'use strict';

angular.module('createExtractor').

/** 
* Service for manipulating the data model of the app.
* Provides functions for initalizing and getting the extractor, as well as applier keys, field types, etc.
*/
factory('dataModel', ['DBService', function(DBService){
	var _applier_keys = [];
	var _field_types = [];
	var _data_types = [];
	var _utilities = [];

	// stores data about the extractor being manipulated
	var _extractor = {};

	/**
	* Initializes the app's data model. 
	* Gets data from the server, including a list of applier keys and field types,
	* and creates a new, blank extractor. 
	*/
	var initDataModel = function(rep_bill_id){
		// if data model has already been initialized, return
		if (! $.isEmptyObject(_extractor)){
			return Promise.resolve(null);
		} 

		//Get applier keys
		var applier_keys_promise = DBService.getApplierKeys()
			.success(function(responseObj){
				_applier_keys = responseObj.applier_keys;
		});

		//Get field types
		var field_types_promise = DBService.getFieldTypes()
			.success(function(responseObj){
				_field_types = responseObj.field_types;
		});

		//Get field data types
		var data_types_promise = DBService.getDataTypes()
			.success(function(responseObj){
				_data_types = responseObj.data_types;
		});

		//Get utilities
		var utilities_promise = DBService.getUtilities()
			.success(function(responseObj){
				_utilities = responseObj.rows;
		});

		// execute the above requests asynchronously, and then create a new extractor
		var promises = [applier_keys_promise, field_types_promise, data_types_promise, utilities_promise];
		return Promise.all(promises).then(function(){
			newExtractor(rep_bill_id);
		});
	};


	/**
	* Resets _extractor with a new extractor with default values.
	* Also adds a field for each applier key; each field is disabled by default 
	*/
	var newExtractor = function(rep_bill_id){
		_extractor = {}
		_extractor.fields = [];
		_extractor.name = "New Extractor Name";
		_extractor.representative_bill_id = rep_bill_id;
		_extractor.origin_regex = null;
		_extractor.origin_x = null;
		_extractor.origin_y = null;

		// add a default, disabled field for each applier key
		_applier_keys.forEach(function(applier_key){
			_extractor.fields.push(getNewField(applier_key));
		});
	};

	/**  
	* Returns a new field, disabled by default.
	* The field type and data type are the first elements in the 
	* _field_types and _data_types arrays, respectively.
	*/
	var getNewField = function(applier_key){
		var new_field = {
			applier_key: applier_key,
			discriminator: _field_types[0],
			type: _data_types[0],
			enabled: false,

			page_num: 1,
			maxpage: null,
			bbregex: null,
			offset_regex: null,
			bounding_box: null,
			corner: 0,

			//table specific parameters
			table_start_regex: null,
			table_stop_regex: null,
			multipage_table: false,
			nextpage_top: null
		};
		return new_field;
	};

	var saveExtractor = function(){
		return DBService.saveExtractor(_extractor)
			.success(function(responseObj){
				_extractor.id = responseObj.id;
				console.log("saved successfully to id "+_extractor.id);
			})
			.error(function(){
				console.log("failed to save extractor to db.");
			});
	}

	var loadExtractor = function(id){
		return DBService.loadExtractor(id)
			.success(function(responseObj){
				console.log(responseObj.extractor);
				_extractor = responseObj.extractor;
				_extractor.id = _extractor.extractor_id;
			})
			.error(function(){
				console.log("failed to load extractor from db.");
			});
	}

	return {
		extractor: function(){ return _extractor;},
		applier_keys: function(){ return _applier_keys;},
		field_types: function(){ return _field_types;},
		data_types: function(){ return _data_types;},
		utilities: function(){ return _utilities;},
		initDataModel: initDataModel,
		newExtractor: newExtractor,
		getNewField: getNewField,
		saveExtractor: saveExtractor,
		loadExtractor: loadExtractor,
	};
}]);
	