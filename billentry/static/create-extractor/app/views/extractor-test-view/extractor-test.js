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

	dataModel.initDataModel();

	// the template for creating new tests. 
	// This template is modified by the UI, and when the user starts a test the template's variables are used as parameters.
	$scope.test_template = {};
	$scope.batch_tests = [];
	$scope.indiv_tests = [];
	$scope.selected_test = null;

	/* EVERYTHING BELOW HERE IS A FUNCTION BINDING */

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
		$scope.loadExtractor(id);
	}

	// Sends a batch task to the server. 
	$scope.addBatchTest = function(){
		// copy test template for request.
		// Only need to do a shallow copy, as all the parameters are strings/numbers.
		var test_request = $.extend({}, $scope.test_template);
		test_request.extractor_id = $scope.extractor().extractor_id;
		test_request.batch = true;

		DBService.runBatchTest(test_request)
			.success(function(responseObj){
				test_request.bills_to_run = responseObj.bills_to_run;
				// check if task is empty
				if (test_request.bills_to_run > 0){
					test_request.task_id = responseObj.task_id;
				} else {
					test_request.status = "No bills to run.";
				}
				test_request.results = {};

				// add task to tests list
				$scope.batch_tests.push(test_request);
			})
			.error(function(){
				console.log("failed to run batch test");
			});
	};

	// Sends an individual task to the server (i.e. runs only one bill)
	$scope.addIndividualTest = function(){
		var test_request = $.extend({}, $scope.test_template);
		test_request.extractor_id = $scope.extractor().extractor_id;
		test_request.batch = false;
		test_request.results = {}
		$scope.indiv_tests.push(test_request);

		DBService.runIndividualTest(test_request)
			.success(function(responseObj){
				$.extend(test_request.results, responseObj);
			})
			.error(function(){
				console.log("failed to run individual bill test.");
				test_request.failed = true;
			});
	};

	// selects a test, and displays detailed info for it in the view.
	// If the test is already selected, this de-selects it.
	$scope.selectTest = function(test){
		if ($scope.selected_test == test){
			$scope.selected_test = null;
		}
		else {
			$scope.selected_test = test;
		}
	};

	// Stops a given batch test by sending the server a stop request.
	$scope.stopTest = function(test){
		if(!test.batch){
			return;
		}
		DBService.stopTest(test.task_id)
			.success(function(){
				test.status = "STOPPED";
			})
			.error(function(){
				console.log("Could not stop test "+test.task_id);
			});
	}

	// Gets the updated status for all batch tests from the server.
	$scope.refreshAllTests = function(){
		$scope.batch_tests.forEach($scope.refreshTest);
	};

	// Updates the status for one test by querying the server.
	$scope.refreshTest = function(test){
		if (!test.task_id){
			return;
		}
		DBService.getTestStatus(test.task_id)
			.success(function(responseObj){
				$.extend(test.results, responseObj);
				test.status = test.results.state;
			})
			.error(function(){
				console.log("Could not get task status for task "+test.task_id);
			});
	}

	$scope.testHasResults = function(test){
		return !$.isEmptyObject(test.results);
	}

}]);
