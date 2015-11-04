define(function (require) {

    "use strict";

    var $ = require('jquery');
    var Backbone = require('backbone');

    return Backbone.Model.extend({
        defaults: {
            name: '',
            short_desc: '',
            description: '',
            content: '',
            modified: null,
            version: 1,
            lang: 'en'
        }
    });

});