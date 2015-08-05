'use strict';

angular.module('createExtractor').

controller('extractorTestViewCtrl', ['$scope', 'DBService', 'dataModel', function($scope, DBService, dataModel) {
	$scope.extractor = dataModel.extractor;
	$scope.applier_keys = dataModel.applier_keys;
	$scope.field_types = dataModel.field_types;
	$scope.data_types = dataModel.data_types;
	$scope.utilities = dataModel.utilities;

	$scope.newExtractor = dataModel.newExtractor;
	$scope.saveExtractor = dataModel.saveExtractor;
	$scope.loadExtractor = dataModel.loadExtractor;

	// the template for creating new tests. 
	// This template is modified by the UI, and when the user starts a test the template's variables are used as parameters.
	$scope.test_template = {};

	$scope.tests = [];

	

}]);
