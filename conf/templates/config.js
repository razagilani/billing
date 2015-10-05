{
  librato: {
    email:  "itops@nextility.com",
    token:  "", # TODO
    source: "<%= @env%>"
  }
  , backends: ["statsd-librato-backend"]
  , port: 8125
}
