import unittest
from unittest.mock import patch, call
import os
import ddf_exporter
import prometheus_client


class TestDdfExporter(unittest.TestCase):

    def _set_env_var(self, var: str, value):
        os.environ[var] = value

    def _reset_env_var(self, var, previous_value=None):
        if previous_value is None:
            # del is platform independent
            del os.environ[var]
        else:
            os.environ[var] = previous_value

    def setUp(self):
        # env vars for the test
        self.metric_prefix = 'test_case_'
        self.host = 'https://localhost'

        # env vars previous to the test
        self.old_metric_prefix = os.getenv('METRIC_PREFIX')
        self.old_host = os.getenv('HOST_ADDRESS')

        # set the env vars to the test ones
        self._set_env_var('METRIC_PREFIX', self.metric_prefix)
        self._set_env_var('HOST_ADDRESS', self.host)

    def tearDown(self):

        # set the env vars to whatever they were before the tests,
        # if they were None, just unset them.
        self._reset_env_var('METRIC_PREFIX', previous_value=self.old_metric_prefix)

        self._reset_env_var('HOST_ADDRESS', previous_value=self.old_host)


    def mocked_requests_session_get(*args, **kwargs):

        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code

            def json(self):
                return self.json_data

        if args[0] == 'https://localhost:8993/services/internal/metrics/':
            return MockResponse({'title': 'categoryQueries'}, 200)

        elif args[0] == 'https://localhost:8993/services/internal/metrics/testMetric.json?dateOffset=120':
            return MockResponse({'value': 0.0}, 200)

        elif args[0] == 'https://localhost:8993/services/internal/metrics/connectionError.json?dateOffset=120':
            return MockResponse({}, 403)

        return MockResponse(None, 404)


    @patch('requests.Session.get', side_effect=mocked_requests_session_get)
    def test__make_request_insecure(self, mock_get):

        os.environ['SECURE'] = "False"

        exp = ddf_exporter.DDFCollector()

        # test_acquire_endpoints_request
        json_data = exp._make_request('', offset=None)
        self.assertEqual(json_data, {'title': 'categoryQueries'}, 200)

        # test_successful_request
        exp.metric_endpoints['test_metric'] = 'testMetric'
        json_data = exp._make_request('test_metric')
        self.assertEqual(json_data, {'value': 0.0}, 200)

        # test_site_not_found_request
        exp.metric_endpoints['not_found_metric'] = 'notFoundMetric'
        json_data = exp._make_request('not_found_metric')
        self.assertIsNone(json_data)

        # test_no_data_field_response
        exp.metric_endpoints['connection_error'] = 'connectionError'
        json_data = exp._make_request('connection_error')
        self.assertDictEqual(json_data, {})


    @patch('requests.Session.get', side_effect=mocked_requests_session_get)
    @patch('os.path.isfile', return_value=True)
    def test__make_request_secure(self, mock_get, mock_os):

        os.environ['SECURE'] = "True"

        exp = ddf_exporter.DDFCollector()

        # test_acquire_endpoints_request
        json_data = exp._make_request('', offset=None)
        self.assertEqual(json_data, {'title': 'categoryQueries'}, 200)

        # test_successful_request
        exp.metric_endpoints['test_metric'] = 'testMetric'
        json_data = exp._make_request('test_metric')
        self.assertEqual(json_data, {'value': 0.0}, 200)

        # test_site_not_found_request
        exp.metric_endpoints['not_found_metric'] = 'notFoundMetric'
        json_data = exp._make_request('not_found_metric')
        self.assertIsNone(json_data)

        # test_no_data_field_response
        exp.metric_endpoints['connection_error'] = 'connectionError'
        json_data = exp._make_request('connection_error')
        self.assertDictEqual(json_data,{})


    @patch('requests.Session.get', side_effect=mocked_requests_session_get)
    @patch('os.path.isfile', return_value=False)
    def test__make_request_secure_no_file(self, mock_get, mock_os):

        os.environ['SECURE'] = "True"

        exp = ddf_exporter.DDFCollector()

        # test no cert response
        self.assertRaises(FileNotFoundError, exp._make_request, 'connection_error')


    def test__json_to_metric_generator(self):

        # test empty dict
        gen = ddf_exporter._json_to_metric_generator({})
        self.assertRaises(StopIteration, next, gen)

        # test dict with no data attribute
        gen = ddf_exporter._json_to_metric_generator({'title': 'Empty'})
        self.assertRaises(StopIteration, next, gen)

        # test dict with 1 result
        gen = ddf_exporter._json_to_metric_generator({
                'title': '1data',
                'data': [{'value': 0.0, 'timestamp': 'Jan 15 2019 12:07:00'}]})

        self.assertDictEqual(next(gen), {'value': 0.0, 'timestamp': 'Jan 15 2019 12:07:00'})

        self.assertRaises(StopIteration, next, gen)

        # test dict with multiple results
        gen = ddf_exporter._json_to_metric_generator({
            'title': '1data',
            'data': [{'value': 0.0, 'timestamp': 'Jan 15 2019 12:07:00'},
                    {'value': 0.3, 'timestamp': 'Jan 15 2019 12:08:00'}]
        })

        self.assertDictEqual(next(gen), {'value': 0.0, 'timestamp': 'Jan 15 2019 12:07:00'})
        self.assertDictEqual(next(gen), {'value': 0.3, 'timestamp': 'Jan 15 2019 12:08:00'})

        self.assertRaises(StopIteration, next, gen)


    def test_fetch_available_endpoints(self):

        # test with no responses
        with patch.object(ddf_exporter.DDFCollector, '_make_request', return_value={}) as mock_make_request:
            exp = ddf_exporter.DDFCollector()
            self.assertDictEqual(exp.fetch_available_endpoints(), {})

        # test with 1 response
        with patch.object(ddf_exporter.DDFCollector, '_make_request', return_value={'fakeItemA': 'a'}) as mock_make_request:
            exp = ddf_exporter.DDFCollector()
            self.assertDictEqual(exp.fetch_available_endpoints(), {'fake_item_a': 'fakeItemA'})

        # Test with multiple responses
        with patch.object(ddf_exporter.DDFCollector, '_make_request', return_value={'fakeItemA': 'a', 'fakeItemB': 'b'}) as mock_make_request:
            exp = ddf_exporter.DDFCollector()
            self.assertDictEqual(exp.fetch_available_endpoints(), {'fake_item_a': 'fakeItemA', 'fake_item_b': 'fakeItemB'})


    def mocked_make_request(*args, **kwargs):

        options = {
            'empty': {},
            'no_label': {'data': [{'value': 0.0}]},
            'yes_label': {'data': [{'value': 1.0}]},
            '1_0': {'data': []},
            '1_1': {'data': [{'value': 1.0}]},
            '1_2': {'data': [{'value': 1.0},
                             {'value': 2.0}]},
            '2_0_metric_1': {'data': []},
            '2_0_metric_2': {'data': []},
            '2_1_metric_1': {'data': [{'value': 1.0}]},
            '2_1_metric_2': {'data': [{'value': 2.0}]},
            '2_2_metric_1': {'data': [{'value': 1.0},
                             {'value': 2.0}]},
            '2_2_metric_2': {'data': [{'value': 1.0},
                             {'value': 2.0}]}
        }

        return options.get(args[0], 'no value found')


    @patch('ddf_exporter.DDFCollector._make_request', side_effect=mocked_make_request)
    def test_populate_and_fetch_metrics(self, mock_requests):

        exp = ddf_exporter.DDFCollector()

        # test empty dict
        metrics = exp.populate_and_fetch_metrics({}, self.metric_prefix)
        self.assertDictEqual(metrics, {})

        # test metric without labels
        with patch.object(prometheus_client.metrics_core.GaugeMetricFamily,'add_metric') as mock_add_metric:
            exp.populate_and_fetch_metrics({'no_label': 'no_label'},
                                            self.metric_prefix)

        mock_add_metric.assert_called_with(labels=[], value=0.0)

        # test metric with labels
        with patch.object(prometheus_client.metrics_core.GaugeMetricFamily,'add_metric') as mock_add_metric:
            exp.populate_and_fetch_metrics({'yes_label': 'yes_label'},
                                            self.metric_prefix,
                                            {'host_label': 'machine_yes_label'})

        mock_add_metric.assert_called_with(labels=['machine_yes_label'], value=1.0)

        # test 1 metric; 0 sample
        with patch.object(prometheus_client.metrics_core.GaugeMetricFamily, 'add_metric') as mock_add_metric:
            exp.populate_and_fetch_metrics({'1_0': '1_0'},
                                            self.metric_prefix,
                                            {'host_label': 'machine_1_0'})

        mock_add_metric.assert_not_called()

        # test 1 metric; 1 sample
        with patch.object(prometheus_client.metrics_core.GaugeMetricFamily, 'add_metric') as mock_add_metric:
            exp.populate_and_fetch_metrics({'1_1': '1_1'},
                                            self.metric_prefix,
                                            {'host_label': 'machine_1_1'})

        mock_add_metric.assert_called_with(labels=['machine_1_1'], value=1.0)

        # test 1 metric; multiple samples
        with patch.object(prometheus_client.metrics_core.GaugeMetricFamily, 'add_metric') as mock_add_metric:
            exp.populate_and_fetch_metrics({'1_2': '1_2'},
                                            self.metric_prefix,
                                            {'host_label': 'machine_1_2'})

        calls = [call(labels=['machine_1_2'], value=1.0), call(labels=['machine_1_2'], value=2.0)]
        mock_add_metric.assert_has_calls(calls)

        # test multiple metric; 0 sample
        with patch.object(prometheus_client.metrics_core.GaugeMetricFamily, 'add_metric') as mock_add_metric:
            exp.populate_and_fetch_metrics({'2_0_metric_1': '2_0_metric_1',
                                            '2_0_metric_2': '2_0_metric_2'},
                                            self.metric_prefix,
                                            {'host_label': 'machine_2_0'})

        mock_add_metric.assert_not_called()

        # test multiple metric; 1 sample
        with patch.object(prometheus_client.metrics_core.GaugeMetricFamily, 'add_metric') as mock_add_metric:
            exp.populate_and_fetch_metrics({'2_1_metric_1': '2_1_metric_1',
                                            '2_1_metric_2': '2_1_metric_2'},
                                            self.metric_prefix,
                                            {'host_label': 'machine_2_1'})

        calls = [call(labels=['machine_2_1'], value=1.0), call(labels=['machine_2_1'], value=2.0)]
        mock_add_metric.assert_has_calls(calls)
        # Its hard to tell because we are patching the add_metric method, but the metric_results would end up looking
        # similar to:
        # {
        #  '2_1_metric_1':
        # 	Metric(test_case_2_1_metric_1, ...,
        # 		[Sample(name='test_case_2_1_metric_1',
        # 				labels={'host_label': 'machine_2_1'},
        # 				value=1.0)
        # 		]
        # 	),
        #  '2_1_metric_2':
        # 	Metric(test_case_2_1_metric_2, ...,
        # 		[Sample(name='test_case_2_1_metric_2',
        # 				labels={'host_label': 'machine_2_1'},
        # 				value=2.0)
        # 		]
        # 	)
        # }

        # test multiple metric; multiple samples
        with patch.object(prometheus_client.metrics_core.GaugeMetricFamily, 'add_metric') as mock_add_metric:
            metrics = exp.populate_and_fetch_metrics({'2_2_metric_1': '2_2_metric_1',
                                                      '2_2_metric_2': '2_2_metric_2'},
                                                     self.metric_prefix,
                                                     {'host_label': 'machine_2_2'})

        calls = [call(labels=['machine_2_2'], value=1.0),
                 call(labels=['machine_2_2'], value=2.0),
                 call(labels=['machine_2_2'], value=1.0),
                 call(labels=['machine_2_2'], value=2.0)]
        mock_add_metric.assert_has_calls(calls)
        # {
        # '2_2_metric_1':
        #     Metric(test_case_2_2_metric_1, ...,
        #            [Sample(name='test_case_2_2_metric_1',
        #                    labels={'host_label': 'machine_2_1'},
        #                    value=1.0),
        #             Sample(name='test_case_2_2_metric_1',
        #                    labels={'host_label': 'machine_2_1'},
        #                    value=2.0)
        #             ]
        #     ),
        # '2_2_metric_2':
        #     Metric(test_case_2_2_metric_2, ...,
        #            [Sample(name='test_case_2_2_metric_2',
        #                    labels={'host_label': 'machine_2_1'},
        #                    value=1.0),
        #             Sample(name='test_case_2_2_metric_2',
        #                    labels={'host_label': 'machine_2_1'}
        #                    value = 2.0)
        #             ]
        #     )
        # }

    def test__camel_to_snake_case(self):

        # test empty string
        ans = ddf_exporter._camel_to_snake_case('')
        self.assertEqual(ans, '')

        # test camel case string
        ans = ddf_exporter._camel_to_snake_case('camelCaseString')
        self.assertEqual(ans, 'camel_case_string')

        # test upper camel case string
        ans = ddf_exporter._camel_to_snake_case('CamelCaseString')
        self.assertEqual(ans, 'camel_case_string')

        # test snake case string
        ans = ddf_exporter._camel_to_snake_case('snake_case_string')
        self.assertEqual(ans, 'snake_case_string')

        # test numbers in string
        ans = ddf_exporter._camel_to_snake_case('a1B2c34D')
        self.assertEqual(ans, 'a1_b2c34_d')

        # test all caps string
        ans = ddf_exporter._camel_to_snake_case('consecutiveUPPERCase')
        self.assertEqual(ans, 'consecutive_upper_case')









