'use strict';

/* Services */

var dbService = angular.module('dbService', ['ngResource']);

dbService.factory('BillingDataOp', ['$http',
  function($http){
    var BillingDataOp = {};

    BillingDataOp.getUtilBill = function(id){
    	return $http.get('/get-utilbill/'+id);
    }
    BillingDataOp.getApplierKeys = function(){
    	return $http.get('/get-applier-keys');
    }
    BillingDataOp.getFieldTypes = function(){
    	return $http.get('/get-field-types');
    }
    BillingDataOp.getFieldDataTypes = function(){
    	return $http.get('/get-field-data-types');
    }

    return BillingDataOp;
  }]);
