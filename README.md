# DDFexporter for Prometheus

A prometheus exporter for the metrics endpoint in DDF.

## Installation
Configure your prometheus instance to scrape from this module.

## Configuration options
This exporter can be configured using environment variables, they are as follows:

| Env variable      | Default           | Description  |
| ------------- |:-------------:| -----:|
| `BIND_PORT`| 9170 | The port for the exporter to bind to
| `METRIC_PREFIX` | "ddf_" | What to prepend to all of the gathered metrics
| `HOST_ADDRESS` | "https://localhost" | The address to gather metrics from. Please include the http:// or https://
| `HOST_PORT` | 8993 | The port to gather metrics from
| `METRIC_API_LOCATION` | "services/internal/metrics" | The path to the metrics endpoint
| `SECURE` | "True" | Whether to use ssl for the connection. <br/> If true, you must point to a valid ca cert in the next parameter
| `CA_CERT_PATH` | "/certs/ca.pem" | The path to the ca cert to be used during secure connections

### Docker-compose example

<details><summary>Click to expand</summary>
<p>

```
...
    ddfexporter:
        build: ./
        ports:
          - 9170:9170
   
        environment:
          BIND_PORT: 9170
          HOST_ADDRESS: "https://localhost"
          HOST_PORT: 8993
          METRIC_PREFIX: "ddf_"
          METRIC_API_LOCATION: "services/internal/metrics"
          SECURE: "True"
    
        volumes:
          - type: bind
            source: ./cacert.pem
            target: /cacerts/cert.pem
...
```

</p>
</details>

