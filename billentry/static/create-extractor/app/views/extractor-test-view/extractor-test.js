'use strict';

angular.module('createExtractor').

controller('extractorTestViewCtrl', ['$scope', 'DBService', 'dataModel', function($scope, DBService, dataModel) {
	$scope.extractor = dataModel.extractor;
	$scope.applier_keys = dataModel.applier_keys;
	$scope.field_types = dataModel.field_types;
	$scope.data_types = dataModel.data_types;
	$scope.utilities = dataModel.utilities;
	$scope.batch_tests = dataModel.batch_tests;
	$scope.indiv_tests = dataModel.indiv_tests;

	$scope.newExtractor = dataModel.newExtractor;
	$scope.saveExtractor = dataModel.saveExtractor;
	$scope.loadExtractor = dataModel.loadExtractor;

	/* FUNCTION BINDINGS */

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
	};

	// Runs a test, and keeps track of its results / status.
	$scope.addTest = function(isBatch){
		var batchTestRun = function(){
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
					$scope.batch_tests().push(test_request);
				})
				.error(function(){
					console.log("failed to run batch test");
				});
		}

		var indivTestRun = function(){
			test_request.results = {};
			$scope.indiv_tests().push(test_request);
			DBService.runIndividualTest(test_request)
				.success(function(responseObj){
					$.extend(test_request.results, responseObj);
				})
				.error(function(){
					console.log("failed to run individual bill test.");
					test_request.failed = true;
				});
		}

		// copy test request template
		var test_request = $.extend({}, $scope.test_template);

		// saves the extractor, so it can be up to date on the server when the test is run.
		$scope.saveExtractor()
			.success(function(){
				test_request.extractor_id = $scope.extractor().extractor_id;
				test_request.batch = isBatch;
				if (isBatch){
					batchTestRun();
				} else {
					indivTestRun();
				}
			})
			.error(function(){
				console.log("Could not save extractor.");
			});
	}

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

	// Get all currently running batch tests, and load them into dataModel.batch_tests
	$scope.getRunningBatchTests = function(){
		if($scope.batch_tests().length != 0){
			return;
		}

		DBService.getRunningBatchTests()
			.success(function(responseObj){
				console.log(responseObj.tasks);
				console.log($scope.batch_tests());
				responseObj.tasks.forEach(function(t){
					t.results = {};
					t.batch = true;
					$scope.batch_tests().push(t);
				});
			})
			.error(function(){
				console.log("Failed to load tests.")
			});
	};

	// Gets the updated status for all batch tests from the server.
	$scope.refreshAllTests = function(){
		$scope.batch_tests().forEach($scope.refreshTest);
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

	/* INIT CODE */

	dataModel.initDataModel().then($scope.getRunningBatchTests);

	// the template for creating new tests. 
	// This template is modified by the UI, and when the user starts a test the template's variables are used as parameters.
	$scope.test_template = {};
	$scope.selected_test = null;

}]);
