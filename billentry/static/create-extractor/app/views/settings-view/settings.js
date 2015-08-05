'use strict';

angular.module('createExtractor').

controller('settingsViewCtrl', ['$scope', '$routeParams', 'DBService', 'dataModel', function($scope, $routeParams, DBService, dataModel) {
	// load bill id
	if($routeParams.bill_id){
		$scope.bill_id = $routeParams.bill_id;
	} 
	else if(dataModel.extractor().representative_bill_id != null) {
		$scope.bill_id = dataModel.extractor().representative_bill_id;
	}
	else {
		$scope.bill_id = null;
	}

	// initialize data model, and then refresh scope
	dataModel.initDataModel($scope.bill_id)
		.then(function(){
			$scope.$apply();
		});

	$scope.selected = null;

	$scope.corners = [
		{number:0, name: "top left"},
		{number:1, name: "top right"},
		{number:2, name: "bottom left"},
		{number:3, name: "bottom right"},
	]

	/* EVERYTHING BELOW HERE IS A FUNCTION BINDING */

	$scope.extractor = dataModel.extractor;
	$scope.applier_keys = dataModel.applier_keys;
	$scope.field_types = dataModel.field_types;
	$scope.data_types = dataModel.data_types;

	$scope.newExtractor = dataModel.newExtractor;
	$scope.saveExtractor = dataModel.saveExtractor;
	$scope.loadExtractor = dataModel.loadExtractor;

	$scope.viewBill = function(){
		$scope.bill_id = $scope.extractor().representative_bill_id;
	}

	// Updates origin_x and origin_y using origin_regex
	$scope.updateExtractorOrigin = function(){
		var ex = $scope.extractor();
		if (ex.origin_regex == null || ex.origin_regex == ""){
			ex.origin_obj = null;
			return;
		}
		DBService.getTextLine($scope.bill_id, ex.origin_regex, 1)
			.success(function(data, status, headers, config){
				ex.origin_obj = data.textline;
				ex.origin_x = ex.origin_obj.x0;
				ex.origin_y = ex.origin_obj.y1;
			})
			.error(function(data, status, headers, config){
				console.log("Could not update origin.");
			});
	}

	// shows the "load extractor" menu.
	$scope.showLoadScreen = function(){
		$scope.viewLoadScreen = !$scope.viewLoadScreen;
		if($scope.viewLoadScreen){
			DBService.getExtractors()
				.success(function(data, status, headers, config){
					$scope.availableExtractors = data.extractors;
				})
				.error(function(data, status, headers, config){
					console.log("Could not load extractors");
				});
		}
	}

	// when an extractor is selected from the load menu
	$scope.chooseExtractor = function(id){
		$scope.viewLoadScreen = false;
		$scope.loadExtractor(id).success(function(){
			$scope.selected = null;

			// update offset objects for drawing individual fields
			var offsetTasks = [];
			$scope.extractor().fields.forEach(function(field){
				if (field.offset_regex){
					offsetTasks.push($scope.updateOffset(field));
				}
			});
			Promise.all(offsetTasks).then($scope.paintCanvas);
		});
	}

	// select a field, so one can view/edit its parameters
	$scope.selectField = function(field){
		if (!field.enabled){
			$scope.enableField(field);
			$scope.selected = field;
		} 
		// clicking on an already selected field de-selects it unless it was disabled.
		else {
			if ($scope.selected == field){
				$scope.selected = null;
			} else {
				$scope.selected = field;
			}
		}
	}
	// enable a field, so that it will be used in extraction
	$scope.enableField = function(field){
		field.enabled = !field.enabled;
		$scope.paintCanvas();
	}

	// allow the bounding box to be edited. 
	// This is in place so that people don't undo bounding boxes by accidentally clicking, etc.
	$scope.activateBoundingBox = function(){
		if ($scope.bboxActive == undefined){
			$scope.bboxActive = false;
		}
		$scope.bboxActive = !$scope.bboxActive;
	}

	// reset the bounding box for a field
	$scope.clearBoundingBox = function(){
		$scope.selected.bounding_box = null;
	}

	// Use the offset_regex to find an object to use as a the relative origin for bounding box coordinates. 
	// This function does not need to be called to create a valid extractor, but it updates the view to 
	// take offset_regex into account, making the UI more intuitive. 
	$scope.updateOffset = function(field){
		if (field.offset_regex == null || field.offset_regex == ""){
			field.offset_obj = null;
			return Promise.resolve(null);
		}

		return DBService.getTextLine($scope.bill_id, field.offset_regex, field.page_num, field.maxpage)
			.success(function(responseJSON){
				field.offset_obj = responseJSON.textline;
			})
			.error(function(data, status, headers, config){
				field.offset_obj = null;
				console.log("could not preview offset");
			});
	}

	// Test the output of a single field
	$scope.previewField = function(field){
		DBService.previewField($scope.bill_id, field)
			.success(function(data, status, headers, config){
				$scope.preview_output = data.field_output;
			})
			.error(function(data, status, headers, config){
				$scope.preview_output = "(preview failed)";
				console.log("Field preview failed.");
				console.log(data);
			});
	}
}]);


