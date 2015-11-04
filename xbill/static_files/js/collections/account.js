define(function (require) {

    "use strict";

    var $ = require('jquery');
    var Backbone = require('backbone');
    var Account = require('models/account');

    return Backbone.Collection.extend({
        model: Account,
        url: '/rest_api/referredaccounts',
        sort_asc: true,
        sort_property: 'last_name',

        comparator: function (model) {
            if (this.sort_property === 'tou_signed') {
                return !!model.get(this.sort_property);
            }
            return model.get(this.sort_property).toLowerCase();
        },

        filterByName: function (name) {
            name = name.toLowerCase();
            return this.filter(function (account) {
                var fn = account.get('first_name').toLowerCase();
                var ln = account.get('last_name').toLowerCase();
                return (fn.indexOf(name) > -1 || ln.indexOf(name) > -1);
            });
        }
    });

});