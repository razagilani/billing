module.exports = function(config){
  config.set({

    basePath : '../',

    files : [
      '../angular/bower_components/jquery/dist/jquery.js',
      '../angular/bower_components/angular/angular.js',
      '../angular/bower_components/angular-route/angular-route.js',
      '../angular/bower_components/angular-resource/angular-resource.js',
      '../angular/bower_components/angular-mocks/angular-mocks.js',
      '../ext/lib/pdf.js/pdf.js',
      'app/**/*.js',
      'test/unit/**/*.js'
    ],

    autoWatch : true,

    frameworks: ['jasmine'],

    browsers : ['Chrome'],

    plugins : [
            'karma-chrome-launcher',
            'karma-firefox-launcher',
            'karma-jasmine'
            ],

    junitReporter : {
      outputFile: 'test_out/unit.xml',
      suite: 'unit'
    }

  });
};