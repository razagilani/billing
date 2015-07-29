'use strict';

var dbServiceModule = angular.module('DBService', ['ngResource']).

// add service for getting data from server/DB
factory('DBService', ['$http',
  function($http){
    var DBService = {};

    // Each of these functions return a promise that executes the request.
    DBService.getUtilBill = function(id){
      return $http.get('/get-utilbill/'+id);
    };
    DBService.getApplierKeys = function(){
      return $http.get('/get-applier-keys');
    };
    DBService.getFieldTypes = function(){
      return $http.get('/get-field-types');
    };
    DBService.getFieldDataTypes = function(){
      return $http.get('/get-field-data-types');
    };

    return DBService;
}]);