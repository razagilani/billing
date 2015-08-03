'use strict';

angular.module('createExtractor').

controller('settingsViewCtrl', ['$scope', 'DBService', 'dataModel', function($scope, DBService, dataModel) {
	// initialize data model
	dataModel.initDataModel();
	$scope.extractor = dataModel.extractor;
	$scope.applier_keys = dataModel.applier_keys;
	$scope.field_types = dataModel.field_types;
	$scope.data_types = dataModel.data_types;

	//set up pdf viewer
	$scope.bill_id = 24153;

	// initialize values for bounding box corners 
	$scope.corners = [{number: 0, name: "Top Left"}, 
					  {number: 1, name: "Top Right"}, 
					  {number: 2, name: "Bottom Left"}, 
					  {number: 3, name: "Bottom Right"}];

	$scope.viewBill = function(){
		$scope.bill_id = $scope.extractor().representative_bill_id;
	}

	$scope.selected = null;
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
	}

	// allow the bounding box to be edited. 
	// This is in place so that people don't undo bounding boxes by accidentally clicking, etc.
	$scope.activateBoundingBox = function(){
		if ($scope.bboxActive == undefined){
			$scope.bboxActive = false;
		}
		$scope.bboxActive = !$scope.bboxActive;
	}

	$scope.clearBoundingBox = function(){
		$scope.selected.bounding_box.x0 = null;
		$scope.selected.bounding_box.y0 = null;
		$scope.selected.bounding_box.x1 = null;
		$scope.selected.bounding_box.y1 = null;
	}

	$scope.updateOffset = function(field){
		DBService.getTextLine($scope.bill_id, field.offset_regex)
			.success(function(textline){
				console.log(textline);
			})
			.error(function(data, status, headers, config){
				console.log("could not preview offset");
			});
	}

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


