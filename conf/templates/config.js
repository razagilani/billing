{
  librato: {
    email:  "itops@nextility.com",
    // read-only API token
    token:  "3ee3f68e175297f0d12986d9cbbec2bac503c1f8101ef5c10b1c89579172392c",
    source: "<%= @env%>"
  }
  , backends: ["statsd-librato-backend"]
  , port: 8125
}
