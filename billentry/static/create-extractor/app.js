'use strict';

// Declare app level module which depends on views, and components
angular.module('createExtractor', [
  'ngRoute',
  'createExtractor.mainView'
]).
// add main view to app. mainView corresponds to the extractor settings and the PDF viewer.
config(['$routeProvider', function($routeProvider) {
  $routeProvider.otherwise({redirectTo: '/mainView'});
}]);
