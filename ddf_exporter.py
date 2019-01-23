#!/usr/bin/env python

from typing import Optional, Iterator
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

import requests, sys, time, os, signal, re
from requests import Timeout, TooManyRedirects


class DDFCollector:

    def __init__(self):

        self.metric_prefix = os.getenv('METRIC_PREFIX', 'ddf_')
        self.host = os.getenv('HOST_ADDRESS', 'https://localhost')
        self.host_port = os.getenv('HOST_PORT', 8993)
        self.metric_api_location = os.getenv('METRIC_API_LOCATION',
                                             'services/internal/metrics')
        self.secure = os.getenv('SECURE', "True")
        self.ca_cert_path = os.getenv('CA_CERT_PATH', '/certs/ca.pem')

        self.file_ext = '.json'

        self.metric_endpoints = {}
        self.metric_results = {}

    # The collect method is used whenever a scrape request from prometheus activates this script.
    def collect(self):
        # get the endpoints
        self.metric_endpoints = self.fetch_available_endpoints()

        # fetch data from those endpoints
        self.metric_results = self.populate_and_fetch_metrics(
            self.metric_endpoints,
            self.metric_prefix,
            labels={'host': self.host})

        # yield the data as metrics
        for metric_name in self.metric_endpoints.keys():
            yield self.metric_results[metric_name]

    # If offset is less than 120, then there may be no record, as the server may still be collecting that info.
    def _make_request(self, metric_name: str, offset: Optional[int] = 120) -> dict:
        """
        Sends a get request based on a specified metric, and then returns the json.

        :param metric_name: The name of the metric, which will be used to lookup the corresponding endpoint
        :param offset: From the present, how many seconds into the past to fetch data for that metric
        :return: The dict/json representing the response
        """

        query_url = '{host}:{host_port}/{api_location}/'.format(
            **{
                'host': self.host,
                'host_port': self.host_port,
                'api_location': self.metric_api_location
            })

        # If no offset, then we only want the base url.
        if offset is not None:
            query_url += '{metric_endpoint}{file_ext}?dateOffset={offset}'.format(
                **{
                    'metric_endpoint': self.metric_endpoints.get(metric_name),
                    'file_ext': self.file_ext,
                    'offset': str(offset)
                })

        download = None
        with requests.Session() as session:
            try:
                # User wants to operate insecurely, or the host is not an https request.
                # Have to hardcode strings because dockerfiles cannot handle booleans
                if self.secure == "False" or not query_url.startswith("https://"):
                    download = session.get(query_url, verify=False)
                    # shows a warning if using HTTPS, does not do so if using http.

                # If user wants to operate securely and they provided a certificate in the certs directory.
                elif self.secure == "True" and os.path.isfile(self.ca_cert_path):
                    download = session.get(query_url, verify=self.ca_cert_path)

                # If the user wants to operate securely but didn't provide a certificate, we can't get metrics.
                else:
                    raise FileNotFoundError(
                        'Secure metric connections are enabled but could not locate cert.pem inside of cacerts directory. '
                        'Either set environment variable SECURE to \"False\", or place a certificate at the path listed in the CA_CERT_PATH env variable.'
                        'See readme for more details.'
                    )

            except requests.RequestException as e:
                # DNS failure, refused connection, etc
                print("Error: " + str(e))
                return {}

        return download.json()

    def fetch_available_endpoints(self) -> dict:
        """
        Query the metrics endpoint to get available metrics, then process the result into a snake_case: camelCase
        dictionary.

        :return: a dict representing the snake_case: camelCase available endpoints
        """
        endpoints = list(self._make_request('', offset=None).keys())

        available_endpoints = {}
        for endpoint in endpoints:
            available_endpoints[_camel_to_snake_case(endpoint)] = endpoint

        return available_endpoints

    def populate_and_fetch_metrics(self,
                                   available_endpoints: dict,
                                   prefix: str,
                                   labels: Optional[dict] = None) -> dict:
        """
        Query each available endpoint, retrieve it's value/values at that time, and store it into a results dictionary.

        :param available_endpoints: dictionary of snake_case: camelCase strings representing metric endpoints
        :param prefix: the prefix to be prepended to all metrics generated by this exporter
        :param labels: an optional set of tags for to include on the metrics
        :return: a dictionary of metrics with their corresponding values as retrieved from the endpoint
        """
        metric_results = {}

        if labels is None:
            labels = {}

        # for every available endpoint
        for metric_name in available_endpoints.keys():

            # Create an empty metric for that endpoint to hold its results
            metric_results[metric_name] = GaugeMetricFamily(
                prefix + metric_name, metric_name, labels=labels.keys())

            # Call to that endpoint and add all of its datapoints to the results.
            # Empty metrics are automatically hidden in prometheus, so an endpoint that responded
            # without data doesn't present an issue.
            for data_point in _json_to_metric_generator(self._make_request(metric_name)):
                metric_results[metric_name].add_metric(labels=list(labels.values()), value=data_point['value'])

        return metric_results


def _json_to_metric_generator(json_response: dict) -> Iterator[dict]:
    """
    The returned JSON may or may not have multiple data rows, this helper function makes the results
    iterable so that these multiple rows can be handled in a loop.

    :param: json_response, a dict object representing the jason file. Its structure is:
    {
       "data":[
          {
             "value": flt,
             "timestamp": str
          },
          {
             "value": flt,
             "timestamp": str
          },
          ...
       ],
       "title": str,
       "totalCount": int
    }

    :rtype: dict
    """

    # see if there are any data tags inside the response
    data = json_response.get('data')
    if data is None or len(data) == 0:
        return

    for data_point in data:
        yield data_point


def _camel_to_snake_case(string: str) -> str:
    """
    converts camelCase to snake_case.
    snake_case is used for metric names.
    camelCase is used for endpoint names.

    :rtype: str
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', string)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def sigterm_handler(_signo, _stack_frame):
    sys.exit(0)


if __name__ == '__main__':
    # Ensure we have something to export
    start_http_server(int(os.getenv('BIND_PORT', 9170)))
    REGISTRY.register(DDFCollector())

    signal.signal(signal.SIGTERM, sigterm_handler)
    while True:
        time.sleep(1)
