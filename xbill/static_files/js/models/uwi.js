define(function (require) {

    "use strict";

    var $ = require('jquery');
    var Backbone = require('backbone');

    return Backbone.Model.extend({
        defaults: {
            utility_username_decrypted: '',
            utility_password_decrypted: '',
            account: '',
            utility_provider: null
        }
    });

});