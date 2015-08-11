'use strict';

describe('extractorTestViewCtrl', function() {
	beforeEach(module('createExtractor'));

	var $controller;

	beforeEach(inject(function(_$controller_){
		// The injector unwraps the underscores (_) from around the parameter names when matching
		$controller = _$controller_;
	}));

	describe('extractorTestViewCtrl controller', function(){
		var $scope, controller;

		beforeEach(function(){
			$scope = {};
			controller = $controller('extractorTestViewCtrl', { $scope: $scope });
		});

		it('should ....', function(){
			expect(4).toEqual(4);
		});

	});
});