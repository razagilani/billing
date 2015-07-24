'use strict';

// Declare app level module which depends on views, and components
angular.module('createExtractor', [
  'ngRoute',
  'createExtractor.mainView'
]).
config(['$routeProvider', function($routeProvider) {
  $routeProvider.otherwise({redirectTo: '/mainView'});
}]);
