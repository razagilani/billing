'use strict';

// Declare app level module which depends on views, and components
angular.module('createExtractor', [
  'ngRoute',
  'createExtractor.settingsView',
  'createExtractor.extractorTestView',
]).
// add main view to app. mainView corresponds to the extractor settings and the PDF viewer.
config(['$routeProvider', function($routeProvider) {
  $routeProvider.
  	when('/settings', {
  		templateUrl: 'views/settings-view/settings.html',
  		controller: 'settingsViewCtrl'
  	}).
  	when('/settings/:bill_id', {
  		templateUrl: 'views/settings-view/settings.html',
  		controller: 'settingsViewCtrl'
  	}).
  	when('/test',{
  		templateUrl: 'views/extractor-test-view/extractor-test.html',
  		controller: 'extractorTestViewCtrl'
  	}).
  	otherwise({redirectTo: '/settings'});
}]);