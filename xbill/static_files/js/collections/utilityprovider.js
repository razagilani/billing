define(function (require) {

    "use strict";

    var $ = require('jquery');
    var Backbone = require('backbone');
    var UtilityProvider = require('models/utilityprovider');

    return Backbone.Collection.extend({
        model: UtilityProvider,
        url: '/rest_api/utilityproviders'
    });

});
