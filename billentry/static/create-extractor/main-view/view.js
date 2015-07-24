'use strict';

angular.module('myApp.mainView', ['ngRoute'])

.config(['$routeProvider', function($routeProvider) {
  $routeProvider.when('/', {
    templateUrl: 'main-view/view.html',
    controller: 'mainViewCtrl'
  });
}])

.controller('mainViewCtrl', [function() {
	
}]);