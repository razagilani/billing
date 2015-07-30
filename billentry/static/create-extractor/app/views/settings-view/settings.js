'use strict';

angular.module('createExtractor').

controller('settingsViewCtrl', ['$scope', 'DBService', 'dataModel', function($scope, DBService, dataModel) {
	// initialize data model
	dataModel.initDataModel();
	$scope.extractor = dataModel.extractor();
	$scope.applier_keys = dataModel.applier_keys();
	$scope.field_types = dataModel.field_types();
	$scope.data_types = dataModel.data_types();

	//set up pdf viewer
	$scope.bill_id = 24153;

	// initialize values for bounding box corners 
	$scope.corners = [
		{name: "Top Left", value: 0},
		{name: "Top Right", value: 1},
		{name: "Bottom Left", value: 2},
		{name: "Bottom Right", value: 3}];

	/**
	* Create an array of page numbers for the current PDF document. 
	 * 'withNull' specifies whether to provide a 'null' option for the page number.
	*/
	$scope.getPDFPageNums = function(withNull){
		var pdfPageNums = withNull ? [null] : [];
		if($scope.pdfDoc){
			for(var i = 1; i <= $scope.pdfDoc.numPages; i++){
				pdfPageNums.push(i);	
			}
		}
		return pdfPageNums;
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
}]);


