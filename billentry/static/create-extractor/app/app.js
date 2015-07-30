'use strict';

//module declarations
angular.module('createExtractor', ['ngRoute']);


// Declare app level module which depends on views, and components
angular.module('createExtractor').

// add views to app.
config(['$routeProvider', function($routeProvider) {
  $routeProvider.
  	when('/settings', {
  		templateUrl: 'app/views/settings-view/settings.html',
  		controller: 'settingsViewCtrl'
  	}).
  	when('/settings/:bill_id', {
  		templateUrl: 'app/views/settings-view/settings.html',
  		controller: 'settingsViewCtrl'
  	}).
  	when('/test',{
  		templateUrl: 'app/views/extractor-test-view/extractor-test.html',
  		controller: 'extractorTestViewCtrl'
  	}).
  	otherwise({redirectTo: '/settings'});
}]);