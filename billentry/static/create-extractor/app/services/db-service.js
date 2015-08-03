'use strict';

angular.module('createExtractor').

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
    DBService.getDataTypes = function(){
      return $http.get('/get-data-types');
    };
    DBService.getTextLine = function(bill_id, regex){
      return $http.post('/get-text-line/'+bill_id, {regex: regex});
    };
    DBService.previewField = function(bill_id, field){
      return $http.post('/preview-field/'+bill_id, field);
    };

    return DBService;
}]);